# src/agents/historical_trainer.py
"""
HistoricalTrainer — self-training agent that uses 10 years of data.

What it does
------------
1. Loads full 10-year history for every watchlist ticker.
2. Runs *all* 8 strategies on each ticker (walk-forward backtest).
3. Runs parameter grid-search (bt.optimize()) to find optimal settings;
   saves them to data/historical/best_params.json.
4. Detects historical market regimes (Bull / Bear / Ranging) and tests
   which strategies win in each regime.
5. Calls Claude (Sonnet) with the full findings and asks it to:
   - Identify patterns no individual agent sees
   - Propose 3-5 new strategy variants with specific entry/exit rules
   - Recommend which strategies to deploy NOW vs retire
6. Writes a comprehensive training report to vault/05-Performance/.

Entry points
------------
    trainer = HistoricalTrainer()
    trainer.train_all()            # full training run (~5-20 min)
    trainer.run_regime_check()     # fast daily regime snapshot (< 1 min)
"""
from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.agents.base import BaseAgent
from src.backtester import STRATEGIES, _PARAM_GRIDS, run_backtest, run_param_search
from src.historical_loader import load_all_historical, _HIST_DIR
from src.llm import TradingLLM
from config import WATCHLIST


# ── Regime detection ──────────────────────────────────────────────────────────

