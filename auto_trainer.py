"""
auto_trainer.py
---------------
Continuous self-training daemon for Trading Brain.

Runs train_strategies.py on a configurable loop — 24/7, unattended.
Windows Task Scheduler starts this script at boot; it runs forever until
the machine shuts down or you kill it.

Configuration (env vars, all optional):
  AUTO_TRAIN_INTERVAL_HOURS   How many hours to sleep between training runs.
                               Default: 6  (4 full training cycles per day)
  AUTO_TRAIN_TICKERS          Comma-separated ticker override, e.g. AAPL,TSLA
                               Default: uses WATCHLIST from config.py
  AUTO_TRAIN_LOG_DIR          Directory for log files. Default: logs/

Usage:
  Start now (foreground, Ctrl+C to stop):
      .venv\\Scripts\\python auto_trainer.py

  Start in background (detached, survives terminal close):
      pythonw auto_trainer.py          ← no console window
      start /B .venv\\Scripts\\python auto_trainer.py

  Windows Task Scheduler (set up by setup_auto_trainer.bat):
      Runs at system startup, keeps running until shutdown.
"""

import sys
import os
import signal
import subprocess
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

# ── Auto-activate venv ─────────────────────────────────────────────────────────
_ROOT       = Path(__file__).parent
_VENV_PY    = _ROOT / ".venv" / "Scripts" / "python.exe"
_PYTHONW    = _ROOT / ".venv" / "Scripts" / "pythonw.exe"

if _VENV_PY.exists() and Path(sys.executable).resolve() != _VENV_PY.resolve():
    # Re-launch ourselves under the venv interpreter
    result = subprocess.run([str(_VENV_PY)] + sys.argv)
    sys.exit(result.returncode)

# ── Config ─────────────────────────────────────────────────────────────────────
INTERVAL_HOURS = float(os.getenv("AUTO_TRAIN_INTERVAL_HOURS", "6"))
LOG_DIR        = Path(os.getenv("AUTO_TRAIN_LOG_DIR", str(_ROOT / "logs")))
LOCK_FILE      = LOG_DIR / "auto_trainer.lock"
TRAIN_SCRIPT   = _ROOT / "train_strategies.py"

LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Graceful shutdown flag ─────────────────────────────────────────────────────
_shutdown = False

def _on_signal(signum, frame):
    global _shutdown
    _shutdown = True
    _log("Shutdown signal received — will stop after current run completes.")

signal.signal(signal.SIGTERM, _on_signal)
try:
    signal.signal(signal.SIGBREAK, _on_signal)   # Windows Ctrl+Break
except AttributeError:
    pass

# ── Logging ────────────────────────────────────────────────────────────────────
_log_file = None

def _open_log():
    global _log_file
    if _log_file:
        _log_file.close()
    log_path = LOG_DIR / f"auto_trainer_{datetime.now().strftime('%Y%m%d')}.log"
    _log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    return log_path

def _log(msg: str):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if _log_file and not _log_file.closed:
        _log_file.write(line + "\n")

# ── Lock file (prevents overlapping runs) ─────────────────────────────────────
def _acquire_lock() -> bool:
    """Return True if we successfully acquired the run lock."""
    try:
        pid_data = LOCK_FILE.read_text() if LOCK_FILE.exists() else ""
        if pid_data.strip().isdigit():
            old_pid = int(pid_data.strip())
            # Check if that process is still alive
            try:
                import ctypes
                handle = ctypes.windll.kernel32.OpenProcess(0x0400, False, old_pid)
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    _log(f"Another training run (PID {old_pid}) is already active — skipping this cycle.")
                    return False
            except Exception:
                pass  # If we can't check, proceed anyway
        LOCK_FILE.write_text(str(os.getpid()))
        return True
    except Exception as e:
        _log(f"Lock file warning: {e} — proceeding without lock.")
        return True

def _release_lock():
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except Exception:
        pass

# ── Training cycle ─────────────────────────────────────────────────────────────
_STATUS_FILE = LOG_DIR / "auto_trainer_status.json"

def _write_status(state: str, run_count: int, last_run: str, next_run: str,
                  last_duration_s: float = 0, last_error: str = ""):
    try:
        _STATUS_FILE.write_text(json.dumps({
            "state":            state,
            "run_count":        run_count,
            "last_run":         last_run,
            "next_run":         next_run,
            "last_duration_s":  round(last_duration_s, 1),
            "interval_hours":   INTERVAL_HOURS,
            "last_error":       last_error,
            "pid":              os.getpid(),
        }, indent=2), encoding="utf-8")
    except Exception:
        pass

