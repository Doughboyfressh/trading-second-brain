# run_daily_loop.py
import sys
import os
import re
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Auto-relaunch with venv Python if running outside it
_venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    import subprocess
    sys.exit(subprocess.run([str(_venv_python)] + sys.argv).returncode)

sys.stdout.reconfigure(encoding="utf-8")

from datetime import datetime
from config import WATCHLIST, VAULT_PATH

from src.agents.data_scout          import DataScout
from src.agents.news_scout          import NewsScout
from src.agents.sector_scout        import SectorScout
from src.agents.market_analyst      import MarketAnalyst
from src.agents.strategist          import Strategist
from src.agents.optimizer           import Optimizer
from src.agents.risk_guardian       import RiskGuardian
from src.agents.critic              import Critic
from src.agents.regime_classifier   import RegimeClassifier
from src.agents.sentiment_agent     import SentimentAgent
from src.agents.meta_evaluator      import MetaEvaluator
from src.agents.signal_generator    import SignalGenerator
from src.agents.pnl_tracker         import PnLTracker
from src.agents.volatility_agent    import VolatilityAgent
from src.agents.execution_agent     import ExecutionAgent
from src.agents.outcome_tracker     import OutcomeTracker
from src.agents.historical_trainer  import HistoricalTrainer
from src.data_fetcher               import DataFetcher

# ── Thread-safe output ────────────────────────────────────────────────────────
_print_lock = threading.Lock()


def _tprint(*args, **kwargs):
    """Thread-safe print — keeps parallel output lines clean."""
    with _print_lock:
        print(*args, **kwargs)


def run_step(label: str, fn) -> bool:
    """Run one agent step; isolate failures so the loop keeps going."""
    _tprint(f"\n{'='*60}\n▶  {label}\n{'='*60}")
    try:
        fn()
        _tprint(f"✅ {label} — done")
        return True
    except Exception as e:
        _tprint(f"❌ {label} — FAILED: {e}")
        import traceback
        with _print_lock:
            traceback.print_exc()
        return False


