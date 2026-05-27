# src/agents/execution_agent.py
"""
ExecutionAgent — reads RiskGuardian-approved signals, routes them to Alpaca paper,
saves execution logs to the vault, and fires Telegram trade alerts.

Two-file approach (robust against LLM formatting variation):
  1. Parse vault/03-Trade-Journal/signals_*.md  → price levels per ticker
  2. Parse vault/06-Playbooks/RISK_SWEEP_*.md   → APPROVE/REJECT per ticker
  3. Intersect: execute only tickers that are APPROVED and have valid prices

Circuit breaker: if account equity has dropped >CIRCUIT_BREAKER_DRAWDOWN_PCT
(default 10%) from the last saved portfolio snapshot, no new orders are placed.
"""
import json
import re
import os
from pathlib import Path
from datetime import datetime

import requests

from src.agents.base   import BaseAgent
from src.alpaca_broker import AlpacaBroker
from src.llm           import TradingLLM
from src.vault_manager import VaultManager
from config            import CIRCUIT_BREAKER_DRAWDOWN_PCT


class ExecutionAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "ExecutionAgent",
            "You are ExecutionAgent. Summarise the paper trades just placed in 2-3 sentences: "
            "list each ticker, direction, quantity, entry/stop/target prices, and dollar risk. "
            "If no trades were placed, explain why (no approved signals / already in position / "
            "market closed). Keep it factual and concise.",
            model=TradingLLM.HAIKU,
            max_tokens=500,
            rag_top_k=0,
            temperature=0.0,    # summarising real fill data — no creativity needed
        )
        self.broker         = AlpacaBroker()
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id        = os.getenv("TELEGRAM_CHAT_ID")

    # ── Telegram ─────────────────────────────────────────────────────────────
    def _telegram(self, msg: str):
        if not (self.telegram_token and self.chat_id):
            return
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                json={"chat_id": self.chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=5,
            )
            if resp.status_code == 200:
                print("   📲 Telegram alert sent")
            else:
                print(f"   ⚠️  Telegram HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            print(f"   ⚠️  Telegram failed: {e}")

    # ── File loaders ─────────────────────────────────────────────────────────
    def _load_latest(self, folder: str, glob_pattern: str) -> tuple[str, str]:
        """
        Return (text, filename) for the most recent file matching glob_pattern
        in vault/<folder>/.

        Uses explicit folder/glob rather than rglob with a path-separator in the
        pattern, which is non-standard across platforms.
        """
        folder_path = Path(self.vault.root) / folder
        files = sorted(folder_path.glob(glob_pattern), reverse=True)
        if not files:
            return "", ""
        f = files[0]
        return f.read_text(encoding="utf-8", errors="replace"), f.name

    # ── Circuit breaker ───────────────────────────────────────────────────────
    def _circuit_breaker_tripped(self, current_equity: float) -> bool:
        """
        Return True (and fire a Telegram alert) if account equity has dropped
        more than CIRCUIT_BREAKER_DRAWDOWN_PCT below the last saved portfolio
        snapshot.  This halts new entries during significant drawdowns without
        requiring manual intervention.

        Baseline = equity from vault/09-Portfolio/positions.json (written by
        PnLTracker at the end of each prior run).  Returns False if no snapshot
        exists yet (first run — allow trading).
        """
        snapshot_path = Path(self.vault.root) / "09-Portfolio" / "positions.json"
        if not snapshot_path.exists():
            return False   # no baseline yet — allow trading
        try:
            snap     = json.loads(snapshot_path.read_text(encoding="utf-8"))
            baseline = float(snap.get("account", {}).get("equity", 0))
            if baseline <= 0:
                return False
            drawdown = (current_equity - baseline) / baseline
            if drawdown < -CIRCUIT_BREAKER_DRAWDOWN_PCT:
                msg = (
                    f"🚨 *Circuit Breaker Tripped*\n"
                    f"Equity `${current_equity:,.0f}` is "
                    f"`{drawdown:.1%}` below baseline `${baseline:,.0f}`\n"
                    f"Threshold: `{CIRCUIT_BREAKER_DRAWDOWN_PCT:.0%}` — no new trades today."
                )
                print(f"   🚨 CIRCUIT BREAKER: equity ${current_equity:,.0f} is "
                      f"{drawdown:.1%} below last snapshot ${baseline:,.0f} "
                      f"(threshold {CIRCUIT_BREAKER_DRAWDOWN_PCT:.0%}) — halting")
                self._telegram(msg)
                return True
        except Exception as e:
            print(f"   ⚠️  Circuit breaker check failed: {e}")
        return False

    # ── Step 1: Parse signals file for price levels ───────────────────────────
    def _parse_signal_prices(self, text: str) -> dict[str, dict]:
        """
        Read vault/03-Trade-Journal/signals_*.md and extract per-ticker:
          direction, entry, stop, target
        Only returns tickers with direction BUY or SELL (not NO SIGNAL).
        """
        prices: dict[str, dict] = {}
        blocks = re.split(r'###\s+', text)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            ticker_m = re.match(r'([A-Z]{1,5})\b', block)
            if not ticker_m:
                continue
            ticker = ticker_m.group(1).upper()
            if ticker in {"SIGNAL", "REPORT", "SUMMARY", "NOTE", "TRADE"}:
                continue

            # Direction must be BUY or SELL
            # Allow for LLM markdown bold: "DIRECTION: **BUY**" or "DIRECTION: BUY"
            dir_m = re.search(
                r'DIRECTION\s*[:\-]\s*[\*\s]*(BUY|SELL|LONG|SHORT|NO\s*SIGNAL)',
                block, re.IGNORECASE
            )
            if not dir_m:
                continue
            raw_dir = dir_m.group(1).upper().replace(" ", "")
            if raw_dir in ("NOSIGNAL", "NO"):
                continue
            direction = "BUY" if raw_dir in ("BUY", "LONG") else "SELL"

            def _price(pat: str) -> float | None:
                m = re.search(pat, block, re.IGNORECASE)
                if not m:
                    return None
                try:
                    # Strip any markdown or parenthetical text after the number
                    raw = m.group(1).replace(",", "").replace("$", "").strip()
                    return float(raw)
                except (ValueError, TypeError):
                    return None

            # Patterns are intentionally permissive — match first number on the line,
            # which handles:  "$215.33", "$215.33 *(note)*", "**$215.33**"
            entry  = _price(r'ENTRY\s*[:\-]\s*[\*\s]*\$?([\d,]+\.?\d*)')
            stop   = _price(r'STOP\s*[:\-]\s*[\*\s]*\$?([\d,]+\.?\d*)')
            target = _price(r'TARGET\s*[:\-]\s*[\*\s]*\$?([\d,]+\.?\d*)')

            if not (entry and stop and target):
                continue

            # Sanity-check price order
            if direction == "BUY"  and not (stop < entry < target):
                continue
            if direction == "SELL" and not (target < entry < stop):
                continue

            prices[ticker] = {
                "ticker":    ticker,
                "direction": direction,
                "entry":     entry,
                "stop":      stop,
                "target":    target,
            }

        return prices

    # ── Step 2: Parse risk sweep for approved tickers ─────────────────────────
    def _parse_approved_tickers(self, text: str) -> set[str]:
        """
        Read vault/06-Playbooks/RISK_SWEEP_*.md and return the set of tickers
        whose VERDICT contains APPROVE (handles table, colon, pipe, emoji formats).
        """
        approved: set[str] = set()
        blocks = re.split(r'###\s+', text)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Broad VERDICT APPROVE match — handles all RiskGuardian output styles:
            #   "VERDICT: APPROVE", "**VERDICT** | ✅ APPROVE", "VERDICT — APPROVE", etc.
            if not re.search(r'VERDICT.{0,30}APPROVE', block, re.IGNORECASE):
                continue

            ticker_m = re.match(r'([A-Z]{1,5})\b', block)
            if not ticker_m:
                continue
            ticker = ticker_m.group(1).upper()
            if ticker in {"SIGNAL", "REPORT", "SUMMARY", "NOTE", "FINAL", "DAILY"}:
                continue

            approved.add(ticker)
            print(f"   ✅ RiskGuardian APPROVED: {ticker}")

        return approved

    # ── Main execution method ─────────────────────────────────────────────────
    def execute_approved_signals(self) -> list[dict]:
        """
        Full cycle: load signals + sweep → intersect → size → circuit-breaker
        check → place → log → alert.  Returns list of placed order dicts.
        """
        # 1. Load signals file (price levels)
        sig_text, sig_file = self._load_latest("03-Trade-Journal", "signals_*.md")
        if not sig_text:
            print("   No signals file found — nothing to execute")
            self._save_execution_log([], "No signals file found.")
            return []
        print(f"   Signals file:  {sig_file}")

        # 2. Load risk sweep (approve/reject)
        sweep_text, sweep_file = self._load_latest("06-Playbooks", "RISK_SWEEP_*.md")
        if not sweep_text:
            print("   No RISK_SWEEP file found — nothing to execute")
            self._save_execution_log([], "No risk sweep file found.")
            return []
        print(f"   Risk sweep:    {sweep_file}")

        # 3. Parse both files
        signal_prices    = self._parse_signal_prices(sig_text)
        approved_tickers = self._parse_approved_tickers(sweep_text)

        print(f"   Signals with prices: {list(signal_prices.keys())}")
        print(f"   Approved tickers:    {sorted(approved_tickers)}")

        # 4. Intersect — only execute what is BOTH priced AND approved
        to_execute = [
            signal_prices[t] for t in approved_tickers
            if t in signal_prices
        ]

        if not to_execute:
            print("   No overlap between approved tickers and priced signals — nothing to execute")
            for t in approved_tickers:
                if t not in signal_prices:
                    print(f"   ℹ️  {t} was approved but has no price levels in signals file")
            self._save_execution_log([], "No approved signals with valid price levels today.")
            return []

        # 5. Fetch account info
        try:
            account = self.broker.get_account()
            equity  = account["equity"]
            print(f"   Paper equity: ${equity:,.2f}")
        except Exception as e:
            print(f"   ❌ Could not fetch account: {e}")
            self._save_execution_log([], f"Account fetch failed: {e}")
            return []

        # 6. Circuit breaker — halt if drawdown exceeds threshold
        if self._circuit_breaker_tripped(equity):
            self._save_execution_log([], "Circuit breaker tripped — no new entries today.")
            return []

        # 7. Market status
        hours    = self.broker.market_hours()
        mkt_note = ("🟢 Market OPEN" if hours["is_open"]
                    else f"🔴 Market CLOSED — orders queue for {hours['next_open']}")
        print(f"   {mkt_note}")

        placed_orders: list[dict] = []
        skipped_notes: list[str]  = []

        for sig in to_execute:
            ticker    = sig["ticker"]
            direction = sig["direction"]
            entry     = sig["entry"]
            stop      = sig["stop"]
            target    = sig["target"]

            # Skip if already in position
            if self.broker.has_position(ticker):
                note = f"{ticker}: position already open — skipping"
                print(f"   ⏭  {note}")
                skipped_notes.append(note)
                continue

            # Size position (1% equity risk)
            qty         = self.broker.compute_position_size(equity, entry, stop)
            dollar_risk = qty * abs(entry - stop)
            rr          = abs(target - entry) / max(abs(entry - stop), 0.01)
            print(f"   📐 {ticker} {direction} × {qty} | "
                  f"entry=${entry:.2f}  stop=${stop:.2f}  target=${target:.2f} | "
                  f"risk=${dollar_risk:.2f}  R:R={rr:.1f}:1")

            # Place bracket order
            try:
                order = self.broker.place_bracket_order(
                    symbol=ticker, side=direction, qty=qty,
                    limit_price=entry, stop_price=stop,
                    take_profit_price=target,
                )
                order.update({
                    "entry":       entry,
                    "stop":        stop,
                    "target":      target,
                    "dollar_risk": dollar_risk,
                    "rr":          round(rr, 2),
                })
                placed_orders.append(order)
                print(f"   ✅ {ticker} {direction} × {qty} @ ${entry:.2f} "
                      f"[stop=${stop:.2f}  target=${target:.2f}] — {order['status']}")

                self._telegram(
                    f"🚀 *Paper Trade Placed*\n"
                    f"*{ticker}* {direction} × {qty} shares\n"
                    f"Entry: `${entry:.2f}` | Stop: `${stop:.2f}` | Target: `${target:.2f}`\n"
                    f"R:R `{rr:.1f}:1` | Risk: `${dollar_risk:.2f}` | "
                    f"Equity: `${equity:,.0f}`\n_{mkt_note}_"
                )

            except Exception as e:
                note = f"{ticker}: order failed — {e}"
                print(f"   ❌ {note}")
                skipped_notes.append(note)

        # Summary Telegram
        if placed_orders:
            tickers_placed = ", ".join(o["symbol"] for o in placed_orders)
            self._telegram(
                f"📋 *Execution Summary*\n"
                f"{len(placed_orders)} order(s): {tickers_placed}\n"
                f"Capital deployed: "
                f"`${sum(o['qty']*o['entry'] for o in placed_orders):,.0f}`\n"
                f"Total at risk: `${sum(o['dollar_risk'] for o in placed_orders):,.2f}`"
            )

        self._save_execution_log(placed_orders, "\n".join(skipped_notes))
        return placed_orders

    # ── Save execution log ───────────────────────────────────────────────────
    def _save_execution_log(self, orders: list[dict], skipped_notes: str = ""):
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"# Execution Log — {today}\n\n"]

        if orders:
            total_risk    = sum(o.get("dollar_risk", 0) for o in orders)
            total_capital = sum(o.get("qty", 0) * o.get("entry", 0) for o in orders)
            lines.append(
                f"**{len(orders)} bracket order(s) placed**\n"
                f"Capital deployed: ${total_capital:,.0f} | "
                f"Total at risk: ${total_risk:,.2f}\n\n"
            )
            for o in orders:
                sym = o.get("symbol", o.get("ticker", "?"))
                lines.append(
                    f"## {sym} {str(o.get('side','')).upper()}\n"
                    f"- **Qty**: {int(o.get('qty', 0))} shares\n"
                    f"- **Entry (limit)**: ${o.get('entry', 0):.2f}\n"
                    f"- **Stop-loss**: ${o.get('stop', 0):.2f}\n"
                    f"- **Take-profit**: ${o.get('target', 0):.2f}\n"
                    f"- **R:R**: {o.get('rr', 0):.1f}:1\n"
                    f"- **Dollar Risk**: ${o.get('dollar_risk', 0):.2f}\n"
                    f"- **Order ID**: `{o.get('id', 'N/A')}`\n"
                    f"- **Status**: {o.get('status', 'submitted')}\n\n"
                )
        else:
            lines.append("**No orders placed today.**\n\n")

        if skipped_notes and skipped_notes.strip():
            lines.append(f"## Skipped / Errors\n{skipped_notes}\n")

        vm = VaultManager()
        vm.write_note(
            "03-Trade-Journal",
            f"EXECUTED_{today.replace('-', '')}.md",
            "".join(lines),
        )
        print(f"   📝 Execution log saved: EXECUTED_{today.replace('-', '')}.md")
