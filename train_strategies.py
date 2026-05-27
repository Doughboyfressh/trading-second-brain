"""
train_strategies.py
-------------------
Standalone historical training runner for the Trading Brain.

What it does
------------
1. Loads 10-year OHLCV for all 8 watchlist tickers from data/historical/
2. Runs all 8 strategies (5 original + 3 new) on every ticker (walk-forward)
3. Grid-searches optimal parameters for each strategy × ticker
4. Detects historical Bull/Bear/Ranging regimes and maps strategy performance
5. Calls Claude Sonnet with all findings to:
   - Rank strategies by deployment readiness
   - Identify regime-specific best strategies
   - Propose 3 new strategy variants with full entry/exit rules
6. Saves best_params.json to data/historical/ (used by the daily loop)
7. Writes TRAINING_REPORT to vault/05-Performance/

Run from the project root:
    .venv/Scripts/python train_strategies.py

Expected runtime: 10-25 minutes depending on CPU speed.

Run periodically (e.g. weekly or monthly) to re-optimise as new data
accumulates. The daily loop automatically picks up best_params.json
on its next run.
"""

import sys
import os
from pathlib import Path

# ── Auto-activate venv ────────────────────────────────────────────────────────
_venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    import subprocess
    sys.exit(subprocess.run([str(_venv_python)] + sys.argv).returncode)

# ── Force UTF-8 output ────────────────────────────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime

# Validate env before loading agents (config.py raises if missing)
try:
    from config import WATCHLIST
except EnvironmentError as e:
    print(f"\nERROR: {e}")
    sys.exit(1)

from src.agents.historical_trainer import HistoricalTrainer
from src.historical_loader import _HIST_DIR


def main():
    start = datetime.now()

    print(f"\n{'='*70}")
    print(f"  Trading Brain — Strategy Historical Trainer")
    print(f"  Date     : {start.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Tickers  : {WATCHLIST}")
    print(f"  Data dir : {_HIST_DIR}")
    print(f"{'='*70}\n")

    # Validate that 10-year CSVs exist
    missing = [t for t in WATCHLIST
               if not (_HIST_DIR / f"{t}_10y.csv").exists()]
    if missing:
        print(f"WARNING: Missing 10y CSVs for: {missing}")
        print("         Run download_history.py first to download historical data.")
        print("         Training will use vault CSVs / live fetch for these tickers.\n")

    # Run full training pipeline
    trainer = HistoricalTrainer()
    trainer.train_all(tickers=WATCHLIST)

    elapsed = int((datetime.now() - start).total_seconds())

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  TRAINING COMPLETE")
    print(f"  Time elapsed : {elapsed // 60}m {elapsed % 60}s")
    print(f"  Best params  : {_HIST_DIR / 'best_params.json'}")

    params_path = _HIST_DIR / "best_params.json"
    if params_path.exists():
        import json
        try:
            data = json.loads(params_path.read_text(encoding="utf-8"))
            best_by_ticker = data.get("best_by_ticker", {})
            regime_best    = data.get("regime_best_strategy", {})

            if best_by_ticker:
                print("\n  Best strategy per ticker (OOS-validated):")
                for ticker, info in sorted(best_by_ticker.items()):
                    print(f"    {ticker:<6} -> {info['strategy']:<22} "
                          f"Calmar={info.get('oos_calmar', 0):.2f}")

            if regime_best:
                print("\n  Best strategy per market regime:")
                for regime, strat in regime_best.items():
                    print(f"    {regime:<10} -> {strat}")

        except Exception as e:
            print(f"  (Could not parse best_params.json: {e})")

    print(f"\n  Next step: run the daily loop to use these optimised strategies.")
    print(f"  run_daily_loop.py will auto-load best_params.json on startup.")
    print(f"{'='*70}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