# ── Parallel helpers ──────────────────────────────────────────────────────────
def run_parallel(steps: list[tuple[str, callable]], max_workers: int = 4) -> dict[str, bool]:
    """Run multiple (label, fn) pairs concurrently; return {label: bool}."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_step, lbl, fn): lbl for lbl, fn in steps}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results


# ── Strategy ranking reader ───────────────────────────────────────────────────
_KNOWN_STRATEGIES = {
    # Original 5
    "SMA_Crossover", "RSI_MeanReversion", "MACD_Momentum",
    "BB_Reversion", "EMA_Momentum",
    # Added in Session 3 — must be here or _read_top_strategy() falls back to SMA_Crossover
    "Volume_Breakout", "Trend_Pullback", "ROC_Momentum",
}

def _read_top_strategy(vault_path: str) -> str:
    """
    Parse the most recent STRATEGY_RANKING_*.md file and return the name of
    the Tier-1 (deploy-ready) strategy.  Falls back to 'SMA_Crossover' if the
    file is missing, unparseable, or no Tier-1 row is found.
    """
    playbooks = Path(vault_path) / "06-Playbooks"
    files = sorted(playbooks.glob("STRATEGY_RANKING_*.md"), reverse=True)
    if not files:
        _tprint("   ⚠️  No strategy ranking file — defaulting to SMA_Crossover")
        return "SMA_Crossover"
    try:
        text = files[0].read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            # Match table rows that contain "Tier 1" or "deploy" to find the top strategy
            if re.search(r'Tier\s*1\b|deploy.ready', line, re.IGNORECASE):
                # Extract the second pipe-delimited column = strategy name
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    candidate = parts[1].strip()
                    if candidate in _KNOWN_STRATEGIES:
                        _tprint(f"   📊 Top-ranked strategy from vault: {candidate}")
                        return candidate
    except Exception as e:
        _tprint(f"   ⚠️  Could not parse strategy ranking ({e}) — defaulting to SMA_Crossover")
    return "SMA_Crossover"


# ── File logging (Tee: console + daily log file) ──────────────────────────────
class _Tee:
    """Write every print() call to both console and a daily log file."""
    def __init__(self, *streams):
        self._streams = streams
    def write(self, s):
        for st in self._streams:
            try:
                st.write(s)
            except Exception:
                pass
    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass


def _send_loop_summary(results: dict, failed: list, elapsed: int,
                       start: "datetime", vault_path: str):
    """
    Fire a Telegram digest at the end of every daily loop run.

    Pulls three pieces of live data so the message is actually informative:
      1. Approved tickers — parsed from today's RISK_SWEEP_*.md
      2. Account equity   — read from vault/09-Portfolio/positions.json
      3. Open positions   — also from positions.json

    Silently no-ops when TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID are unset,
    or when the Telegram API call fails — a failed digest must never crash the loop.
    """
    import json as _json
    import requests as _req
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return   # Telegram not configured — skip silently

    passed      = sum(v for v in results.values())
    total       = len(results)
    date_str    = start.strftime("%Y-%m-%d (%A)")
    elapsed_str = f"{elapsed // 60}m {elapsed % 60}s"
    ok_icon     = "✅" if not failed else "⚠️"

    # ── Parse approved tickers from today's risk sweep ────────────────────────
    approved: list[str] = []
    try:
        sweep_path = (Path(vault_path) / "06-Playbooks"
                      / f"RISK_SWEEP_{start.strftime('%Y%m%d')}.md")
        if sweep_path.exists():
            text   = sweep_path.read_text(encoding="utf-8", errors="replace")
            blocks = re.split(r'###\s+', text)
            _SKIP  = {"SIGNAL", "REPORT", "SUMMARY", "FINAL", "DAILY", "NOTE"}
            for block in blocks:
                if not re.search(r'VERDICT.{0,30}APPROVE', block, re.IGNORECASE):
                    continue
                m = re.match(r'([A-Z]{1,5})\b', block.strip())
                if m and m.group(1) not in _SKIP:
                    approved.append(m.group(1))
    except Exception:
        pass

    # ── Read equity + open positions from portfolio snapshot ──────────────────
    equity_str    = "—"
    open_positions: list[str] = []
    try:
        snap_path = Path(vault_path) / "09-Portfolio" / "positions.json"
        if snap_path.exists():
            snap = _json.loads(snap_path.read_text(encoding="utf-8"))
            eq   = snap.get("account", {}).get("equity")
            if eq:
                equity_str = f"${float(eq):,.0f}"
            open_positions = [
                p["symbol"] for p in snap.get("positions", [])
                if float(p.get("qty", 0)) != 0
            ]
    except Exception:
        pass

    # ── Build message ─────────────────────────────────────────────────────────
    err_line = f"\n❌ Failed steps: `{', '.join(failed)}`" if failed else ""
    sig_line = (
        f"✅ Approved: *{', '.join(approved)}*"
        if approved else "❌ No signals approved today"
    )
    pos_line = (
        f"📂 Open positions ({len(open_positions)}): {', '.join(open_positions)}"
        if open_positions else "📂 No open positions"
    )
    msg = (
        f"{ok_icon} *Trading Brain — Daily Loop "
        f"{'Complete' if not failed else 'ERRORS'}*\n"
        f"📅 {date_str}  |  ⏱ {elapsed_str}\n"
        f"📊 {passed}/{total} steps passed{err_line}\n"
        f"{sig_line}\n"
        f"💰 Equity: `{equity_str}`\n"
        f"{pos_line}"
    )

    # ── Send ──────────────────────────────────────────────────────────────────
    try:
        resp = _req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=8,
        )
        if resp.status_code == 200:
            _tprint("📲 Telegram end-of-run summary sent")
        else:
            _tprint(f"⚠️  Telegram summary HTTP {resp.status_code}: {resp.text[:80]}")
    except Exception as _tg_err:
        _tprint(f"⚠️  Telegram summary failed (non-fatal): {_tg_err}")


def main():
    start = datetime.now()

    # ── Market calendar guard — skip weekends and US market holidays ──────────
    # Queries Alpaca's calendar API so public holidays (July 4, Thanksgiving,
    # Christmas, etc.) are handled correctly, not just Mon–Fri weekday check.
    # Guard runs BEFORE the log file is created → no empty logs on skip days.
    try:
        from src.alpaca_broker import AlpacaBroker as _Broker
        if not _Broker().is_trading_day():
            print(f"⏭  {start.strftime('%Y-%m-%d (%A)')} is not a US trading day "
                  f"— daily loop skipped")
            return 0
        print(f"✅ Market calendar: {start.strftime('%Y-%m-%d (%A)')} is a trading day")
    except Exception as _cal_err:
        print(f"⚠️  Market calendar check failed ({_cal_err}) — proceeding anyway")

    # ── Set up file logging ───────────────────────────────────────────────────
    log_dir  = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"daily_{start.strftime('%Y%m%d_%H%M')}.log"
    _log_file = open(log_path, "w", encoding="utf-8")
    _orig_stdout = sys.stdout
    sys.stdout = _Tee(sys.__stdout__, _log_file)

    try:
        _tprint(f"Starting Trading Brain Daily Loop — {start.strftime('%Y-%m-%d %H:%M')}")
        _tprint(f"Log file: {log_path}")
        _tprint(f"Watchlist ({len(WATCHLIST)} tickers): {WATCHLIST}")
        _tprint("=" * 90)

        results = {}

        # ── Phase 0: Outcome tracking — closes the learning loop ─────────────────
        # Runs FIRST so lessons from past trades are in the vault (and therefore
        # in RAG context) before SignalGenerator generates today's signals.
        results["OutcomeTracker"] = run_step(
            "OutcomeTracker → track_outcomes",
            OutcomeTracker().track_outcomes,
        )

        # ── Phase 1a: Parallel data prefetch ─────────────────────────────────────
        # Uses DataScout.prefetch_and_save() which now loads from the 10-year
        # historical CSV as the base (instant, no network) and only fetches the
        # recent delta (last ~10 days) from yfinance.  This is much faster than
        # the old full 2-year network fetch and gives agents 10 years of context.
        _tprint("\n▶  DataScout → PREFETCH (parallel, 10y base)")
        _tprint("=" * 60)
        scout = DataScout()

        def _prefetch(ticker):
            ok = scout.prefetch_and_save(ticker)
            if not ok:
                _tprint(f"   Prefetch failed: {ticker}")
            return ok

        # max_workers=3 — keeps yfinance delta fetches within rate limits
        with ThreadPoolExecutor(max_workers=3) as ex:
            prefetch_ok = dict(zip(WATCHLIST, ex.map(_prefetch, WATCHLIST)))
        _tprint(f"Prefetch done — {sum(prefetch_ok.values())}/{len(WATCHLIST)} tickers cached")

        # ── Earnings cache: fetch once, shared by SignalGenerator + RiskGuardian ─
        # Without this, both agents independently call DataFetcher.get_earnings_date()
        # for every ticker — 2× the yfinance/Polygon API calls for identical data.
        # Warming here makes both agents' earnings checks instant (disk read only).
        _tprint("\n▶  Earnings cache: pre-fetching calendar for all watchlist tickers")
        try:
            from src.earnings_cache import load_or_fetch as _warm_earnings
            _warm_earnings(WATCHLIST, VAULT_PATH)
            _tprint("✅ Earnings cache ready")
        except Exception as _ec_err:
            _tprint(f"⚠️  Earnings cache pre-fetch failed ({_ec_err}) "
                    f"— agents will fall back to individual live fetches")

        # ── Phase 1b: Sequential LLM analysis per ticker (reads from CSV) ───────
        ok = True
        for ticker in WATCHLIST:
            ok &= run_step(f"DataScout → {ticker}", lambda t=ticker: scout.analyze_from_csv(t))
        results["DataScout"] = ok

        # ── Phase 2: News + Sectors in parallel (both use Haiku, independent) ────
        parallel_news = run_parallel([
            ("NewsScout → scan_news",       lambda: NewsScout().scan_news(WATCHLIST)),
            ("SectorScout → scan_sectors",  lambda: SectorScout().scan_sectors()),
        ], max_workers=2)
        results.update(parallel_news)

        # ── Phase 3: Market context ───────────────────────────────────────────────
        # Regime + Volatility can run in parallel (independent data fetches)
        phase3a = run_parallel([
            ("RegimeClassifier",           RegimeClassifier().classify_regime),
            ("VolatilityAgent",            VolatilityAgent().analyze_volatility),
        ], max_workers=2)
        results.update(phase3a)
        # Sentiment + MarketAnalyst run after regime (may read regime output)
        results["SentimentAgent"]   = run_step("SentimentAgent",   SentimentAgent().analyze_sentiment)
        results["MarketAnalyst"]    = run_step("MarketAnalyst",     MarketAnalyst().daily_analysis)

        # ── Phase 3.5: Lightweight regime check (uses 10-year history) ──────────
        # Quick snapshot of current Bull/Bear/Ranging regime per ticker based on
        # 10-year trained data.  Fast — no backtests, just SMA-based labelling.
        results["HistoricalTrainer.regime"] = run_step(
            "HistoricalTrainer → regime_check",
            HistoricalTrainer().run_regime_check,
        )

        # ── best_params.json freshness check ─────────────────────────────────────
        # Warn when optimised strategy parameters are stale — the Optimizer will
        # still run but will use outdated params until train_strategies.py is re-run.
        # Recommended cadence: weekly (market regimes shift, PF rankings change).
        _params_file = Path(__file__).parent / "data" / "historical" / "best_params.json"
        if _params_file.exists():
            _params_age = int(
                (datetime.now() - datetime.fromtimestamp(
                    _params_file.stat().st_mtime
                )).total_seconds() // 86400
            )
            if _params_age > 7:
                _tprint(
                    f"   ⚠️  best_params.json is {_params_age} days old — "
                    f"run train_strategies.py to refresh optimised strategy params"
                )
            else:
                _tprint(f"   ✅ best_params.json is {_params_age} day(s) old — OK")
        else:
            _tprint(
                "   ⚠️  best_params.json not found — Optimizer will use default params. "
                "Run train_strategies.py once to generate optimised params."
            )

        # ── Phase 4: Strategy optimisation ───────────────────────────────────────
        # Optimizer now uses 10-year data + saved best_params.json (if it exists).
        # Run train_strategies.py once to populate best_params.json.
        optimizer = Optimizer()
        results["Optimizer.loop"] = run_step(
            "Optimizer → run_optimization_loop",
            lambda: optimizer.run_optimization_loop(tickers=WATCHLIST),
        )
        results["Optimizer.rank"] = run_step("Optimizer → rank_strategies", optimizer.rank_strategies)

        # ── Dynamically select the top-ranked Tier-1 strategy to refine ─────────
        top_strategy = _read_top_strategy(VAULT_PATH)
        results["Strategist"] = run_step(
            f"Strategist → refine {top_strategy}",
            lambda s=top_strategy: Strategist().refine_strategy(s),
        )

        # ── Phase 5: Strategy evaluation (Critic + MetaEval in parallel) ─────────
        # Critic reviews the SAME strategy that Strategist just refined (top_strategy),
        # not a hardcoded fallback — the two agents now always stay in sync.
        eval_results = run_parallel([
            ("MetaEvaluator → evaluate_performance", MetaEvaluator().evaluate_performance),
            (f"Critic → review {top_strategy}.md",
             lambda s=top_strategy: Critic().review_note("02-Strategies", f"{s}.md")),
        ], max_workers=2)
        results.update(eval_results)

        # ── Mid-run RAG refresh ───────────────────────────────────────────────────
        # _indexed_once = True after the first agent __init__ prevents agents from
        # re-indexing the vault on every instantiation — good for performance.
        # BUT it means vault files written during Phases 1-5 (DataScout analysis,
        # NewsScout, RegimeClassifier, Sentiment, Strategist, etc.) are invisible
        # to SignalGenerator and RiskGuardian's RAG retrieve() calls.
        # A single explicit refresh here catches everything written so far this run.
        _tprint("\n▶  RAG refresh — indexing Phase 1-5 vault writes for Signal + Risk agents")
        try:
            from src.rag_memory import RAGMemory
            RAGMemory().refresh()
            _tprint("✅ RAG index updated")
        except Exception as _rag_err:
            _tprint(f"⚠️  RAG refresh failed (non-fatal): {_rag_err}")

        # ── Phase 6: Signals + Risk (sequential — RiskGuardian reads SignalGen output) ──
        results["SignalGenerator"] = run_step(
            "SignalGenerator → generate_signals",
            lambda: SignalGenerator().generate_signals(tickers=WATCHLIST),
        )
        results["RiskGuardian"] = run_step(
            "RiskGuardian → daily_risk_sweep",
            RiskGuardian().daily_risk_sweep,
        )

        # ── Critic reviews today's signals + risk sweep (catch bad signals early) ─
        today        = datetime.now().strftime("%Y-%m-%d")
        today_short  = datetime.now().strftime("%Y%m%d")
        critic       = Critic()
        for folder, fname in [
            ("03-Trade-Journal", f"signals_{today}.md"),
            ("06-Playbooks",     f"RISK_SWEEP_{today_short}.md"),
        ]:
            run_step(f"Critic → review {fname}",
                     lambda f=folder, n=fname: critic.review_note(f, n))

        # ── Phase 7: Execute approved signals via Alpaca paper trading ───────────
        results["ExecutionAgent"] = run_step(
            "ExecutionAgent → execute_approved_signals",
            ExecutionAgent().execute_approved_signals,
        )

        # ── Phase 8: P&L + portfolio snapshot (after execution) ──────────────────
        results["PnLTracker"] = run_step("PnLTracker → track_pnl", PnLTracker().track_pnl)

        # ── Summary ───────────────────────────────────────────────────────────────
        elapsed = int((datetime.now() - start).total_seconds())
        passed  = sum(v for v in results.values())
        failed  = [k for k, v in results.items() if not v]

        _tprint(f"\n{'='*90}")
        status = "DAILY LOOP COMPLETE" if not failed else "DAILY LOOP FINISHED WITH ERRORS"
        _tprint(f"{'OK  ' if not failed else 'WARN'} {status}")
        _tprint(f"   {passed}/{len(results)} steps passed  |  {elapsed}s elapsed"
                f"  ({elapsed//60}m {elapsed%60}s)")
        if failed:
            _tprint(f"   Failed: {', '.join(failed)}")
        _tprint(f"   Log saved to: {log_path}")
        _tprint(f"   Open vault/ in Obsidian to review results")
        _tprint(f"{'='*90}")

        # ── Telegram end-of-run digest ────────────────────────────────────────
        _send_loop_summary(results, failed, elapsed, start, VAULT_PATH)

        return 0 if not failed else 1

    finally:
        # Always restore stdout and close log file — even if an exception escaped
        sys.stdout = _orig_stdout
        _log_file.flush()
        _log_file.close()


if __name__ == "__main__":
    sys.exit(main())
