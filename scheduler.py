# scheduler.py
"""
Trading Brain Scheduler — keeps the daily loop running on a market-day schedule.

Runs run_daily_loop.py automatically at the configured time each weekday.
Skips weekends.  Keeps a persistent log of every scheduled run.

Usage:
    python scheduler.py              # uses RUN_TIME from .env (default 08:45 ET)
    python scheduler.py --now        # run immediately then resume schedule
    python scheduler.py --time 09:00 # override run time for this session

Keep this script running in the background (minimised terminal or as a service).
Stop it any time with Ctrl+C — the next day it will pick up on schedule.
"""

import sys
import os
import time
import subprocess
import argparse
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

# Auto-relaunch with venv Python if running outside it
_venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    sys.exit(subprocess.run([str(_venv_python)] + sys.argv).returncode)

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
# Set TRADING_RUN_TIME=HH:MM in .env to change the default run time.
# All times are US/Eastern (handles EST/EDT automatically).
_DEFAULT_RUN_TIME = os.getenv("TRADING_RUN_TIME", "08:45")   # 08:45 ET = ~45 min pre-market

ET = ZoneInfo("America/New_York")
PROJECT_ROOT = Path(__file__).parent


# ── Logging ───────────────────────────────────────────────────────────────────
def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    # Append to scheduler log (separate from daily run logs)
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "scheduler.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _is_weekday() -> bool:
    """Return True if today is Monday–Friday in Eastern time."""
    return datetime.now(ET).weekday() < 5   # 0=Mon … 4=Fri


def _next_run_dt(run_time_str: str) -> datetime:
    """
    Return the next datetime (ET, tz-aware) when the loop should fire.
    If today is a weekday AND the run time hasn't passed yet → today.
    Otherwise → next weekday at run_time_str.
    """
    h, m = map(int, run_time_str.split(":"))
    now   = datetime.now(ET)
    today = now.replace(hour=h, minute=m, second=0, microsecond=0)

    candidate = today
    # Wind forward until we land on a future weekday slot
    while True:
        if candidate > now and candidate.weekday() < 5:
            return candidate
        candidate = candidate.replace(
            hour=h, minute=m, second=0, microsecond=0
        )
        # Advance by one day
        from datetime import timedelta
        candidate = candidate + timedelta(days=1)


def _run_daily_loop() -> int:
    """Spawn run_daily_loop.py as a subprocess; return its exit code."""
    _log("▶  Launching run_daily_loop.py …")
    result = subprocess.run(
        [str(_venv_python if _venv_python.exists() else sys.executable),
         str(PROJECT_ROOT / "run_daily_loop.py")],
        cwd=str(PROJECT_ROOT),
    )
    code = result.returncode
    status = "✅ COMPLETED" if code == 0 else f"⚠️  FINISHED WITH ERRORS (exit {code})"
    _log(f"{status}")
    return code


# ── Main scheduler loop ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Trading Brain daily scheduler")
    parser.add_argument("--time", default=_DEFAULT_RUN_TIME,
                        help="Run time HH:MM ET (default: %(default)s)")
    parser.add_argument("--now", action="store_true",
                        help="Fire the daily loop immediately, then resume schedule")
    args = parser.parse_args()

    run_time = args.time
    # Validate format
    try:
        h, m = map(int, run_time.split(":"))
        assert 0 <= h <= 23 and 0 <= m <= 59
    except Exception:
        print(f"Invalid --time '{run_time}'. Use HH:MM format (e.g. 08:45)")
        sys.exit(1)

    _log("=" * 60)
    _log(f"Trading Brain Scheduler started")
    _log(f"Scheduled run time : {run_time} ET  (weekdays only)")
    _log(f"Project root       : {PROJECT_ROOT}")
    _log("Press Ctrl+C to stop")
    _log("=" * 60)

    # Optionally fire immediately
    if args.now:
        _log("--now flag: running daily loop immediately …")
        _run_daily_loop()

    # Main wait-and-fire loop
    while True:
        next_dt = _next_run_dt(run_time)
        wait_s  = (next_dt - datetime.now(ET)).total_seconds()
        day_str = next_dt.strftime("%A %Y-%m-%d")

        _log(f"Next run: {day_str} at {run_time} ET  "
             f"(in {int(wait_s//3600)}h {int((wait_s%3600)//60)}m)")

        # Sleep in 60-second ticks so Ctrl+C is responsive
        while True:
            remaining = (next_dt - datetime.now(ET)).total_seconds()
            if remaining <= 0:
                break
            # Print a heartbeat every 30 minutes so you can see the process is alive
            if int(remaining) % 1800 == 0 and remaining > 60:
                mins = int(remaining // 60)
                _log(f"⏳ Waiting … {mins}m until next run")
            time.sleep(min(60, max(1, remaining)))

        # Time to run — double-check it's still a weekday (DST/date-change edge case)
        if _is_weekday():
            _run_daily_loop()
        else:
            _log(f"Skipping — {datetime.now(ET).strftime('%A')} is not a trading day")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _log("\nScheduler stopped by user (Ctrl+C).")
        sys.exit(0)
