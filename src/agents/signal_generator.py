# src/agents/signal_generator.py
"""
SignalGenerator — high-conviction signal engine.
Injects real computed indicators (RSI/MACD/BB/ATR) from saved CSVs
so the LLM doesn't have to guess price levels.

Earnings filter: if a ticker has earnings within 5 days, the signal
prompt flags it with a ⚠️ WARNING — the LLM is instructed to reject
or heavily downsize to avoid binary earnings risk.
"""
import pandas as pd
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from src.historical_loader import load_performance_stats, get_best_params
from src.llm import TradingLLM
from datetime import datetime, date, timedelta
from config import WATCHLIST


class SignalGenerator(BaseAgent):
    EARNINGS_WINDOW_DAYS = 5   # flag tickers with earnings within this many days

    def __init__(self):
        super().__init__(
            "SignalGenerator",
            "You are SignalGenerator. Only output high-conviction signals when regime, "
            "sentiment, sector rotation, AND backtest edge all align.\n\n"
            "CRITICAL: The vault contains an OUTCOMES report (vault/08-Logs/OUTCOMES_*.md) "
            "with quantified win/loss patterns from recent trades. "
            "You MUST check the RAG context for '✅ FAVOUR' and '🚫 AVOID' rules "
            "from OutcomeTracker and apply them to every signal.\n\n"
            "For each ticker output exactly this format:\n"
            "### TICKER\n"
            "DIRECTION: BUY | SELL | NO SIGNAL\n"
            "CONFIDENCE: N%\n"
            "ENTRY: $X.XX\n"
            "STOP: $X.XX  (use 1.5× ATR below/above entry)\n"
            "TARGET: $X.XX\n"
            "R:R: X:X\n"
            "RATIONALE: <1-2 sentences citing specific indicators AND any outcome-pattern rules applied>\n\n"
            "EARNINGS RULE: If a ticker is flagged ⚠️ EARNINGS WITHIN 5 DAYS, "
            "output NO SIGNAL unless confidence ≥ 80% AND R:R ≥ 1:3. "
            "Binary earnings risk invalidates most edge.\n\n"
            "For NO SIGNAL, explain which condition failed. "
            "Reject anything with confidence <65% or R:R <1:2.",
            model=TradingLLM.SONNET,
            max_tokens=1600,
            rag_top_k=6,        # increased to pick up the OUTCOMES note
            temperature=0.20,   # slight variability helps explore different signal combinations
        )
        self._fetcher = DataFetcher()

    def _build_perf_block(self, tickers: list) -> str:
        """
        Load performance_stats.json and build a compact per-ticker block
        showing historical win/loss counts, profit factor, and P&L.
        Agents use this to calibrate confidence — a strategy with PF=0.97
        (near profitable) warrants higher confidence than one with PF=0.27.
        """
        stats = load_performance_stats()
        if not stats:
            return ""

        by_ticker   = stats.get("by_ticker", {})
        by_strategy = stats.get("by_strategy", {})
        by_session  = stats.get("by_session", [])
        regime_best = get_best_params().get("regime_best_strategy", {})

        lines = ["\n\nHISTORICAL STRATEGY PERFORMANCE (from 10-year backtest training):"]
        lines.append(
            "Use this to calibrate confidence — favour strategies near PF 1.0; "
            "penalise strategies with PF < 0.5 or expectancy < -2%."
        )
        lines.append(f"{'Ticker':<7} {'Best Strategy':<22} {'Win%':<7} "
                     f"{'Wins':<6} {'Losses':<8} {'PF':<6} {'Expect/trade':<14} "
                     f"{'Return%':<10} {'P&L($100k)'}")
        lines.append("-" * 95)

        for ticker in tickers:
            bt = by_ticker.get(ticker, {})
            if not bt or not bt.get("best_strategy"):
                lines.append(f"  {ticker}: no training data")
                continue
            strat   = bt["best_strategy"]
            wr      = bt.get("best_win_rate", 0)
            wins    = bt.get("best_wins", 0)
            losses  = bt.get("best_losses", 0)
            pf      = bt.get("best_profit_factor", 0)
            exp     = bt.get("best_expectancy_pct", 0)
            ret     = bt.get("best_return_pct", 0)
            pnl     = bt.get("best_pnl_usd", 0)
            pf_flag = " <<NEAR PROFITABLE>>" if pf >= 0.85 else (" <<AVOID>>" if pf < 0.40 else "")
            lines.append(
                f"  {ticker:<7} {strat:<22} {wr:.1f}%  "
                f"{wins:<6} {losses:<8} {pf:<6.3f} {exp:+.3f}%        "
                f"{ret:+.1f}%      ${pnl:+,.0f}{pf_flag}"
            )

        # Regime context
        if regime_best:
            lines.append("")
            lines.append("Regime-best strategies (from historical training):")
            for regime, strat in regime_best.items():
                agg = by_strategy.get(strat, {})
                wr  = agg.get("avg_win_rate", 0)
                pf  = agg.get("avg_profit_factor", 0)
                lines.append(f"  {regime:<10} -> {strat:<22} (avg WinRate={wr:.1f}%  PF={pf:.3f})")

        # Top 3 sessions as concrete examples of the best edge found
        top3 = stats.get("top10_by_pf", [])[:3]
        if top3:
            lines.append("")
            lines.append("Top 3 best-performing sessions (highest PF — closest to profitable edge):")
            for s in top3:
                lines.append(
                    f"  {s['ticker']} {s['strategy']}: "
                    f"PF={s['profit_factor']:.3f}  "
                    f"WinRate={s['win_rate']:.1f}% ({s['wins']}W/{s['losses']}L)  "
                    f"Expect={s['expectancy_pct']:+.3f}%/trade  "
                    f"Return={s['return_pct']:+.1f}%"
                )

        return "\n".join(lines)

    def _earnings_flags(self, tickers: list) -> dict[str, str]:
        """
        Return {ticker: "YYYY-MM-DD"} for tickers with earnings within EARNINGS_WINDOW_DAYS.

        Reads the shared earnings cache written by the orchestrator in Phase 1a
        (src/earnings_cache.py) — zero network calls on the warm path.
        Falls back to live fetch automatically for any ticker missing from the cache.
        """
        from src.earnings_cache import get_upcoming_flags
        return get_upcoming_flags(
            tickers,
            str(self.vault.root),
            window_days=self.EARNINGS_WINDOW_DAYS,
        )

    def _build_indicator_summary(self, tickers: list) -> str:
        """Load pre-computed indicators from saved CSVs for exact price context."""
        lines = []
        for ticker in tickers:
            csv_path = self.vault.root / "01-Assets" / "Stocks" / f"{ticker}.csv"
            if not csv_path.exists():
                lines.append(f"  {ticker}: no data available")
                continue
            try:
                df = pd.read_csv(str(csv_path))
                if df.empty or len(df) < 2:
                    lines.append(f"  {ticker}: insufficient data")
                    continue

                last = df.iloc[-1]
                prev = df.iloc[-2]
                chg  = (float(last["close"]) - float(prev["close"])) / float(prev["close"]) * 100

                rsi       = last.get("rsi",         float("nan"))
                macd      = last.get("macd",        0.0)
                macd_sig  = last.get("macd_signal", 0.0)
                macd_hist = last.get("macd_hist",   0.0)
                bb_pct    = last.get("bb_pct",      50.0)
                bb_upper  = last.get("bb_upper",    float("nan"))
                bb_lower  = last.get("bb_lower",    float("nan"))
                atr       = last.get("atr",         float("nan"))
                sma50     = last.get("sma50",       last["close"])
                sma200    = last.get("sma200",      last["close"])
                close     = float(last["close"])

                # Derived signals
                rsi_sig  = ("OVERBOUGHT" if rsi >= 70 else "OVERSOLD" if rsi <= 30 else "neutral")
                macd_dir = "bullish cross ↑" if macd > macd_sig else "bearish cross ↓"
                bb_sig   = ("at UPPER band" if bb_pct >= 85 else
                            "at LOWER band" if bb_pct <= 15 else "mid-range")
                trend    = ("ABOVE" if close > sma50 else "BELOW")
                primary  = ("ABOVE" if close > sma200 else "BELOW")

                # ATR-based stop distances
                atr_stop_long  = f"${close - 1.5*atr:.2f}" if not pd.isna(atr) else "N/A"
                atr_stop_short = f"${close + 1.5*atr:.2f}" if not pd.isna(atr) else "N/A"

                lines.append(
                    f"  {ticker}:\n"
                    f"    Close=${close:.2f} ({chg:+.2f}%)  ATR=${atr:.2f}\n"
                    f"    RSI={rsi:.1f} ({rsi_sig})  "
                    f"MACD={macd:+.4f}/sig={macd_sig:+.4f}/hist={macd_hist:+.4f} ({macd_dir})\n"
                    f"    BB={bb_pct:.0f}%B ({bb_sig}) [{bb_lower:.2f}–{bb_upper:.2f}]\n"
                    f"    SMA50=${sma50:.2f} ({trend})  SMA200=${sma200:.2f} ({primary} — "
                    f"{'uptrend' if close>sma200 else 'downtrend'})\n"
                    f"    ATR-based stops: Long stop≈{atr_stop_long}  Short stop≈{atr_stop_short}"
                )
            except Exception as e:
                lines.append(f"  {ticker}: parse error ({e})")

        return "\n".join(lines)

    def generate_signals(self, tickers: list = None):
        if tickers is None:
            tickers = WATCHLIST

        indicator_block = self._build_indicator_summary(tickers)
        perf_block      = self._build_perf_block(tickers)

        # Check for upcoming earnings — add warnings to prompt
        print("   Checking earnings calendar ...")
        earnings_flags = self._earnings_flags(tickers)
        earnings_block = ""
        if earnings_flags:
            warnings = [f"  ⚠️  {t}: EARNINGS {d} (within {self.EARNINGS_WINDOW_DAYS} days)"
                        for t, d in sorted(earnings_flags.items())]
            earnings_block = (
                f"\n\nEARNINGS WARNINGS — apply tighter rules to these tickers:\n"
                + "\n".join(warnings)
            )
            print(f"   Earnings flags: {earnings_flags}")
        else:
            print("   No earnings within 5 days — no flags")

        task = (
            f"Generate high-conviction trading signals for: {', '.join(tickers)}.\n\n"
            f"LIVE COMPUTED INDICATORS (use these exact values for price levels):\n"
            f"{indicator_block}"
            f"{earnings_block}"
            f"{perf_block}\n\n"
            "Cross-reference: current market regime, sector rotation signal, "
            "sentiment scores, and best-ranked strategies from the vault.\n"
            "PERFORMANCE RULE: Strategies with Profit Factor < 0.50 have historically "
            "destroyed capital — reduce confidence by 15% for those tickers. "
            "Strategies with PF ≥ 0.85 (near profitable) warrant higher confidence. "
            "Cite the historical win rate and PF in your RATIONALE for every signal.\n"
            "Entry should be near current close or a key level. "
            "Stop = 1.5× ATR from entry (provided above). "
            "Target = minimum 2× risk for R:R ≥ 1:2."
        )
        self.think_and_write(
            task,
            "03-Trade-Journal",
            f"signals_{datetime.now().strftime('%Y-%m-%d')}.md",
        )
