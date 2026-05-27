# src/agents/outcome_tracker.py
"""
OutcomeTracker — closes the learning loop between signals and real results.

Runs at the START of each daily loop (Phase 0), before SignalGenerator, so
lessons from yesterday's trades are already in the vault (and therefore in RAG
context) when today's signals are generated.

What it does each run:
  1. Reads all signals from vault/03-Trade-Journal/signals_*.md (last 60 days)
  2. Reads real filled-order history from Alpaca
  3. Reads current prices from saved CSVs to estimate outcomes for older signals
  4. Matches signals → outcomes (WIN / LOSS / OPEN / EXPIRED / NO_SIGNAL)
  5. Writes a structured lesson note to vault/08-Logs/OUTCOMES_YYYY-MM-DD.md
  6. Maintains a running ledger at vault/09-Portfolio/signal_ledger.json
  7. Asks Claude to extract *patterns* from the win/loss history
     → these pattern notes are indexed by RAG and inform tomorrow's agents

The pattern extraction is the key learning mechanism:
  "RSI>70 entries: 1 win / 8 losses (11% win rate) → flag as HIGH RISK"
  "Above-SMA200 + MACD bullish: 7 wins / 3 losses (70% win rate) → favour"
  "Entries within 5 days of earnings: 0 wins / 4 losses → gate correctly"
"""

import json
import re
import pandas as pd
from pathlib import Path
from datetime import datetime, date, timedelta
from src.agents.base import BaseAgent
from src.alpaca_broker import AlpacaBroker
from src.llm import TradingLLM
from config import WATCHLIST