def run_training_cycle(run_count: int) -> tuple[bool, float, str]:
    """
    Invoke train_strategies.py as a subprocess.
    Returns (success, duration_seconds, error_message).
    """
    if not TRAIN_SCRIPT.exists():
        return False, 0.0, f"train_strategies.py not found at {TRAIN_SCRIPT}"

    start   = time.monotonic()
    env     = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # Pipe output to the log file so it's captured even when running headless
    log_path = LOG_DIR / f"train_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    _log(f"Run #{run_count} starting → log: {log_path.name}")

    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as fout:
            proc = subprocess.run(
                [str(_VENV_PY), str(TRAIN_SCRIPT)],
                stdout=fout,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=str(_ROOT),
            )
        duration = time.monotonic() - start
        if proc.returncode == 0:
            _log(f"Run #{run_count} COMPLETE — {duration/60:.1f} min  (exit 0)")
            return True, duration, ""
        else:
            err = f"Exit code {proc.returncode}"
            _log(f"Run #{run_count} FAILED — {err}  ({duration/60:.1f} min)")
            return False, duration, err
    except Exception as exc:
        duration = time.monotonic() - start
        _log(f"Run #{run_count} EXCEPTION — {exc}")
        return False, duration, str(exc)

# ── Main loop ──────────────────────────────────────────────────────────────────
def main():
    log_path = _open_log()
    _log("=" * 68)
    _log("  Trading Brain — Auto-Trainer Daemon  STARTING")
    _log(f"  PID            : {os.getpid()}")
    _log(f"  Train script   : {TRAIN_SCRIPT}")
    _log(f"  Interval       : every {INTERVAL_HOURS:.1f} hours")
    _log(f"  Log dir        : {LOG_DIR}")
    _log(f"  Status file    : {_STATUS_FILE.name}")
    _log("=" * 68)
    _log("  Ctrl+C or SIGTERM for clean shutdown after current run.")
    _log("")

    run_count    = 0
    last_success = None
    last_error   = ""

    while not _shutdown:
        # Roll log file at midnight
        _open_log()

        # Attempt to acquire lock
        if not _acquire_lock():
            # Another process is training — wait 10 min and retry
            _log(f"Waiting 10 min for other run to complete…")
            _write_status("waiting_for_lock", run_count,
                          last_success or "never",
                          (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M"),
                          last_error=last_error)
            _sleep_with_interrupt(600)
            continue

        run_count += 1
        _write_status("running", run_count,
                      last_success or "never",
                      (datetime.now() + timedelta(hours=INTERVAL_HOURS)).strftime("%Y-%m-%d %H:%M"))

        success, duration, error = run_training_cycle(run_count)
        _release_lock()

        if success:
            last_success = datetime.now().strftime("%Y-%m-%d %H:%M")
            last_error   = ""
        else:
            last_error = error

        if _shutdown:
            break

        next_run = datetime.now() + timedelta(hours=INTERVAL_HOURS)
        _log(f"Next run at {next_run.strftime('%Y-%m-%d %H:%M')} "
             f"(sleeping {INTERVAL_HOURS:.0f}h)…")
        _log("")

        _write_status("sleeping", run_count,
                      last_success or "never",
                      next_run.strftime("%Y-%m-%d %H:%M"),
                      last_duration_s=duration,
                      last_error=last_error)

        _sleep_with_interval(INTERVAL_HOURS * 3600)

    _log("Auto-trainer daemon stopped cleanly.")
    _write_status("stopped", run_count,
                  last_success or "never", "—",
                  last_error=last_error)
    if _log_file:
        _log_file.close()

def _sleep_with_interrupt(seconds: float):
    """Sleep seconds but wake early if _shutdown is set."""
    deadline = time.monotonic() + seconds
    while not _shutdown and time.monotonic() < deadline:
        time.sleep(min(5, deadline - time.monotonic()))

def _sleep_with_interval(seconds: float):
    """Sleep the full interval, waking every 30 s to check _shutdown."""
    deadline = time.monotonic() + seconds
    while not _shutdown and time.monotonic() < deadline:
        time.sleep(min(30, deadline - time.monotonic()))


if __name__ == "__main__":
    main()