def detect_regimes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Label each bar in *df* as Bull / Bear / Ranging.

    Rules
    -----
    Bull    : close > SMA200  AND  SMA50 > SMA200
    Bear    : close < SMA200  AND  SMA50 < SMA200
    Ranging : everything else (choppy / transitioning)

    Requires at least 210 bars.  Returns df with a new 'regime' column.
    """
    df = df.copy()
    close  = df["close"] if "close" in df.columns else df["Close"]
    sma50  = close.rolling(50,  min_periods=50).mean()
    sma200 = close.rolling(200, min_periods=200).mean()

    def _label(row_idx):
        c  = close.iloc[row_idx]
        s5 = sma50.iloc[row_idx]
        s2 = sma200.iloc[row_idx]
        if pd.isna(s5) or pd.isna(s2):
            return "Unknown"
        if c > s2 and s5 > s2:
            return "Bull"
        if c < s2 and s5 < s2:
            return "Bear"
        return "Ranging"

    df["regime"] = [_label(i) for i in range(len(df))]
    return df


def regime_periods(df: pd.DataFrame, min_bars: int = 30) -> list[dict]:
    """
    Extract contiguous regime blocks (min *min_bars* long) from a df
    that already has a 'regime' column.

    Returns list of dicts:
        {regime, start, end, bars, df_slice}
    """
    if "regime" not in df.columns:
        df = detect_regimes(df)

    periods: list[dict] = []
    if df.empty:
        return periods

    current_regime = df["regime"].iloc[0]
    start_idx      = 0

    for i in range(1, len(df)):
        if df["regime"].iloc[i] != current_regime:
            length = i - start_idx
            if length >= min_bars and current_regime != "Unknown":
                ts_col = "timestamp" if "timestamp" in df.columns else df.index.name or "index"
                if ts_col in df.columns:
                    start_dt = str(df[ts_col].iloc[start_idx])[:10]
                    end_dt   = str(df[ts_col].iloc[i - 1])[:10]
                else:
                    start_dt = str(start_idx)
                    end_dt   = str(i - 1)
                periods.append({
                    "regime":   current_regime,
                    "start":    start_dt,
                    "end":      end_dt,
                    "bars":     length,
                    "df_slice": df.iloc[start_idx:i].copy(),
                })
            current_regime = df["regime"].iloc[i]
            start_idx      = i

    # Trailing period
    length = len(df) - start_idx
    if length >= min_bars and current_regime != "Unknown":
        ts_col = "timestamp" if "timestamp" in df.columns else None
        if ts_col and ts_col in df.columns:
            start_dt = str(df[ts_col].iloc[start_idx])[:10]
            end_dt   = str(df[ts_col].iloc[-1])[:10]
        else:
            start_dt = str(start_idx)
            end_dt   = str(len(df) - 1)
        periods.append({
            "regime":   current_regime,
            "start":    start_dt,
            "end":      end_dt,
            "bars":     length,
            "df_slice": df.iloc[start_idx:].copy(),
        })

    return periods


# ── HistoricalTrainer agent ───────────────────────────────────────────────────

class HistoricalTrainer(BaseAgent):
    """
    Deep historical training agent.  Runs offline (not in the hot daily loop).
    Call train_all() from train_strategies.py.
    Call run_regime_check() from the daily loop for a lightweight regime snapshot.
    """

    def __init__(self):
        super().__init__(
            "HistoricalTrainer",
            "You are HistoricalTrainer, a quantitative research specialist.\n\n"
            "You receive the complete 10-year walk-forward backtest results and "
            "parameter optimisation findings for 8 strategies across 8 major tech stocks.\n\n"
            "Your job is to synthesise ALL findings and produce:\n\n"
            "## 1. Strategy Verdict Table\n"
            "  Rank | Strategy | Avg Calmar | Avg Sharpe | Avg Return% | Best Ticker(s) | "
            "Best Regime | Verdict (DEPLOY / REFINE / RETIRE)\n\n"
            "## 2. Regime-Strategy Matrix\n"
            "  Which strategies statistically outperform in Bull / Bear / Ranging regimes? "
            "Give win rates and Sharpe by regime.\n\n"
            "## 3. Optimal Parameter Insights\n"
            "  For each strategy, what parameter ranges work best across tickers? "
            "Any surprising findings (e.g., shorter lookbacks beat longer for TSLA)?\n\n"
            "## 4. NEW Strategy Proposals (CRITICAL)\n"
            "  Propose EXACTLY 3 new strategy variants the system should test next. "
            "For each provide:\n"
            "  - Strategy Name\n"
            "  - Type (momentum / mean-reversion / breakout / multi-factor)\n"
            "  - Entry Condition (specific indicator thresholds)\n"
            "  - Exit Condition\n"
            "  - Position Sizing rule\n"
            "  - Regime Filter (when to apply it)\n"
            "  - Why you expect edge (cite the data patterns that inspired it)\n\n"
            "## 5. Immediate Action Items\n"
            "  5 concrete bullets for the trading system to act on tomorrow.\n\n"
            "Use ONLY the provided data. Cite specific numbers.",
            model=TradingLLM.SONNET,
            max_tokens=4000,
            rag_top_k=3,
            temperature=0.25,   # proposes new strategy variants — moderate creativity
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _safe_metric(val, default=0.0) -> float:
        try:
            f = float(val)
            return f if math.isfinite(f) else default
        except Exception:
            return default

    def _run_strategy_on_period(self, df_slice: pd.DataFrame,
                                strategy_name: str) -> dict:
        """Run a single backtest on a regime slice; return key metrics."""
        from src.backtester import _run_bt_core, BACKTEST_CASH
        if len(df_slice) < 60:
            return {}
        try:
            stats, _ = _run_bt_core(df_slice, strategy_name)
            return {
                "calmar":   self._safe_metric(stats.get("Calmar Ratio")),
                "sharpe":   self._safe_metric(stats.get("Sharpe Ratio")),
                "return":   self._safe_metric(stats.get("Return [%]")),
                "win_rate": self._safe_metric(stats.get("Win Rate [%]")),
                "trades":   int(stats.get("# Trades", 0)),
            }
        except Exception:
            return {}

    # ── Phase 1: Full 10-year strategy benchmark ──────────────────────────────

    def run_full_benchmark(self, all_data: dict[str, pd.DataFrame]) -> dict:
        """
        Run every strategy on every ticker's 10-year history.
        Returns nested dict: {strategy_name: {ticker: {metrics}}}
        """
        print("   [Trainer] Phase 1: Full benchmark (all strategies × all tickers)...")
        results: dict[str, dict] = {s: {} for s in STRATEGIES}

        for ticker, df in all_data.items():
            if df.empty or len(df) < 300:
                continue
            for strat_name in STRATEGIES:
                print(f"      {strat_name} / {ticker}...")
                report = run_backtest(df, strat_name, ticker)
                # Parse key metrics from the markdown report
                import re

                def _val(pat, text=report):
                    m = re.search(pat, text)
                    try:
                        return float(m.group(1)) if m else 0.0
                    except Exception:
                        return 0.0

                win_rate = _val(r"\*\*Win.?Rate\*\*[:\s]+(\d+\.?\d*)%")
                trades   = int(_val(r"\*\*(?:Total\s+)?Trades\*\*[:\s]+(\d+)"))
                n_wins   = round(win_rate / 100 * trades)
                results[strat_name][ticker] = {
                    "return":     _val(r"\*\*Return\*\*[:\s]+([+-]?\d+\.?\d*)%"),
                    "max_dd":     _val(r"\*\*Max.?Drawdown\*\*[:\s]+([+-]?\d+\.?\d*)%"),
                    "sharpe":     _val(r"\*\*Sharpe\*\*[:\s]+([+-]?\d+\.?\d*)"),
                    "win_rate":   win_rate,
                    "wins":       n_wins,
                    "losses":     trades - n_wins,
                    "calmar":     _val(r"\*\*Calmar\*\*[:\s]+([+-]?\d+\.?\d*)"),
                    "pf":         _val(r"\*\*Profit.?Factor\*\*[:\s]+([+-]?\d+\.?\d*)"),
                    "expectancy": _val(r"\*\*Expectancy\*\*[:\s]+([+-]?\d+\.?\d*)%"),
                    "trades":     trades,
                }

        self._write_performance_stats(results)
        return results

    def _write_performance_stats(self, results: dict) -> None:
        """
        Build and save data/historical/performance_stats.json.

        Called automatically by run_full_benchmark() so every agent can
        load win/loss counts, profit factors, and P&L without re-running
        backtests or querying RAG.
        """
        from src.backtester import BACKTEST_CASH

        sessions = []
        for strat_name, ticker_map in results.items():
            for ticker, r in ticker_map.items():
                trades   = int(r.get("trades", 0))
                win_rate = r.get("win_rate", 0)
                wins     = int(r.get("wins", round(win_rate / 100 * trades)))
                losses   = trades - wins
                ret      = r.get("return", 0)
                sessions.append({
                    "ticker":         ticker,
                    "strategy":       strat_name,
                    "win_rate":       round(win_rate, 1),
                    "wins":           wins,
                    "losses":         losses,
                    "trades":         trades,
                    "profit_factor":  round(r.get("pf", 0), 3),
                    "expectancy_pct": round(r.get("expectancy", 0), 3),
                    "return_pct":     round(ret, 2),
                    "pnl_usd":        round(ret / 100 * BACKTEST_CASH),
                    "max_dd_pct":     round(r.get("max_dd", 0), 2),
                    "sharpe":         round(r.get("sharpe", 0), 3),
                    "calmar":         round(r.get("calmar", 0), 3),
                })

        # Per-strategy aggregates
        by_strategy: dict = {}
        for strat_name, ticker_map in results.items():
            rows = list(ticker_map.values())
            n = len(rows)
            if n == 0:
                continue
            total_trades = sum(int(r.get("trades", 0)) for r in rows)
            total_wins   = sum(int(r.get("wins", 0)) for r in rows)
            by_strategy[strat_name] = {
                "avg_win_rate":       round(sum(r.get("win_rate", 0) for r in rows) / n, 1),
                "total_wins":         total_wins,
                "total_losses":       total_trades - total_wins,
                "total_trades":       total_trades,
                "win_loss_ratio":     f"{total_wins}:{total_trades - total_wins}",
                "avg_profit_factor":  round(sum(r.get("pf", 0) for r in rows) / n, 3),
                "avg_expectancy_pct": round(sum(r.get("expectancy", 0) for r in rows) / n, 3),
                "avg_return_pct":     round(sum(r.get("return", 0) for r in rows) / n, 1),
                "avg_pnl_usd":        round(sum(r.get("return", 0) / 100 * BACKTEST_CASH
                                               for r in rows) / n),
                "avg_sharpe":         round(sum(r.get("sharpe", 0) for r in rows) / n, 3),
                "profitable_tickers": sum(1 for r in rows if r.get("return", -999) > 0),
            }

        # Per-ticker: best strategy by profit factor
        by_ticker: dict = {}
        all_tickers = set(t for tm in results.values() for t in tm)
        for ticker in all_tickers:
            best = {"best_strategy": None, "best_profit_factor": -999}
            for strat_name, ticker_map in results.items():
                r = ticker_map.get(ticker)
                if r is None:
                    continue
                pf = r.get("pf", 0)
                if pf > best["best_profit_factor"]:
                    trades = int(r.get("trades", 0))
                    wins   = int(r.get("wins", 0))
                    best = {
                        "best_strategy":       strat_name,
                        "best_profit_factor":  round(pf, 3),
                        "best_return_pct":     round(r.get("return", 0), 2),
                        "best_pnl_usd":        round(r.get("return", 0) / 100 * BACKTEST_CASH),
                        "best_win_rate":       round(r.get("win_rate", 0), 1),
                        "best_wins":           wins,
                        "best_losses":         trades - wins,
                        "best_trades":         trades,
                        "best_expectancy_pct": round(r.get("expectancy", 0), 3),
                    }
            by_ticker[ticker] = best

        # Top 10 sessions by profit factor (closest to profitable)
        top10 = sorted(sessions, key=lambda x: x["profit_factor"], reverse=True)[:10]

        # Overall totals
        total_trades = sum(s["trades"] for s in sessions)
        total_wins   = sum(s["wins"] for s in sessions)
        profitable   = sum(1 for s in sessions if s["return_pct"] > 0)

        payload = {
            "generated":          datetime.now().isoformat()[:19],
            "capital":            BACKTEST_CASH,
            "total_sessions":     len(sessions),
            "total_trades":       total_trades,
            "total_wins":         total_wins,
            "total_losses":       total_trades - total_wins,
            "overall_win_rate":   round(total_wins / total_trades * 100, 1) if total_trades else 0,
            "profitable_sessions": profitable,
            "by_session":         sessions,
            "by_strategy":        by_strategy,
            "by_ticker":          by_ticker,
            "top10_by_pf":        top10,
        }

        perf_path = _HIST_DIR / "performance_stats.json"
        perf_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"   [Trainer] Performance stats saved -> {perf_path}")

    # ── Phase 2: Parameter grid search ────────────────────────────────────────

    def run_param_optimisation(self, all_data: dict[str, pd.DataFrame]
                               ) -> dict[str, dict]:
        """
        Grid-search optimal parameters for each strategy × ticker.
        Saves results to data/historical/best_params.json.
        Returns {strategy_name: {ticker: {best_params + oos metrics}}}
        """
        print("   [Trainer] Phase 2: Parameter optimisation...")
        opt_results: dict[str, dict] = {s: {} for s in _PARAM_GRIDS}

        for ticker, df in all_data.items():
            if len(df) < 300:
                continue
            for strat_name in _PARAM_GRIDS:
                print(f"      Optimising {strat_name} / {ticker}...")
                res = run_param_search(df, strat_name, ticker)
                if res:
                    opt_results[strat_name][ticker] = res

        # ── Build per-ticker "best strategy" recommendation ───────────────────
        best_by_ticker: dict[str, dict] = {}
        for ticker in all_data:
            best_calmar = -999.0
            best_strat  = "SMA_Crossover"
            best_params = {}
            for strat_name, ticker_map in opt_results.items():
                r = ticker_map.get(ticker, {})
                if r and self._safe_metric(r.get("oos_calmar")) > best_calmar:
                    best_calmar = self._safe_metric(r["oos_calmar"])
                    best_strat  = strat_name
                    best_params = r.get("best_params", {})
            best_by_ticker[ticker] = {
                "strategy":   best_strat,
                "best_params": best_params,
                "oos_calmar": round(best_calmar, 3),
            }

        # ── Save to JSON ──────────────────────────────────────────────────────
        strategies_flat: dict[str, dict] = {}
        for strat_name, ticker_map in opt_results.items():
            strategies_flat[strat_name] = {}
            for ticker, res in ticker_map.items():
                strategies_flat[strat_name][ticker] = {
                    **res.get("best_params", {}),
                    "_oos_calmar": res.get("oos_calmar", 0),
                    "_oos_sharpe": res.get("oos_sharpe", 0),
                    "_oos_return": res.get("oos_return", 0),
                }

        payload = {
            "generated":      datetime.now().isoformat(),
            "strategies":     strategies_flat,
            "best_by_ticker": best_by_ticker,
        }
        params_path = _HIST_DIR / "best_params.json"

        # Custom encoder: coerce numpy scalar types to native Python so json.dumps works
        class _NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, "item"):   # numpy int/float
                    return obj.item()
                if hasattr(obj, "tolist"): # numpy array
                    return obj.tolist()
                return super().default(obj)

        params_path.write_text(
            json.dumps(payload, indent=2, cls=_NumpyEncoder), encoding="utf-8"
        )
        print(f"   [Trainer] Best params saved -> {params_path}")

        return opt_results

    # ── Phase 3: Regime analysis ──────────────────────────────────────────────

    def run_regime_analysis(self, all_data: dict[str, pd.DataFrame]
                            ) -> dict[str, dict]:
        """
        For each ticker, detect historical Bull/Bear/Ranging regimes
        and test which strategies performed best in each.

        Returns {regime: {strategy: avg_calmar}}
        """
        print("   [Trainer] Phase 3: Regime analysis...")
        regime_perf: dict[str, dict[str, list]] = {
            "Bull":    {s: [] for s in STRATEGIES},
            "Bear":    {s: [] for s in STRATEGIES},
            "Ranging": {s: [] for s in STRATEGIES},
        }

        for ticker, df in all_data.items():
            if len(df) < 210:
                continue
            df_reg = detect_regimes(df)
            periods = regime_periods(df_reg, min_bars=40)
            print(f"   {ticker}: {len(periods)} regime periods detected")

            for period in periods:
                reg   = period["regime"]
                slice_ = period["df_slice"]
                if reg not in regime_perf:
                    continue
                for strat_name in STRATEGIES:
                    m = self._run_strategy_on_period(slice_, strat_name)
                    if m and m.get("trades", 0) >= 3:
                        regime_perf[reg][strat_name].append(m.get("calmar", 0))

        # Compute averages
        regime_summary: dict[str, dict] = {}
        for regime, strat_map in regime_perf.items():
            avg_by_strat = {}
            for strat_name, calmars in strat_map.items():
                if calmars:
                    avg_by_strat[strat_name] = round(
                        sum(calmars) / len(calmars), 3
                    )
            regime_summary[regime] = avg_by_strat

        # Find best strategy per regime
        best_per_regime: dict[str, str] = {}
        for regime, strat_map in regime_summary.items():
            if strat_map:
                best = max(strat_map, key=lambda s: strat_map[s])
                best_per_regime[regime] = best
                print(f"   Best for {regime}: {best} "
                      f"(avg Calmar {strat_map[best]:.2f})")

        # Update best_params.json with regime info
        params_path = _HIST_DIR / "best_params.json"
        if params_path.exists():
            try:
                data = json.loads(params_path.read_text(encoding="utf-8"))
                data["regime_best_strategy"] = best_per_regime
                data["regime_analysis"]      = {
                    r: {s: v for s, v in sorted(sm.items(),
                                                key=lambda x: x[1], reverse=True)}
                    for r, sm in regime_summary.items()
                }

                class _NE(json.JSONEncoder):
                    def default(self, obj):
                        if hasattr(obj, "item"):   return obj.item()
                        if hasattr(obj, "tolist"): return obj.tolist()
                        return super().default(obj)

                params_path.write_text(
                    json.dumps(data, indent=2, cls=_NE), encoding="utf-8"
                )
            except Exception as e:
                print(f"   [Trainer] Could not update best_params with regime data: {e}")

        return regime_summary

    # ── Phase 4: LLM strategy discovery ──────────────────────────────────────

    def discover_strategies(self, benchmark: dict, opt_results: dict,
                            regime_summary: dict) -> str:
        """
        Feed all training findings to Claude Sonnet and ask for new strategy
        proposals + deployment recommendations.
        Saves the output to vault/05-Performance/TRAINING_REPORT.md.
        """
        print("   [Trainer] Phase 4: LLM strategy discovery...")

        # ── Build benchmark summary table ─────────────────────────────────────
        bench_lines = ["## Benchmark: All Strategies × All Tickers (10-Year WF)\n",
                       "Strategy | Ticker | Return% | MaxDD% | Sharpe | WinRate | Calmar | Trades"]
        for strat_name, ticker_map in benchmark.items():
            for ticker, m in sorted(ticker_map.items()):
                bench_lines.append(
                    f"{strat_name} | {ticker} | "
                    f"{m.get('return', 0):+.1f}% | "
                    f"{m.get('max_dd', 0):.1f}% | "
                    f"{m.get('sharpe', 0):.2f} | "
                    f"{m.get('win_rate', 0):.0f}% | "
                    f"{m.get('calmar', 0):.2f} | "
                    f"{int(m.get('trades', 0))}"
                )

        # ── Build optimised params summary ────────────────────────────────────
        opt_lines = ["\n## Grid-Search: Best Parameters (OOS Validated)\n",
                     "Strategy | Ticker | Best Params | OOS Sharpe | OOS Calmar | OOS Return%"]
        for strat_name, ticker_map in opt_results.items():
            for ticker, res in sorted(ticker_map.items()):
                opt_lines.append(
                    f"{strat_name} | {ticker} | "
                    f"{res.get('best_params', {})} | "
                    f"{res.get('oos_sharpe', 0):.2f} | "
                    f"{res.get('oos_calmar', 0):.2f} | "
                    f"{res.get('oos_return', 0):+.1f}%"
                )

        # ── Build regime analysis ─────────────────────────────────────────────
        reg_lines = ["\n## Regime Performance: Avg Calmar by Strategy\n",
                     "Regime | Best Strategy | " + " | ".join(STRATEGIES.keys())]
        for regime, strat_map in regime_summary.items():
            best = max(strat_map, key=lambda s: strat_map.get(s, 0)) if strat_map else "N/A"
            row  = " | ".join(
                f"{strat_map.get(s, 0):.2f}" for s in STRATEGIES.keys()
            )
            reg_lines.append(f"{regime} | {best} | {row}")

        full_data = (
            "\n".join(bench_lines) + "\n"
            + "\n".join(opt_lines)  + "\n"
            + "\n".join(reg_lines)
        )

        task = (
            "You have complete 10-year walk-forward backtest results, grid-search "
            "optimisation findings, and regime-specific performance data for 8 strategies "
            "on 8 major tech stocks.\n\n"
            "Produce the full structured analysis as per your system prompt.\n\n"
            + full_data
        )

        response = self.think_and_write(
            task,
            "05-Performance",
            f"TRAINING_REPORT_{datetime.now().strftime('%Y%m%d')}.md",
        )
        print("   [Trainer] Training report saved to vault/05-Performance/")
        return response

    # ── Master entry point ────────────────────────────────────────────────────

    def train_all(self, tickers: list[str] | None = None) -> None:
        """
        Full training run.  Typically takes 5-20 minutes depending on CPU.

        Phases
        ------
        1. Load 10-year data for all tickers
        2. Run all 8 strategies × 8 tickers (walk-forward benchmark)
        3. Grid-search optimal parameters; save to best_params.json
        4. Detect regimes; test per-regime strategy performance
        5. LLM synthesis + new strategy proposals

        Results written to:
          - data/historical/best_params.json   (machine-readable params)
          - vault/04-Backtests/*.md             (individual WF reports)
          - vault/05-Performance/TRAINING_REPORT_*.md  (LLM synthesis)
        """
        if tickers is None:
            tickers = WATCHLIST

        start = datetime.now()
        print(f"\n{'='*70}")
        print(f"  HistoricalTrainer.train_all()")
        print(f"  Tickers  : {tickers}")
        print(f"  Strategies: {list(STRATEGIES.keys())}")
        print(f"  Started  : {start.strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}\n")

        # Phase 1: Load data
        print("[Phase 1] Loading 10-year historical data...")
        all_data = load_all_historical(tickers, years=10)
        for t, df in all_data.items():
            print(f"   {t}: {len(df)} bars "
                  f"({df['timestamp'].min().date() if 'timestamp' in df.columns else '?'} "
                  f"- {df['timestamp'].max().date() if 'timestamp' in df.columns else '?'})")

        if not all_data:
            print("ERROR: No historical data loaded. Run download_history.py first.")
            return

        # Phase 2: Benchmark
        print("\n[Phase 2] Running full strategy benchmark...")
        benchmark = self.run_full_benchmark(all_data)

        # Phase 3: Parameter optimisation
        print("\n[Phase 3] Running parameter grid-search...")
        opt_results = self.run_param_optimisation(all_data)

        # Phase 4: Regime analysis
        print("\n[Phase 4] Regime detection and strategy mapping...")
        regime_summary = self.run_regime_analysis(all_data)

        # Phase 5: LLM discovery
        print("\n[Phase 5] LLM strategy synthesis and discovery...")
        self.discover_strategies(benchmark, opt_results, regime_summary)

        elapsed = int((datetime.now() - start).total_seconds())
        print(f"\n{'='*70}")
        print(f"  Training complete in {elapsed//60}m {elapsed%60}s")
        print(f"  best_params.json -> {_HIST_DIR / 'best_params.json'}")
        print(f"  Vault reports    -> vault/04-Backtests/ and vault/05-Performance/")
        print(f"{'='*70}\n")

    # ── Lightweight daily regime check ────────────────────────────────────────

    def run_regime_check(self) -> None:
        """
        Fast daily call: detect the current regime for each ticker using
        10-year data and write a regime snapshot to the vault.
        Does NOT run backtests — just regime detection + LLM summary.
        """
        print("   [Trainer] Daily regime check...")
        all_data = load_all_historical(WATCHLIST, years=10)

        regime_lines = []
        for ticker, df in all_data.items():
            if len(df) < 210:
                continue
            df_reg = detect_regimes(df)
            last = df_reg.iloc[-1]
            regime = last.get("regime", "Unknown")
            close  = float(df_reg["close"].iloc[-1])
            sma50  = float(df_reg["sma50"].iloc[-1])  if "sma50"  in df_reg.columns else None
            sma200 = float(df_reg["sma200"].iloc[-1]) if "sma200" in df_reg.columns else None

            sma_note = ""
            if sma50 and sma200:
                gap = (sma50 - sma200) / sma200 * 100
                sma_note = f" | SMA50/200 gap: {gap:+.1f}%"

            regime_lines.append(f"  {ticker}: **{regime}** @ ${close:.2f}{sma_note}")

        # Load best params for regime-based strategy recommendation
        params_path = _HIST_DIR / "best_params.json"
        regime_recs = ""
        if params_path.exists():
            try:
                params_data = json.loads(params_path.read_text(encoding="utf-8"))
                best_regime = params_data.get("regime_best_strategy", {})
                if best_regime:
                    regime_recs = (
                        "\n\n## Trained Regime Recommendations\n"
                        + "\n".join(f"  - {r}: use **{s}**"
                                    for r, s in best_regime.items())
                    )
            except Exception:
                pass

        regime_block = "\n".join(regime_lines)
        self.think_and_write(
            f"Current market regime snapshot for all watchlist tickers:\n\n"
            f"{regime_block}{regime_recs}\n\n"
            "Summarise: (1) dominant regime across tickers, (2) which trained strategy "
            "the optimizer should prioritise today, (3) any regime transitions to watch.",
            "00-Daily",
            f"regime_check_{datetime.now().strftime('%Y-%m-%d')}.md",
        )
        print("   [Trainer] Regime check written to vault/00-Daily/")
