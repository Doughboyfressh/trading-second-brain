"""
download_history.py
-------------------
Downloads 10 years of daily OHLCV history for the Trading Brain watchlist
using yfinance and saves each ticker as a CSV in data/historical/.

Run from the project root:
    .venv/Scripts/python download_history.py
"""

import sys
import time
import random
from pathlib import Path
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
TICKERS = ["AAPL", "TSLA", "NVDA", "AMD", "GOOGL", "MSFT", "AMZN", "META"]
OUT_DIR = Path(__file__).parent / "data" / "historical"
OUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = (datetime.now() - timedelta(days=365 * 10 + 3)).strftime("%Y-%m-%d")
END_DATE   = datetime.now().strftime("%Y-%m-%d")

# ── Helpers ───────────────────────────────────────────────────────────────────
def standardize(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Flatten MultiIndex columns, lower-case, ensure Date column."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    # yfinance returns the date as the index
    if "date" not in df.columns:
        df = df.reset_index()
        df = df.rename(columns={"index": "date", "datetime": "date"})
    df.columns = [c.lower() for c in df.columns]
    # drop adj close / dividends / stock splits if present
    drop_cols = [c for c in df.columns if c not in
                 ("date", "open", "high", "low", "close", "volume")]
    df.drop(columns=drop_cols, errors="ignore", inplace=True)
    df["ticker"] = ticker
    df["date"]   = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("date").reset_index(drop=True)
    return df


def fetch_ticker(ticker: str, retries: int = 4) -> pd.DataFrame | None:
    for attempt in range(retries):
        try:
            if attempt > 0:
                wait = (2 ** attempt) + random.uniform(1, 3)
                print(f"   Retry {attempt}/{retries-1} for {ticker} - waiting {wait:.1f}s")
                time.sleep(wait)
            else:
                time.sleep(random.uniform(0.3, 1.2))   # polite initial delay

            t  = yf.Ticker(ticker)
            df = t.history(start=START_DATE, end=END_DATE,
                           interval="1d", auto_adjust=True, actions=False)

            if df is None or df.empty:
                # fallback: yf.download
                time.sleep(random.uniform(0.5, 1.5))
                df = yf.download(ticker, start=START_DATE, end=END_DATE,
                                 interval="1d", progress=False, auto_adjust=True)

            if df is not None and not df.empty:
                return standardize(df, ticker)

        except Exception as e:
            err = str(e)
            if "400" in err or "429" in err or "Too Many" in err:
                wait = (2 ** (attempt + 1)) + random.uniform(1, 4)
                print(f"   Rate-limited for {ticker} - backing off {wait:.1f}s")
                time.sleep(wait)
            else:
                print(f"   Non-retryable error for {ticker}: {e}")
                break
    return None


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  Trading Brain - 10-Year History Downloader")
    print(f"  Range : {START_DATE} to {END_DATE}")
    print(f"  Output: {OUT_DIR}")
    print(f"{'='*60}\n")

    results = {}
    for ticker in TICKERS:
        print(f"Fetching {ticker}...")
        df = fetch_ticker(ticker)
        if df is not None and not df.empty:
            out_path = OUT_DIR / f"{ticker}_10y.csv"
            df.to_csv(out_path, index=False)
            rows = len(df)
            first = df["date"].iloc[0]
            last  = df["date"].iloc[-1]
            size  = out_path.stat().st_size / 1024
            print(f"   OK {ticker}: {rows} bars  |  {first} to {last}  |  {size:.1f} KB")
            results[ticker] = {"rows": rows, "first": first, "last": last,
                               "file": str(out_path), "kb": round(size, 1)}
        else:
            print(f"   FAILED {ticker}: No data returned")
            results[ticker] = None

    # ── Summary report ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  Download Summary")
    print(f"{'='*60}")
    ok  = [t for t, v in results.items() if v]
    err = [t for t, v in results.items() if not v]
    for t in ok:
        r = results[t]
        print(f"  OK {t:<6}  {r['rows']:>4} bars   {r['first']} to {r['last']}   {r['kb']} KB")
    for t in err:
        print(f"  FAILED {t}")
    print(f"\n  {len(ok)}/{len(TICKERS)} tickers saved to {OUT_DIR}\n")

    # ── Write manifest ──────────────────────────────────────────────────────
    manifest_path = OUT_DIR / "manifest.txt"
    with open(manifest_path, "w") as f:
        f.write(f"Trading Brain — Historical Data Manifest\n")
        f.write(f"Generated : {datetime.now().isoformat()}\n")
        f.write(f"Date range: {START_DATE} → {END_DATE}\n\n")
        for t in TICKERS:
            r = results.get(t)
            if r:
                f.write(f"{t}: {r['rows']} bars | {r['first']} → {r['last']} | {r['kb']} KB\n")
            else:
                f.write(f"{t}: FAILED\n")
    print(f"  Manifest written: {manifest_path}\n")
    return 0 if not err else 1


if __name__ == "__main__":
    sys.exit(main())