class OutcomeTracker(BaseAgent):
    LOOKBACK_DAYS   = 60    # how many days of signal history to scan
    RESOLUTION_DAYS = 5     # signals older than this are considered "resolved"

    def __init__(self):
        super().__init__(
            "OutcomeTracker",
            "You are OutcomeTracker. Analyse the win/loss history of recent trading signals "
            "and extract actionable patterns that agents can use to improve future decisions.\n\n"
            "Structure your output with:\n"
            "## Win Rate by Condition\n"
            "  For each indicator condition (RSI level, MACD direction, BB position, "
            "  SMA relationship, regime), show: wins / total and win rate %. "
            "  Bold conditions with win rate >60% (favourable) or <35% (avoid).\n"
            "## Recurring Mistakes\n"
            "  List the top 3 error patterns with specific examples and fix rules.\n"
            "## Rule Updates (CRITICAL — agents read these)\n"
            "  Bullet each rule change as an actionable instruction:\n"
            "  '✅ FAVOUR: [condition] — [win rate]% win rate over [N] signals'\n"
            "  '🚫 AVOID: [condition] — [win rate]% win rate over [N] signals'\n"
            "  '⚠️  ADJUST: [parameter] — [specific change and rationale]'\n"
            "## Regime Performance\n"
            "  How do signals perform in Bullish vs Ranging vs Bearish regimes?\n"
            "## Next-Session Priorities\n"
            "  3 concrete things to watch for in tomorrow's signals.\n\n"
            "Use only the real outcome data provided. Never fabricate win rates.",
            model=TradingLLM.SONNET,
            max_tokens=2000,
            rag_top_k=3,
        )
        self.broker = AlpacaBroker()

    # ── Signal parsing ────────────────────────────────────────────────────────

    def _parse_signals_file(self, filepath: Path, signal_date: str) -> list[dict]:
        """Extract all BUY/SELL/NO_SIGNAL entries from a signals markdown file."""
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        signals = []
        blocks  = re.split(r'###\s+', text)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            ticker_m = re.match(r'([A-Z]{1,5})\b', block)
            if not ticker_m:
                continue
            ticker = ticker_m.group(1).upper()
            if ticker in {"SIGNAL", "REPORT", "SUMMARY", "NOTE", "TRADE", "TICKER"}:
                continue

            def _str_field(pattern, default=""):
                m = re.search(pattern, block, re.IGNORECASE)
                return m.group(1).strip() if m else default

            def _float_field(pattern):
                m = re.search(pattern, block, re.IGNORECASE)
                if not m:
                    return None
                try:
                    return float(m.group(1).replace(",", "").replace("$", "").replace("*", ""))
                except ValueError:
                    return None

            direction_raw = _str_field(r'DIRECTION\s*[:\-]\s*[\*\s]*([\w\s]+?)(?:\n|$)')
            direction_raw = direction_raw.upper().replace("*", "").strip()
            if "NO" in direction_raw or direction_raw == "":
                direction = "NO_SIGNAL"
            elif "BUY" in direction_raw or "LONG" in direction_raw:
                direction = "BUY"
            elif "SELL" in direction_raw or "SHORT" in direction_raw:
                direction = "SELL"
            else:
                direction = "NO_SIGNAL"

            confidence_m = re.search(r'CONFIDENCE\s*[:\-]\s*(\d+)', block)
            confidence   = int(confidence_m.group(1)) if confidence_m else 0

            rationale = _str_field(r'RATIONALE\s*[:\-]\s*(.+?)(?:\n\n|\Z)', "")[:300]

            signals.append({
                "date":       signal_date,
                "ticker":     ticker,
                "direction":  direction,
                "entry":      _float_field(r'ENTRY\s*[:\-][^\d]*([0-9,]+\.?\d*)'),
                "stop":       _float_field(r'STOP\s*[:\-][^\d]*([0-9,]+\.?\d*)'),
                "target":     _float_field(r'TARGET\s*[:\-][^\d]*([0-9,]+\.?\d*)'),
                "confidence": confidence,
                "rationale":  rationale,
                "outcome":    "OPEN",   # will be resolved below
                "outcome_pct": None,
                "outcome_note": "",
            })
        return signals

    def _load_all_signals(self) -> list[dict]:
        """Parse signals files from the last LOOKBACK_DAYS days."""
        journal_dir = Path(self.vault.root) / "03-Trade-Journal"
        cutoff      = date.today() - timedelta(days=self.LOOKBACK_DAYS)
        all_signals = []
        for f in sorted(journal_dir.glob("signals_*.md"), reverse=True):
            date_str = f.stem.replace("signals_", "")
            try:
                sig_date = date.fromisoformat(date_str)
            except ValueError:
                continue
            if sig_date < cutoff:
                break
            all_signals.extend(self._parse_signals_file(f, date_str))
        return all_signals

    # ── Outcome resolution ────────────────────────────────────────────────────

    def _load_ohlc_data(self, tickers: list[str]) -> dict[str, pd.DataFrame]:
        """
        Load OHLC bars from vault CSVs for bar-by-bar stop/target resolution.

        Previously the system used today's close price to guess outcomes, which
        is wrong: a signal from 10 days ago may have hit its stop on day 3,
        recovered, and now sits above entry — old logic would mark it OPEN (or
        even WIN) when the real outcome was a LOSS.

        This loads the full daily bar history so _resolve_signal() can walk
        each bar after the signal date and find the first level touched.
        """
        ohlc: dict[str, pd.DataFrame] = {}
        csv_dir = Path(self.vault.root) / "01-Assets" / "Stocks"
        for ticker in tickers:
            csv_path = csv_dir / f"{ticker}.csv"
            if not csv_path.exists():
                continue
            try:
                df = pd.read_csv(str(csv_path))
                df.columns = [c.lower() for c in df.columns]

                # Normalise the date column (vault CSVs use 'timestamp' or 'date')
                date_col = next(
                    (c for c in ("timestamp", "date") if c in df.columns),
                    df.columns[0],   # last resort: first column
                )
                df["timestamp"] = pd.to_datetime(df[date_col], errors="coerce")
                df = df.dropna(subset=["timestamp"])

                # Keep only what we need; coerce prices to float
                keep = ["timestamp"] + [c for c in ("high", "low", "close") if c in df.columns]
                df = df[keep].copy()
                for col in ("high", "low", "close"):
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                df = df.sort_values("timestamp").reset_index(drop=True)
                ohlc[ticker] = df
            except Exception as e:
                print(f"   OutcomeTracker: OHLC load error for {ticker}: {e}")
        return ohlc

    def _load_alpaca_fills(self) -> dict[str, list[dict]]:
        """
        Fetch recent Alpaca filled orders grouped by ticker.
        Used to match executed signals to actual fill prices.
        """
        fills: dict[str, list[dict]] = {}
        try:
            orders = self.broker.get_recent_orders(limit=200)
            for o in orders:
                if float(o.get("filled_qty", 0)) > 0:
                    sym = o.get("symbol", "")
                    if sym:
                        fills.setdefault(sym, []).append(o)
        except Exception as e:
            print(f"   OutcomeTracker: could not fetch Alpaca fills: {e}")
        return fills

    def _resolve_signal(self, sig: dict, ohlc_data: dict,
                        alpaca_fills: dict) -> dict:
        """
        Determine the outcome of a past signal.

        Resolution priority
        -------------------
        1. Real Alpaca closing fill — most accurate, used when available.
        2. Bar-by-bar OHLC walk — check each day's High/Low after the signal
           date; return the outcome on the first bar that touches stop or target.
           This correctly handles: gap-downs past stop, mid-week target hits that
           reversed before today, etc.  The old current-price snapshot approach
           got all of these wrong.
        3. UNKNOWN — no OHLC data available for this ticker.

        Signals younger than RESOLUTION_DAYS are always left as OPEN.
        """
        sig_date = date.fromisoformat(sig["date"])
        age_days = (date.today() - sig_date).days

        # Too recent — leave open
        if age_days < self.RESOLUTION_DAYS:
            sig["outcome"] = "OPEN"
            return sig

        # NO_SIGNAL — mark and skip (no directional outcome to track)
        if sig["direction"] == "NO_SIGNAL":
            sig["outcome"] = "NO_SIGNAL"
            return sig

        ticker = sig["ticker"]
        entry  = sig["entry"]
        stop   = sig["stop"]
        target = sig["target"]

        if not (entry and stop and target):
            sig["outcome"] = "EXPIRED"
            return sig

        # ── Priority 1: Real Alpaca closing fill ──────────────────────────────
        ticker_fills = alpaca_fills.get(ticker, [])
        for o in ticker_fills:
            filled_at = str(o.get("filled_at", ""))[:10]
            try:
                fill_date = date.fromisoformat(filled_at)
            except ValueError:
                continue
            if abs((fill_date - sig_date).days) > 3:
                continue
            fill_px = o.get("filled_price") or o.get("limit_price") or 0
            if not fill_px:
                continue
            fill_px = float(fill_px)
            side    = str(o.get("side", "")).upper()
            # A closing (opposite-direction) fill reveals the outcome
            if sig["direction"] == "BUY" and "SELL" in side:
                pct = (fill_px - entry) / entry * 100
                sig["outcome"]      = "WIN" if fill_px >= target else "LOSS"
                sig["outcome_pct"]  = round(pct, 2)
                sig["outcome_note"] = f"Alpaca fill: {side} @ ${fill_px:.2f}"
                return sig
            elif sig["direction"] == "SELL" and "BUY" in side:
                pct = (entry - fill_px) / entry * 100
                sig["outcome"]      = "WIN" if fill_px <= target else "LOSS"
                sig["outcome_pct"]  = round(pct, 2)
                sig["outcome_note"] = f"Alpaca fill: {side} @ ${fill_px:.2f}"
                return sig

        # ── Priority 2: Bar-by-bar OHLC stop/target check ─────────────────────
        # Walk each daily bar after the signal date in chronological order.
        # The first bar whose Low pierces stop (long) or High pierces stop (short)
        # is a LOSS; the first whose High reaches target (long) or Low reaches
        # target (short) is a WIN.  Checking stop first on each bar is conservative
        # — a gap-down that opens below stop is a loss even if it later recovers.
        df = ohlc_data.get(ticker)
        if df is not None and not df.empty:
            required_cols = {"high", "low", "close"}
            if required_cols.issubset(df.columns):
                sig_dt      = pd.Timestamp(sig_date)
                future_bars = df[df["timestamp"] > sig_dt].sort_values("timestamp")

                for _, bar in future_bars.iterrows():
                    hi = bar.get("high")
                    lo = bar.get("low")
                    if pd.isna(hi) or pd.isna(lo):
                        continue
                    hi, lo   = float(hi), float(lo)
                    bar_date = str(bar["timestamp"].date())

                    if sig["direction"] == "BUY":
                        # Stop checked first — gap-down opens below stop = loss
                        if lo <= stop:
                            pct = (stop - entry) / entry * 100
                            sig.update({
                                "outcome":      "LOSS",
                                "outcome_pct":  round(pct, 2),
                                "outcome_note": (
                                    f"Stop hit {bar_date} "
                                    f"(Low=${lo:.2f} ≤ stop=${stop:.2f})"
                                ),
                            })
                            return sig
                        if hi >= target:
                            pct = (target - entry) / entry * 100
                            sig.update({
                                "outcome":      "WIN",
                                "outcome_pct":  round(pct, 2),
                                "outcome_note": (
                                    f"Target hit {bar_date} "
                                    f"(High=${hi:.2f} ≥ target=${target:.2f})"
                                ),
                            })
                            return sig

                    else:  # SELL / SHORT
                        # Stop checked first — gap-up opens above stop = loss
                        if hi >= stop:
                            pct = (entry - stop) / entry * 100
                            sig.update({
                                "outcome":      "LOSS",
                                "outcome_pct":  round(pct, 2),
                                "outcome_note": (
                                    f"Stop hit {bar_date} "
                                    f"(High=${hi:.2f} ≥ stop=${stop:.2f})"
                                ),
                            })
                            return sig
                        if lo <= target:
                            pct = (entry - target) / entry * 100
                            sig.update({
                                "outcome":      "WIN",
                                "outcome_pct":  round(pct, 2),
                                "outcome_note": (
                                    f"Target hit {bar_date} "
                                    f"(Low=${lo:.2f} ≤ target=${target:.2f})"
                                ),
                            })
                            return sig

                # Neither stop nor target hit in any bar — still open.
                # Show unrealised P&L from the latest available close.
                if not future_bars.empty and "close" in future_bars.columns:
                    current = float(future_bars["close"].iloc[-1])
                    pct = ((current - entry) / entry * 100
                           if sig["direction"] == "BUY"
                           else (entry - current) / entry * 100)
                    sig.update({
                        "outcome":      "OPEN",
                        "outcome_pct":  round(pct, 2),
                        "outcome_note": (
                            f"No stop/target hit yet; "
                            f"current=${current:.2f} ({pct:+.1f}%)"
                        ),
                    })
                else:
                    sig["outcome"] = "OPEN"
                return sig

        # ── Priority 3: No usable OHLC data ───────────────────────────────────
        sig["outcome"] = "UNKNOWN"
        return sig

    # ── Ledger ────────────────────────────────────────────────────────────────

    def _load_ledger(self) -> dict:
        ledger_path = Path(self.vault.root) / "09-Portfolio" / "signal_ledger.json"
        if ledger_path.exists():
            try:
                return json.loads(ledger_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"signals": [], "last_updated": ""}

    def _save_ledger(self, ledger: dict):
        ledger_path = Path(self.vault.root) / "09-Portfolio" / "signal_ledger.json"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger["last_updated"] = datetime.now().isoformat()
        ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    def _merge_signals_into_ledger(self, ledger: dict, signals: list[dict]) -> dict:
        """
        Upsert today's resolved signals into the ledger.
        Key = date + ticker + direction (one entry per unique signal).
        """
        existing_keys = {
            (s["date"], s["ticker"], s["direction"])
            for s in ledger["signals"]
        }
        updated = 0
        added   = 0

        # Update outcomes of existing entries
        for i, existing in enumerate(ledger["signals"]):
            key = (existing["date"], existing["ticker"], existing["direction"])
            for new_sig in signals:
                if (new_sig["date"], new_sig["ticker"], new_sig["direction"]) == key:
                    if new_sig["outcome"] not in ("OPEN", "UNKNOWN"):
                        ledger["signals"][i]["outcome"]      = new_sig["outcome"]
                        ledger["signals"][i]["outcome_pct"]  = new_sig["outcome_pct"]
                        ledger["signals"][i]["outcome_note"] = new_sig["outcome_note"]
                        updated += 1

        # Add new entries not yet in ledger
        for sig in signals:
            key = (sig["date"], sig["ticker"], sig["direction"])
            if key not in existing_keys:
                ledger["signals"].append(sig)
                existing_keys.add(key)
                added += 1

        print(f"   Ledger: {added} new signals added, {updated} outcomes updated, "
              f"{len(ledger['signals'])} total")
        return ledger

    # ── Summary stats ─────────────────────────────────────────────────────────

    def _build_stats_block(self, ledger: dict) -> str:
        """
        Compute win-rate statistics from the ledger and format as a
        structured prompt block for the LLM pattern-extraction call.
        """
        resolved = [s for s in ledger["signals"]
                    if s["direction"] in ("BUY", "SELL")
                    and s["outcome"] in ("WIN", "LOSS")]

        if not resolved:
            return "No resolved signal outcomes available yet."

        total = len(resolved)
        wins  = sum(1 for s in resolved if s["outcome"] == "WIN")
        losses = total - wins
        avg_win  = (sum(s["outcome_pct"] for s in resolved if s["outcome"] == "WIN" and s["outcome_pct"])
                    / max(wins, 1))
        avg_loss = (sum(s["outcome_pct"] for s in resolved if s["outcome"] == "LOSS" and s["outcome_pct"])
                    / max(losses, 1))

        lines = [
            f"## Overall Signal Performance",
            f"Total resolved signals: {total}",
            f"Wins: {wins} ({wins/total*100:.0f}%)  |  Losses: {losses} ({losses/total*100:.0f}%)",
            f"Avg win: +{avg_win:.1f}%  |  Avg loss: {avg_loss:.1f}%",
            f"Expected value per signal: {(wins/total * avg_win + losses/total * avg_loss):.2f}%",
            "",
            "## Resolved Signals (newest first)",
        ]

        for s in sorted(resolved, key=lambda x: x["date"], reverse=True)[:40]:
            pct_str = f"{s['outcome_pct']:+.1f}%" if s["outcome_pct"] is not None else "?"
            conf    = s.get("confidence", 0)
            lines.append(
                f"- {s['date']} {s['ticker']} {s['direction']} "
                f"conf={conf}% → **{s['outcome']}** {pct_str} | {s.get('outcome_note','')}"
            )
            if s.get("rationale"):
                lines.append(f"  Rationale: {s['rationale'][:120]}")

        # Ticker breakdown
        lines.append("\n## Win Rate by Ticker")
        ticker_stats: dict[str, dict] = {}
        for s in resolved:
            t = s["ticker"]
            ticker_stats.setdefault(t, {"wins": 0, "total": 0})
            ticker_stats[t]["total"] += 1
            if s["outcome"] == "WIN":
                ticker_stats[t]["wins"] += 1
        for ticker, ts in sorted(ticker_stats.items()):
            wr = ts["wins"] / ts["total"] * 100
            lines.append(f"  {ticker}: {ts['wins']}/{ts['total']} ({wr:.0f}% win rate)")

        # Confidence-bucket breakdown
        lines.append("\n## Win Rate by Confidence Bucket")
        buckets: dict[str, dict] = {"<65%": {"w":0,"t":0}, "65-74%": {"w":0,"t":0},
                                     "75-84%": {"w":0,"t":0}, "≥85%": {"w":0,"t":0}}
        for s in resolved:
            c = s.get("confidence", 0)
            key = ("<65%" if c < 65 else "65-74%" if c < 75
                   else "75-84%" if c < 85 else "≥85%")
            buckets[key]["t"] += 1
            if s["outcome"] == "WIN":
                buckets[key]["w"] += 1
        for bucket, bs in buckets.items():
            if bs["t"] > 0:
                wr = bs["w"] / bs["t"] * 100
                lines.append(f"  Conf {bucket}: {bs['w']}/{bs['t']} ({wr:.0f}% win rate)")

        return "\n".join(lines)

    # ── Main entry ────────────────────────────────────────────────────────────

    def track_outcomes(self):
        today = datetime.now().strftime("%Y-%m-%d")
        print("   OutcomeTracker: loading historical signals …")
        all_signals = self._load_all_signals()
        if not all_signals:
            print("   OutcomeTracker: no historical signals found — skipping")
            return

        print(f"   OutcomeTracker: {len(all_signals)} signals loaded from vault")

        # Resolve outcomes — load OHLC once for all unique tickers, then walk
        # each signal bar-by-bar to find the first stop/target hit.
        unique_tickers = list({s["ticker"] for s in all_signals})
        print(f"   OutcomeTracker: loading OHLC for {unique_tickers}")
        ohlc_data    = self._load_ohlc_data(unique_tickers)
        alpaca_fills = self._load_alpaca_fills()

        resolved_signals = [
            self._resolve_signal(s, ohlc_data, alpaca_fills)
            for s in all_signals
        ]

        wins   = sum(1 for s in resolved_signals if s["outcome"] == "WIN")
        losses = sum(1 for s in resolved_signals if s["outcome"] == "LOSS")
        open_  = sum(1 for s in resolved_signals if s["outcome"] == "OPEN")
        nosig  = sum(1 for s in resolved_signals if s["outcome"] == "NO_SIGNAL")
        print(f"   Outcomes: {wins} WIN · {losses} LOSS · {open_} OPEN "
              f"· {nosig} NO_SIGNAL")

        # Update ledger
        ledger = self._load_ledger()
        ledger = self._merge_signals_into_ledger(ledger, resolved_signals)
        self._save_ledger(ledger)

        # Build stats block for LLM
        stats_block = self._build_stats_block(ledger)

        # LLM pattern extraction — this is the actual learning output
        self.think_and_write(
            f"Analyse the following trading signal outcome history and extract "
            f"concrete, quantified patterns that will improve future signal quality.\n\n"
            f"{stats_block}\n\n"
            f"Focus especially on:\n"
            f"- Which RSI levels, MACD states, and BB positions correlate with wins vs losses\n"
            f"- Whether high-confidence signals (≥75%) actually outperform lower-confidence ones\n"
            f"- Which tickers the system reads best vs worst\n"
            f"- Rule updates SignalGenerator and RiskGuardian should apply tomorrow",
            "08-Logs",
            f"OUTCOMES_{today}.md",
        )
        print(f"   ✅ OutcomeTracker: lessons written to vault/08-Logs/OUTCOMES_{today}.md")
        print(f"   ✅ OutcomeTracker: ledger updated "
              f"({len(ledger['signals'])} total signals tracked)")
