# src/agents/optimizer.py
"""
Optimizer — daily walk-forward strategy benchmarking and ranking.

Data source
-----------
Loads from data/historical/{ticker}_10y.csv via historical_loader
(10 years of data instead of the old 2-year network fetch).
Falls back to vault CSV then live network if the file is missing.

Best params
-----------
If data/historical/best_params.json exists (written by HistoricalTrainer /
train_strategies.py), each strategy's backtest uses the optimised parameters
for that ticker instead of the hardcoded defaults.  This means after one
training run the daily loop's backtests automatically use the best settings.
"""
import re
import json
import pandas as pd
from src.agents.base import BaseAgent
from src.backtester import run_backtest, STRATEGIES
from src.historical_loader import load_historical, get_best_params, load_performance_stats, _HIST_DIR
from src.llm import TradingLLM
from datetime import datetime


class Optimizer(BaseAgent):
    def __init__(self):
        super().__init__(
            "Optimizer",
            "You are Optimizer. Compare walk-forward backtest results across strategies and extract: "
            "which strategy performed best, what failed, parameter sensitivity, and regime fit. "
            "Output a ranked comparison table then 3-5 action bullets.",
            model=TradingLLM.HAIKU,
            max_tokens=1000,
            rag_top_k=2,
            temperature=0.10,   # analytical ranking — deterministic preferred
        )

    def _load_ticker_df(self, ticker: str) -> pd.DataFrame:
        """
        Load OHLCV + indicators for *ticker*.

        Priority order:
          1. data/historical/{ticker}_10y.csv  (10 years, pre-downloaded)
          2. vault/01-Assets/Stocks/{ticker}.csv  (2-year vault CSV from DataScout)
          3. Live network fetch via DataFetcher

        Uses historical_loader which handles all three cases automatically.
        """
        df = load_historical(ticker, years=10, compute_indicators=True)
        if not df.empty and len(df) >= 200:
            print(f"   Optimizer: {ticker} — {len(df)} bars loaded from history")
            return df
        # Ultimate fallback (should rarely trigger now that 10y CSVs exist)
        from src.data_fetcher import DataFetcher
        print(f"   Optimizer: {ticker} — falling back to live fetch")
        return DataFetcher().fetch_historical(ticker)

    def _get_best_params(self, strategy_name: str, ticker: str) -> dict:
        """
        Return the optimised parameter dict for (strategy, ticker) if
        best_params.json exists.  Returns empty dict if not found.
        """
        strat_params = get_best_params(strategy_name)
        return strat_params.get(ticker, {})

    def run_optimization_loop(self, tickers: list = None):
        """
        Run walk-forward backtests for every strategy × ticker combination.
        Uses optimised parameters from best_params.json when available.
        Results are saved to vault/04-Backtests/.
        """
        if tickers is None:
            tickers = ["AAPL", "TSLA"]
        for ticker in tickers:
            print(f"   Optimizing {ticker}...")
            df = self._load_ticker_df(ticker)
            if df.empty:
                continue
            all_reports = ""
            for strat_name in STRATEGIES:
                # Apply saved best params if available (from HistoricalTrainer run)
                best_params = self._get_best_params(strat_name, ticker)
                # Strip meta-keys (keys starting with '_')
                best_params = {k: v for k, v in best_params.items()
                               if not k.startswith("_")}
                report = run_backtest(df, strat_name, ticker,
                                      extra_params=best_params or None)
                all_reports += f"\n\n## {strat_name}\n{report}"
            self.think_and_write(
                f"Compare these backtest results across strategies for {ticker}:{all_reports}",
                "04-Backtests",
                f"OPTIMIZED_{ticker}_{datetime.now().strftime('%Y%m%d')}.md",
            )

    # ── Direct vault file reader (avoids stale RAG after mid-run file creation) ──
    def _read_backtest_metrics(self) -> dict[str, list[dict]]:
        """Scan vault/04-Backtests/ and parse metrics from each strategy's WF reports."""
        bt_dir  = self.vault.root / "04-Backtests"
        results = {s: [] for s in STRATEGIES}

        for strat_name in STRATEGIES:
            seen_tickers: set = set()
            for md_file in sorted(bt_dir.glob(f"*_{strat_name}_WF_*.md"), reverse=True):
                stem   = md_file.stem
                suffix = f"_{strat_name}_WF_"
                if suffix not in stem:
                    continue
                ticker = stem.split(suffix)[0]
                if ticker in seen_tickers:
                    continue
                seen_tickers.add(ticker)

                try:
                    txt = md_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                def _val(pat, default=0.0):
                    m = re.search(pat, txt)
                    if not m:
                        return default
                    try:
                        return float(m.group(1))
                    except (ValueError, TypeError):
                        return default

                row = {
                    "ticker":    ticker,
                    "return":    _val(r'\*\*Return\*\*[:\s]+([+-]?\d+\.?\d*)%'),
                    "max_dd":    _val(r'\*\*Max.?Drawdown\*\*[:\s]+([+-]?\d+\.?\d*)%'),
                    "sharpe":    _val(r'\*\*Sharpe\*\*[:\s]+([+-]?\d+\.?\d*)'),
                    "win_rate":  _val(r'\*\*Win.?Rate\*\*[:\s]+(\d+\.?\d*)%'),
                    "calmar":    _val(r'\*\*Calmar\*\*[:\s]+([+-]?\d+\.?\d*)'),
                    "pf":        _val(r'\*\*Profit.?Factor\*\*[:\s]+([+-]?\d+\.?\d*)'),
                    "trades":    _val(r'\*\*Trades\*\*[:\s]+(\d+)'),
                }
                results[strat_name].append(row)

        return results

    def rank_strategies(self):
        metrics = self._read_backtest_metrics()

        lines    = ["# Backtest Summary — All Strategies\n"]
        agg_rows = []

        for strat_name, rows in metrics.items():
            if not rows:
                lines.append(f"## {strat_name}\n  No backtest files found\n")
                continue

            n       = len(rows)
            avg_ret = sum(r["return"]   for r in rows) / n
            avg_dd  = sum(r["max_dd"]   for r in rows) / n
            avg_sh  = sum(r["sharpe"]   for r in rows) / n
            avg_wr  = sum(r["win_rate"] for r in rows) / n
            avg_cal = sum(r["calmar"]   for r in rows) / n
            avg_pf  = sum(r["pf"]       for r in rows) / n

            agg_rows.append({
                "strategy": strat_name, "n": n,
                "avg_ret": avg_ret, "avg_dd": avg_dd, "avg_sh": avg_sh,
                "avg_wr": avg_wr,   "avg_cal": avg_cal, "avg_pf": avg_pf,
            })

            per_ticker = "\n".join(
                f"  {r['ticker']:6s}: Return={r['return']:+7.2f}%  "
                f"DD={r['max_dd']:6.1f}%  Sharpe={r['sharpe']:5.2f}  "
                f"WR={r['win_rate']:4.0f}%  Calmar={r['calmar']:5.2f}  "
                f"Trades={int(r['trades'])}"
                for r in sorted(rows, key=lambda x: x["calmar"], reverse=True)
            )
            lines.append(
                f"## {strat_name}  ({n} tickers tested)\n"
                f"  Averages: Return={avg_ret:+.2f}%  DD={avg_dd:.1f}%  "
                f"Sharpe={avg_sh:.2f}  WinRate={avg_wr:.0f}%  Calmar={avg_cal:.2f}  "
                f"ProfitFactor={avg_pf:.2f}\n"
                f"{per_ticker}\n"
            )

        # Sort aggregate by Calmar then Avg Return for the ranking prompt
        agg_rows.sort(key=lambda x: (x["avg_cal"], x["avg_ret"]), reverse=True)

        # Add best-params note if available
        params_path = _HIST_DIR / "best_params.json"
        params_note = ""
        if params_path.exists():
            try:
                data = json.loads(params_path.read_text(encoding="utf-8"))
                generated = data.get("generated", "")[:19]
                best_by_ticker = data.get("best_by_ticker", {})
                if best_by_ticker:
                    rec_lines = [f"  {t}: {v['strategy']} (Calmar {v['oos_calmar']:.2f})"
                                 for t, v in sorted(best_by_ticker.items())]
                    params_note = (
                        f"\n# Trained Optimal Strategies (from {generated})\n"
                        + "\n".join(rec_lines) + "\n"
                    )
                # Regime recommendations
                regime_best = data.get("regime_best_strategy", {})
                if regime_best:
                    reg_lines = [f"  {r}: {s}"
                                 for r, s in regime_best.items()]
                    params_note += (
                        "\n# Regime-Best Strategies\n"
                        + "\n".join(reg_lines) + "\n"
                    )
            except Exception:
                pass

        # ── Inject win/loss counts from performance_stats.json ───────────────
        perf_stats = load_performance_stats()
        perf_note  = ""
        if perf_stats:
            by_strategy = perf_stats.get("by_strategy", {})
            plines = ["\n# Win/Loss Counts & Profit Factor (from training sessions)\n",
                      f"{'Strategy':<25} {'Total W':<9} {'Total L':<9} "
                      f"{'W:L':<12} {'Avg PF':<8} {'Avg Expect%':<13} "
                      f"{'Avg Return%':<13} {'Profitable Tickers'}"]
            plines.append("-" * 100)
            for strat, agg in sorted(by_strategy.items(),
                                     key=lambda x: -x[1].get("avg_profit_factor", 0)):
                tw   = agg.get("total_wins", 0)
                tl   = agg.get("total_losses", 0)
                wl   = agg.get("win_loss_ratio", f"{tw}:{tl}")
                pf   = agg.get("avg_profit_factor", 0)
                exp  = agg.get("avg_expectancy_pct", 0)
                ret  = agg.get("avg_return_pct", 0)
                prof = agg.get("profitable_tickers", 0)
                plines.append(
                    f"  {strat:<25} {tw:<9} {tl:<9} {wl:<12} "
                    f"{pf:<8.3f} {exp:+.3f}%       {ret:+.1f}%         {prof}/8"
                )
            overall_wr = perf_stats.get("overall_win_rate", 0)
            tot_w  = perf_stats.get("total_wins", 0)
            tot_l  = perf_stats.get("total_losses", 0)
            plines.append(f"\n  TOTALS: {tot_w} wins / {tot_l} losses across all sessions "
                          f"({overall_wr:.1f}% overall win rate)")
            perf_note = "\n".join(plines)

        rank_block = "\n".join(lines) + params_note + perf_note

        task = (
            "Using ONLY the real backtest data below, produce:\n"
            "1. A ranked markdown table: "
            "Rank | Strategy | Total Wins | Total Losses | Win:Loss | Avg PF | "
            "Avg Return % | Avg Sharpe | Avg Win Rate % | Tier\n"
            "   Tier definitions — 1=deploy-ready (PF>1.0 + positive avg return + WinRate>50%), "
            "2=needs-refinement (PF 0.7–1.0), Retired=PF<0.5 with no recoverable edge.\n"
            "2. Five concrete action bullets citing specific win/loss counts and PF numbers.\n\n"
            + rank_block
        )

        saved_model, saved_tokens = self.model, self.max_tokens
        self.model, self.max_tokens = TradingLLM.SONNET, 2500
        self.think_and_write(
            task, "06-Playbooks",
            f"STRATEGY_RANKING_{datetime.now().strftime('%Y%m%d')}.md",
        )
        self.model, self.max_tokens = saved_model, saved_tokens
        print("Strategy ranking complete")
