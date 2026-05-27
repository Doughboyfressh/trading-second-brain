# src/agents/risk_guardian.py
from src.agents.base import BaseAgent
from src.alpaca_broker import AlpacaBroker
from src.data_fetcher import DataFetcher
from src.historical_loader import load_performance_stats
from src.llm import TradingLLM
from datetime import datetime
from pathlib import Path
import json, re, requests, os

class RiskGuardian(BaseAgent):
    EARNINGS_WINDOW_DAYS = 5    # auto-reject tickers with earnings within this window
    PF_HARD_BLOCK        = 0.35  # Gate 6: block strategies with PF below this threshold
    PF_WARN_THRESHOLD    = 0.55  # Gate 6: warn (require higher confidence) below this
    MAX_SECTOR_POSITIONS = 3    # Gate 7: require conf ≥ 80% beyond this many open positions per sector

    # Sector mapping for Gate 7 concentration check.
    # Extend this dict as the watchlist grows — unknown tickers are skipped (Gate 7 N/A).
    _SECTOR_MAP: dict[str, str] = {
        # Default watchlist
        "AAPL": "Technology",        "MSFT": "Technology",
        "GOOGL": "Technology",       "META": "Technology",
        "NVDA": "Technology",        "AMD":  "Technology",
        "AMZN": "Technology",        "TSLA": "Consumer Cyclical",
        # Common additions — Technology
        "NFLX": "Technology",        "CRM":  "Technology",
        "ORCL": "Technology",        "INTC": "Technology",
        "QCOM": "Technology",        "MU":   "Technology",
        "PLTR": "Technology",        "COIN": "Technology",
        "UBER": "Technology",        "SNAP": "Technology",
        # Financials
        "JPM":  "Financials",        "GS":   "Financials",
        "BAC":  "Financials",        "MS":   "Financials",
        # Energy
        "XOM":  "Energy",            "CVX":  "Energy",
        "XLE":  "Energy",
        # Healthcare
        "JNJ":  "Healthcare",        "PFE":  "Healthcare",
        "XLV":  "Healthcare",
        # ETFs / macro
        "SPY":  "Index",             "QQQ":  "Index",
        "IWM":  "Index",             "DIA":  "Index",
        "GLD":  "Commodity",         "SLV":  "Commodity",
        "TLT":  "Bonds",             "HYG":  "Bonds",
    }

    def __init__(self):
        super().__init__(
            "RiskGuardian",
            "You are RiskGuardian — the final gatekeeper before any trade reaches execution.\n\n"
            "## CRITICAL RULE: Use the exact values from the signal. Do NOT re-grade confidence.\n\n"
            "## Approval Gates (ALL 7 must pass):\n"
            "  Gate 1 — CONFIDENCE ≥ 65%: use the exact % stated in the signal.\n"
            "  Gate 2 — R:R ≥ 1:2: calculate as (TARGET-ENTRY)/(ENTRY-STOP). Must be ≥ 2.0.\n"
            "  Gate 3 — REGIME: direction matches current market regime (Bull=long OK, Bear=short only).\n"
            "  Gate 4 — POSITION SIZE: dollar risk per trade ≤ 1% of the account equity provided.\n"
            "    Formula: qty = (equity × 0.01) / |entry − stop|. Verify the signal's implied size.\n"
            "  Gate 5 — EARNINGS SAFE: REJECT any ticker flagged ⚠️ EARNINGS WITHIN 5 DAYS "
            "unless confidence ≥ 80% AND R:R ≥ 1:3 (binary event — most edges collapse).\n"
            "  Gate 6 — STRATEGY EDGE: Check the HISTORICAL PERFORMANCE REFERENCE block.\n"
            "    - PF < 0.35 → HARD BLOCK: REJECT regardless of other gates. "
            "Strategy has destroyed capital in backtests with no recoverable edge.\n"
            "    - PF 0.35–0.55 → require confidence ≥ 75% AND R:R ≥ 1:2.5 to compensate.\n"
            "    - PF ≥ 0.85 → near profitable edge; standard gates apply.\n"
            "    - If no historical data available, skip Gate 6 (N/A).\n"
            "  Gate 7 — SECTOR CONCENTRATION: Check the PORTFOLIO CONCENTRATION block.\n"
            "    The default watchlist is 7/8 technology stocks — concentrated sector risk.\n"
            "    If approving this signal would make it the 4th+ open position in the same\n"
            "    sector, require confidence ≥ 80% AND R:R ≥ 1:2.5 to compensate for the\n"
            "    correlated drawdown risk.\n"
            "    If no position data is available (first run / positions.json absent): N/A.\n\n"
            "## Output format for EVERY ticker:\n"
            "### TICKER\n"
            "- Confidence: <exact % from signal> → PASS / FAIL\n"
            "- R:R: <number> → PASS / FAIL\n"
            "- Regime: PASS / FAIL\n"
            "- Position Size: PASS / FAIL\n"
            "- Earnings Safe: PASS / FAIL / N/A\n"
            "- Strategy Edge (PF=X.XX, WinRate=X%): PASS / WARN / FAIL\n"
            "- Sector Concentration (<sector>, position #N of max 3): PASS / WARN / N/A\n"
            "VERDICT: APPROVE\n"
            "or\n"
            "VERDICT: REJECT — <which gate(s) failed>\n\n"
            "Tickers with DIRECTION: NO SIGNAL get VERDICT: REJECT automatically.\n"
            "Review every ticker. Output VERDICT: APPROVE clearly when all 7 gates pass.",
            model=TradingLLM.SONNET,
            max_tokens=2200,
            rag_top_k=2,
            temperature=0.0,    # gate pass/fail must be fully deterministic
        )
        self.fetcher = DataFetcher()
        self.broker  = AlpacaBroker()
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id        = os.getenv("TELEGRAM_CHAT_ID")

    def _earnings_block(self, tickers: list) -> str:
        """
        Return a formatted earnings-warning block for the sweep prompt (Gate 5).

        Uses the shared earnings cache (src/earnings_cache.py) — the orchestrator
        pre-warms it for all watchlist tickers in Phase 1a so this is a disk read,
        not a network call.  Falls back to live fetch for any cache miss.
        """
        from src.earnings_cache import get_upcoming_flags
        flags = get_upcoming_flags(
            tickers,
            str(self.vault.root),
            window_days=self.EARNINGS_WINDOW_DAYS,
        )
        if not flags:
            return ""
        warnings = [
            f"  ⚠️  {t}: EARNINGS {d} — apply Gate 5 strictly"
            for t, d in sorted(flags.items())
        ]
        return "\n\nEARNINGS WARNINGS (Gate 5):\n" + "\n".join(warnings)

    def send_telegram(self, message: str):
        if self.telegram_token and self.chat_id:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"},
                    timeout=5,
                )
                print("📲 Telegram alert sent")
            except Exception:
                pass

    def _load_latest_signals(self) -> str:
        """Read the most recent signals file directly from disk — no RAG delay."""
        journal_dir = Path(self.vault.root) / "03-Trade-Journal"
        files = sorted(journal_dir.glob("signals_*.md"), reverse=True)
        if not files:
            return ""
        return files[0].read_text(encoding="utf-8", errors="replace")

    def _build_perf_gate_block(self, tickers: list) -> str:
        """
        Build a Gate 6 reference block from performance_stats.json.
        Shows win/loss counts and PF for each ticker's best historical strategy.
        Hard-blocks (PF < 0.35) are flagged for automatic rejection.
        """
        stats = load_performance_stats()
        if not stats:
            return ""

        by_ticker = stats.get("by_ticker", {})
        lines = [
            "\n\nHISTORICAL PERFORMANCE REFERENCE (Gate 6 — Strategy Edge Check):",
            "PF = Profit Factor (> 1.0 = profitable, < 0.35 = HARD BLOCK).",
            f"{'Ticker':<7} {'Best Strategy':<22} {'Wins':<6} {'Losses':<8} "
            f"{'Win%':<7} {'PF':<7} {'Expect/trade':<14} {'Gate 6 Status'}",
            "-" * 90,
        ]
        hard_blocks = []
        for ticker in tickers:
            bt = by_ticker.get(ticker, {})
            if not bt or not bt.get("best_strategy"):
                lines.append(f"  {ticker:<7} No training data — Gate 6: N/A")
                continue
            strat  = bt["best_strategy"]
            wins   = bt.get("best_wins", 0)
            losses = bt.get("best_losses", 0)
            wr     = bt.get("best_win_rate", 0)
            pf     = bt.get("best_profit_factor", 0)
            exp    = bt.get("best_expectancy_pct", 0)
            if pf < self.PF_HARD_BLOCK:
                status = f"HARD BLOCK (PF={pf:.3f} < {self.PF_HARD_BLOCK})"
                hard_blocks.append(ticker)
            elif pf < self.PF_WARN_THRESHOLD:
                status = f"WARN — require conf≥75% AND R:R≥1:2.5 (PF={pf:.3f})"
            else:
                status = f"PASS (PF={pf:.3f})"
            lines.append(
                f"  {ticker:<7} {strat:<22} {wins:<6} {losses:<8} "
                f"{wr:.1f}%  {pf:<7.3f} {exp:+.3f}%        {status}"
            )
        if hard_blocks:
            lines.append("")
            lines.append(
                f"  *** HARD BLOCK tickers (Gate 6 automatic REJECT): {hard_blocks} ***"
            )
            lines.append(
                f"  These strategies historically destroyed 100% of capital in "
                f"walk-forward backtests. No signal edge survives."
            )
        return "\n".join(lines)

    def _build_concentration_block(self, tickers_in_signals: list[str]) -> str:
        """
        Gate 7 — sector concentration check.

        Loads current open positions from vault/09-Portfolio/positions.json
        (written by PnLTracker at the end of each prior run) and counts how
        many open positions already exist per sector.

        For each ticker in today's signals, flags if approval would push the
        sector count past MAX_SECTOR_POSITIONS.  The LLM uses this to decide
        whether to apply the higher confidence/R:R requirement.

        Returns an empty string when positions.json doesn't exist yet (first
        run) so Gate 7 is automatically N/A on day one.
        """
        # ── Load current open positions ───────────────────────────────────────
        snapshot_path = Path(self.vault.root) / "09-Portfolio" / "positions.json"
        current_symbols: list[str] = []
        if snapshot_path.exists():
            try:
                snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
                current_symbols = [
                    p["symbol"] for p in snap.get("positions", [])
                    if float(p.get("qty", 0)) != 0
                ]
            except Exception as e:
                print(f"   RiskGuardian: could not load positions snapshot ({e})")

        if not current_symbols and not snapshot_path.exists():
            return "\n\nPORTFOLIO CONCENTRATION (Gate 7): N/A — no positions.json yet (first run)."

        # ── Count sectors for open positions ──────────────────────────────────
        sector_positions: dict[str, list[str]] = {}
        for sym in current_symbols:
            sector = self._SECTOR_MAP.get(sym)
            if sector:
                sector_positions.setdefault(sector, []).append(sym)

        lines = ["\n\nPORTFOLIO CONCENTRATION (Gate 7):"]
        if current_symbols:
            summary = ", ".join(
                f"{sym}({self._SECTOR_MAP.get(sym, '?')})"
                for sym in current_symbols
            )
            lines.append(f"  Current open positions: {summary}")
            for sector, syms in sorted(sector_positions.items()):
                bar = "⚠️ " if len(syms) >= self.MAX_SECTOR_POSITIONS else "  "
                lines.append(
                    f"  {bar}{sector}: {len(syms)} open — {', '.join(syms)}"
                    + (" (AT LIMIT)" if len(syms) >= self.MAX_SECTOR_POSITIONS else "")
                )
        else:
            lines.append("  No open positions currently.")

        # ── Flag signals that would breach the sector limit ───────────────────
        warnings: list[str] = []
        for ticker in tickers_in_signals:
            sector = self._SECTOR_MAP.get(ticker)
            if sector is None:
                continue  # unknown ticker — Gate 7 N/A for this one
            existing_count = len(sector_positions.get(sector, []))
            if ticker in current_symbols:
                continue  # already in position — not a new addition
            if existing_count >= self.MAX_SECTOR_POSITIONS:
                warnings.append(
                    f"  ⚠️  {ticker} ({sector}): would be position "
                    f"#{existing_count + 1} in {sector} "
                    f"(limit={self.MAX_SECTOR_POSITIONS}) — "
                    f"Gate 7: require conf ≥ 80% AND R:R ≥ 1:2.5"
                )

        if warnings:
            lines.append("\nGate 7 concentration warnings:")
            lines.extend(warnings)
        else:
            lines.append(
                f"\n  Gate 7: all signals within {self.MAX_SECTOR_POSITIONS}-position "
                f"sector limit — PASS."
            )

        return "\n".join(lines)

    def daily_risk_sweep(self):
        # Read signals file directly (avoids RAG staleness on freshly-written files)
        signals_content = self._load_latest_signals()
        if not signals_content:
            print("   RiskGuardian: no signals file found")
            return

        # Extract tickers mentioned in the signals file (re imported at module level)
        tickers_in_signals = re.findall(r'###\s+([A-Z]{1,5})\b', signals_content)
        tickers_in_signals = list(dict.fromkeys(tickers_in_signals))  # deduplicate, preserve order

        earnings_warnings = ""
        if tickers_in_signals:
            print(f"   RiskGuardian: checking earnings for {tickers_in_signals}")
            earnings_warnings = self._earnings_block(tickers_in_signals)
            if earnings_warnings:
                print(f"   ⚠️  Earnings flags added to sweep prompt")

        # ── Fetch real account equity for Gate 4 position-size verification ────
        equity_block = ""
        try:
            account = self.broker.get_account()
            equity  = account["equity"]
            max_risk_per_trade = equity * 0.01
            equity_block = (
                f"\nACCOUNT EQUITY: ${equity:,.2f}  "
                f"(1% risk cap = ${max_risk_per_trade:,.2f} per trade)\n"
                f"Gate 4 formula: qty × |entry − stop| must be ≤ ${max_risk_per_trade:,.2f}\n"
            )
            print(f"   RiskGuardian: account equity = ${equity:,.2f} "
                  f"(max risk/trade = ${max_risk_per_trade:,.2f})")
        except Exception as e:
            print(f"   ⚠️  RiskGuardian: could not fetch account equity ({e}) — Gate 4 unverifiable")

        # Gate 6 — historical strategy performance reference
        perf_gate_block = self._build_perf_gate_block(tickers_in_signals)
        if perf_gate_block:
            print("   RiskGuardian: Gate 6 performance reference loaded")

        # Gate 7 — sector concentration check
        concentration_block = self._build_concentration_block(tickers_in_signals)
        print("   RiskGuardian: Gate 7 sector concentration block built")

        task = (
            "Apply ALL 7 approval gates to every ticker below.\n"
            "Use the EXACT confidence % and price levels stated — do not re-estimate.\n"
            "Output VERDICT: APPROVE for every ticker where all 7 gates pass.\n"
            + equity_block
            + earnings_warnings
            + perf_gate_block
            + concentration_block
            + "\n\n=== SIGNALS TO REVIEW ===\n\n"
            + signals_content
        )

        response = self.think_and_write(
            task,
            "06-Playbooks",
            f"RISK_SWEEP_{datetime.now().strftime('%Y%m%d')}.md",
        )
        self.send_telegram(f"🛡️ *Daily Risk Sweep*\n{response[:400]}…\n_Full report in vault_")
        print("✅ Risk sweep completed")
