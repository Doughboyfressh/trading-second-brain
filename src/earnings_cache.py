# src/earnings_cache.py
"""
Shared earnings calendar cache — written once per day, read by multiple agents.

Problem it solves
-----------------
Both SignalGenerator._earnings_flags() and RiskGuardian._earnings_block()
previously called DataFetcher.get_earnings_date() independently for every
ticker, doubling the yfinance/Polygon API calls for the exact same data.

How it works
------------
1. The orchestrator (run_daily_loop.py) calls load_or_fetch(WATCHLIST, VAULT_PATH)
   after Phase 1a to warm the cache for all tickers in one shot.
2. SignalGenerator and RiskGuardian call get_upcoming_flags() which reads the
   cached file — instant, no network.
3. Cache file is named earnings_cache_YYYYMMDD.json, so it's automatically
   fresh each day and stale files are simply ignored.
4. If a ticker is missing from the cache (e.g. a new watchlist addition),
   load_or_fetch() fetches only that ticker and appends it to the cache.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


# ── Internal helpers ──────────────────────────────────────────────────────────

def _cache_path(vault_path: str) -> Path:
    """Return today's cache file path inside vault/07-Research/."""
    today     = date.today().strftime("%Y%m%d")
    cache_dir = Path(vault_path) / "07-Research"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"earnings_cache_{today}.json"


# ── Public API ────────────────────────────────────────────────────────────────

def load_or_fetch(tickers: list[str], vault_path: str) -> dict[str, str | None]:
    """
    Return {ticker: "YYYY-MM-DD" or None} for all *tickers*.

    Steps
    -----
    1. Read today's cache from vault/07-Research/earnings_cache_YYYYMMDD.json.
    2. Fetch only tickers that are absent from the cache.
    3. Write the updated cache so subsequent callers pay zero API cost.

    Network calls
    -------------
    Warm path (orchestrator already ran): 0 calls.
    Cold path (first caller):             1 call per ticker in *tickers*.
    Partial miss (new watchlist ticker):  1 call per missing ticker.
    """
    path = _cache_path(vault_path)

    # Load existing cache — may be empty or partial
    cached: dict[str, str | None] = {}
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass  # corrupt cache — rebuild below

    # Short-circuit if every requested ticker is already cached
    missing = [t for t in tickers if t not in cached]
    if not missing:
        return cached

    # Fetch only the missing tickers
    from src.data_fetcher import DataFetcher
    fetcher = DataFetcher()
    for ticker in missing:
        try:
            cached[ticker] = fetcher.get_earnings_date(ticker)
        except Exception:
            cached[ticker] = None

    # Persist updated cache for this session
    try:
        path.write_text(
            json.dumps(cached, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass  # non-fatal — agents can still use the in-memory dict

    return cached


def get_upcoming_flags(tickers: list[str], vault_path: str,
                       window_days: int = 5) -> dict[str, str]:
    """
    Return {ticker: "YYYY-MM-DD"} for tickers that have confirmed earnings
    within *window_days* calendar days from today.

    Tickers with no earnings data are silently excluded.
    """
    all_dates = load_or_fetch(tickers, vault_path)
    today     = date.today()
    cutoff    = today + timedelta(days=window_days)
    flags: dict[str, str] = {}
    for ticker, ed in all_dates.items():
        if not ed:
            continue
        try:
            ed_date = date.fromisoformat(str(ed)[:10])
            if today <= ed_date <= cutoff:
                flags[ticker] = str(ed)[:10]
        except (ValueError, TypeError):
            pass
    return flags
