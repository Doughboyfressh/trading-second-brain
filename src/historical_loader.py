# src/historical_loader.py
"""
HistoricalLoader — central data hub for the Trading Brain.

Loads 10-year daily OHLCV from data/historical/*.csv (pre-downloaded via
download_history.py).  Merges with the vault's recent CSV to stay current,
then falls back to a live network fetch if neither file exists.

All agents should import from here instead of fetching from the network
every run — this is both faster and gives 10x more historical context
(2513 bars vs ~730 for the old 2-year default).

Public API
----------
    load_historical(ticker, years=10) -> pd.DataFrame
        One ticker, returns df with timestamp + OHLCV + indicators.

    load_all_historical(tickers=None, years=10) -> dict[str, pd.DataFrame]
        All tickers in parallel; returns {ticker: df}.
"""
from __future__ import annotations

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

_BASE     = Path(__file__).parent.parent
_HIST_DIR = _BASE / "data" / "historical"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_vault_csv_path(ticker: str) -> Path:
    """Return the vault CSV path without importing VaultManager at module level
    (avoids circular imports — VaultManager imports config which may not be ready)."""
    from config import VAULT_PATH
    return Path(VAULT_PATH) / "01-Assets" / "Stocks" / f"{ticker}.csv"


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardise column names and parse the date/timestamp column.
    Returns a df with lowercase columns and a 'timestamp' datetime column.
    """
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # Coerce the date column to a consistent 'timestamp' name
    if "timestamp" not in df.columns:
        if "date" in df.columns:
            df = df.rename(columns={"date": "timestamp"})
        elif "index" in df.columns:
            df = df.rename(columns={"index": "timestamp"})
        else:
            # Try resetting the index if it looks like a datetime index
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            if "index" in df.columns:
                df = df.rename(columns={"index": "timestamp"})

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=False)
        # Drop timezone info so everything is naive UTC-equivalent
        if hasattr(df["timestamp"].dtype, "tz") and df["timestamp"].dtype.tz is not None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        df = df.dropna(subset=["timestamp"])

    return df


def _keep_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the core OHLCV columns (strip any pre-existing indicators)."""
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    present = [c for c in cols if c in df.columns]
    return df[present].copy()


# ── Public API ────────────────────────────────────────────────────────────────

def load_historical(ticker: str,
                    years: int = 10,
                    compute_indicators: bool = True) -> pd.DataFrame:
    """
    Load historical OHLCV for *ticker*.

    Data source priority
    --------------------
    1. ``data/historical/{ticker}_10y.csv``  — up to 10 years of daily bars
    2. ``vault/01-Assets/Stocks/{ticker}.csv`` — vault CSV appended for freshness
    3. Live yfinance / Polygon fetch            — last resort

    Parameters
    ----------
    ticker              : e.g. ``"AAPL"``
    years               : clip to last N years (default 10)
    compute_indicators  : attach RSI / MACD / BB / ATR / SMA columns (default True)

    Returns
    -------
    pd.DataFrame with columns ``timestamp, open, high, low, close, volume``
    plus indicators when ``compute_indicators=True``.  Empty if all sources fail.
    """
    from src.data_fetcher import DataFetcher

    df = pd.DataFrame()

    # ── 1. 10-year pre-downloaded CSV ─────────────────────────────────────────
    hist_path = _HIST_DIR / f"{ticker}_10y.csv"
    if hist_path.exists():
        try:
            raw = pd.read_csv(str(hist_path))
            raw = _normalize_df(raw)
            raw = _keep_ohlcv(raw)
            if not raw.empty and len(raw) >= 100:
                df = raw.sort_values("timestamp").reset_index(drop=True)
                print(f"   [Loader] {ticker}: {len(df)} bars from 10y CSV")
        except Exception as e:
            print(f"   [Loader] {ticker}: 10y CSV read error — {e}")

    # ── 2. Extend with vault CSV (recent bars not yet in the 10y snapshot) ────
    vault_path = _get_vault_csv_path(ticker)
    if vault_path.exists():
        try:
            vault_raw = pd.read_csv(str(vault_path))
            vault_raw = _normalize_df(vault_raw)
            vault_raw = _keep_ohlcv(vault_raw)

            if not vault_raw.empty:
                if df.empty:
                    df = vault_raw.sort_values("timestamp").reset_index(drop=True)
                    print(f"   [Loader] {ticker}: using vault CSV ({len(df)} bars)")
                else:
                    # Only append bars NEWER than the 10y CSV's last date
                    last_dt   = df["timestamp"].max()
                    new_rows  = vault_raw[vault_raw["timestamp"] > last_dt].copy()
                    if not new_rows.empty:
                        df = pd.concat([df, new_rows], ignore_index=True)
                        df = df.sort_values("timestamp").reset_index(drop=True)
                        print(f"   [Loader] {ticker}: +{len(new_rows)} recent bars from vault")
        except Exception as e:
            print(f"   [Loader] {ticker}: vault extend error — {e}")

    # ── 3. Live network fetch (fallback) ──────────────────────────────────────
    if df.empty:
        print(f"   [Loader] {ticker}: no CSV — live fetch fallback")
        fetcher = DataFetcher()
        df = fetcher.fetch_historical(ticker, days_back=years * 365 + 30)
        return df  # DataFetcher already computes indicators

    # ── Clip to requested window ──────────────────────────────────────────────
    if years:
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
        df = df[df["timestamp"] >= cutoff].copy()

    df = df.sort_values("timestamp").reset_index(drop=True)

    # ── Compute indicators on the full history ────────────────────────────────
    if compute_indicators and not df.empty and len(df) >= 30:
        df = DataFetcher.compute_indicators(df)

    return df


def load_all_historical(tickers: list[str] | None = None,
                        years: int = 10,
                        max_workers: int = 4) -> dict[str, pd.DataFrame]:
    """
    Load historical data for all *tickers* (parallel I/O).

    Returns
    -------
    ``{ticker: df}`` — only includes tickers with non-empty results.
    """
    from config import WATCHLIST
    if tickers is None:
        tickers = WATCHLIST

    result: dict[str, pd.DataFrame] = {}

    def _load(t):
        return t, load_historical(t, years=years)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_load, t): t for t in tickers}
        for fut in as_completed(futures):
            ticker, df = fut.result()
            if not df.empty:
                result[ticker] = df

    return result


def load_performance_stats() -> dict:
    """
    Load the consolidated per-session win/loss and profit statistics.

    Written by HistoricalTrainer.run_full_benchmark() after each training run.
    Contains keys: by_session, by_strategy, by_ticker, top10_by_pf.

    Returns empty dict if the file hasn't been generated yet (run
    train_strategies.py to populate it).
    """
    perf_path = _HIST_DIR / "performance_stats.json"
    if not perf_path.exists():
        return {}
    try:
        import json
        return json.loads(perf_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_best_params(strategy_name: str | None = None) -> dict:
    """
    Load the optimized parameter file saved by HistoricalTrainer.

    Returns the full dict (keyed by strategy then ticker) if *strategy_name* is None,
    or just ``{ticker: {param: value, ...}}`` for a specific strategy.
    """
    params_path = _HIST_DIR / "best_params.json"
    if not params_path.exists():
        return {}
    try:
        import json
        data = json.loads(params_path.read_text(encoding="utf-8"))
        if strategy_name:
            return data.get("strategies", {}).get(strategy_name, {})
        return data
    except Exception:
        return {}
