# src/data_fetcher.py
from polygon import RESTClient
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, OrderType
import pandas as pd
import numpy as np
import threading
import time
import random
from datetime import datetime
from config import POLYGON_API_KEY, ALPACA_API_KEY, ALPACA_SECRET_KEY

# ── Module-level semaphore: caps concurrent Yahoo Finance requests ─────────────
# Yahoo rate-blocks when hit with many simultaneous requests → 400 errors.
# This ensures at most 2 threads call yfinance at the same time, with a small
# random jitter between them to avoid synchronized bursts.
_YF_SEMAPHORE = threading.Semaphore(2)
_YF_JITTER_MAX = 1.5   # max extra seconds of random delay between Yahoo requests


class DataFetcher:
    def __init__(self):
        self.polygon = RESTClient(api_key=POLYGON_API_KEY)
        self.alpaca  = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

    # ── Column standardisation ────────────────────────────────────────────────
    def _standardize_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        # Polygon short names
        col_map = {"t":"timestamp","o":"open","h":"high","l":"low",
                   "c":"close","v":"volume","vw":"vwap","n":"transactions"}
        for old, new in col_map.items():
            if old in df.columns:
                df[new] = df[old]
                if old != new:
                    df.drop(columns=[old], inplace=True, errors="ignore")
        # yfinance capitalised names
        if "Date" in df.columns:
            df = df.rename(columns={"Date":"timestamp","Open":"open","High":"high",
                                    "Low":"low","Close":"close","Volume":"volume"})
        df = df.rename(columns=str.lower)
        if "timestamp" in df.columns:
            # utc=True handles mixed-timezone CSVs (yfinance writes tz-aware UTC,
            # Polygon writes tz-naive).  tz_localize(None) strips the tz offset so
            # backtesting.py and downstream code see a plain datetime column.
            df["timestamp"] = (
                pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
                .dt.tz_localize(None)
            )
            df = df.sort_values("timestamp").reset_index(drop=True)
        if len(df):
            print(f"   Fetched {len(df)} bars | close ${df['close'].iloc[-1]:.2f}")
        return df

    # ── Technical indicators ──────────────────────────────────────────────────
    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Attach RSI, MACD, Bollinger Bands, ATR, and MAs to a OHLCV dataframe."""
        if df.empty or len(df) < 30:
            return df
        df    = df.copy()
        close = df["close"]
        high  = df["high"]
        low   = df["low"]

        # RSI(14) — Wilder's smoothing via EWM
        delta    = close.diff()
        avg_gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        avg_loss = (-delta).clip(lower=0).ewm(com=13, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, 1e-10)
        df["rsi"] = (100 - 100 / (1 + rs)).round(2)

        # MACD (12/26/9)
        ema12           = close.ewm(span=12, adjust=False).mean()
        ema26           = close.ewm(span=26, adjust=False).mean()
        df["macd"]        = (ema12 - ema26).round(4)
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean().round(4)
        df["macd_hist"]   = (df["macd"] - df["macd_signal"]).round(4)

        # Bollinger Bands (20, 2σ)
        sma20           = close.rolling(20).mean()
        std20           = close.rolling(20).std()
        df["bb_upper"]  = (sma20 + 2 * std20).round(2)
        df["bb_lower"]  = (sma20 - 2 * std20).round(2)
        df["bb_mid"]    = sma20.round(2)
        bw              = (df["bb_upper"] - df["bb_lower"]).replace(0, 1e-10)
        df["bb_pct"]    = ((close - df["bb_lower"]) / bw * 100).clip(0, 100).round(1)

        # ATR(14) — True Range
        prev_close = close.shift(1)
        tr         = pd.concat([high - low,
                                (high - prev_close).abs(),
                                (low  - prev_close).abs()], axis=1).max(axis=1)
        df["atr"]  = tr.rolling(14).mean().round(2)

        # Moving averages
        df["sma50"]  = close.rolling(50).mean().round(2)
        df["sma200"] = close.rolling(200).mean().round(2)
        df["ema20"]  = close.ewm(span=20, adjust=False).mean().round(2)

        return df

    # ── Historical OHLCV (Polygon → yfinance fallback) ────────────────────────
    def fetch_historical(self, ticker: str, multiplier=1, timespan="day", days_back=730) -> pd.DataFrame:
        print(f"Fetching {ticker}...")
        try:
            to_dt   = datetime.now().strftime("%Y-%m-%d")
            from_dt = (datetime.now().replace(year=datetime.now().year - 2)).strftime("%Y-%m-%d")
            aggs    = self.polygon.get_aggs(ticker, multiplier, timespan, from_dt, to_dt, limit=50000)
            if aggs:
                df = pd.DataFrame([a.__dict__ for a in aggs])
                df = self._standardize_df(df)
                print(f"   Polygon OK for {ticker}")
                return self.compute_indicators(df)
        except Exception as e:
            print(f"   Polygon failed ({ticker}): {e}")

        return self._yfinance_fetch(ticker, days_back)

    def _yfinance_fetch(self, ticker: str, days_back: int = 730,
                        retries: int = 3) -> pd.DataFrame:
        """
        Rate-limited yfinance fetch with retry + exponential back-off.

        Uses a module-level semaphore (_YF_SEMAPHORE) to cap concurrent Yahoo
        requests — prevents the 400 'rate blocked' response when multiple
        threads call this simultaneously.
        """
        print(f"   yfinance fallback for {ticker}")
        for attempt in range(retries):
            try:
                with _YF_SEMAPHORE:
                    # Random jitter prevents synchronized burst after semaphore release
                    if attempt > 0:
                        wait = (2 ** attempt) + random.uniform(0, _YF_JITTER_MAX)
                        print(f"   yfinance retry {attempt}/{retries} for {ticker} "
                              f"— waiting {wait:.1f}s")
                        time.sleep(wait)
                    else:
                        time.sleep(random.uniform(0, _YF_JITTER_MAX))

                    # Prefer Ticker.history() — better cookie/crumb handling than download()
                    yf_ticker = yf.Ticker(ticker)
                    df = yf_ticker.history(period=f"{days_back}d", interval="1d",
                                           auto_adjust=True, actions=False)

                if df is None or df.empty:
                    # Fall back to download() if Ticker.history() gives nothing
                    with _YF_SEMAPHORE:
                        time.sleep(random.uniform(0.3, _YF_JITTER_MAX))
                        df = yf.download(ticker, period=f"{days_back}d",
                                         interval="1d", progress=False, auto_adjust=True)

                if df is not None and not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    df = df.reset_index()
                    df = self._standardize_df(df)
                    print(f"   yfinance OK for {ticker}")
                    return self.compute_indicators(df)

            except Exception as e:
                err_str = str(e)
                if "400" in err_str or "Too Many Requests" in err_str or "429" in err_str:
                    wait = (2 ** (attempt + 1)) + random.uniform(1, 3)
                    print(f"   ⚠️  Yahoo rate-limit hit for {ticker} — "
                          f"backing off {wait:.1f}s (attempt {attempt+1}/{retries})")
                    time.sleep(wait)
                else:
                    print(f"   yfinance failed ({ticker}): {e}")
                    break   # non-rate-limit errors won't resolve on retry

        print(f"   No data for {ticker}")
        return pd.DataFrame()

    # ── Live price ────────────────────────────────────────────────────────────
    def get_live_price(self, ticker: str) -> float | None:
        try:
            snapshot = self.polygon.get_snapshot(ticker)
            return snapshot.day.close if hasattr(snapshot, "day") else None
        except Exception:
            return None

    # ── News headlines via yfinance ───────────────────────────────────────────
    def get_news(self, ticker: str, limit: int = 5) -> list[dict]:
        """Fetch news headlines with semaphore rate-limiting to avoid Yahoo 400s."""
        try:
            with _YF_SEMAPHORE:
                time.sleep(random.uniform(0.1, 0.5))   # small jitter
                news = yf.Ticker(ticker).news or []
            result = []
            for item in news[:limit]:
                # Handle both old and new yfinance formats
                content = item.get("content", item)
                title   = content.get("title", item.get("title", ""))
                pub     = content.get("provider", {}).get("displayName",
                          item.get("publisher", ""))
                ts      = (content.get("pubDate", "") or
                           str(datetime.fromtimestamp(item.get("providerPublishTime", 0))))
                link    = content.get("canonicalUrl", {}).get("url",
                          item.get("link", ""))
                if title:
                    result.append({"title": title, "publisher": pub,
                                   "time": str(ts)[:16], "link": link})
            return result
        except Exception as e:
            err = str(e)
            if "400" in err or "429" in err:
                print(f"   News rate-limited ({ticker}) — skipping")
            else:
                print(f"   News fetch failed ({ticker}): {e}")
            return []

    # ── Alpaca paper account ──────────────────────────────────────────────────
    def get_alpaca_account(self):
        return self.alpaca.get_account()

    def get_alpaca_positions(self) -> list[dict]:
        try:
            positions = self.alpaca.get_all_positions()
            return [
                {
                    "symbol":         p.symbol,
                    "qty":            float(p.qty),
                    "side":           str(p.side),
                    "avg_entry":      float(p.avg_entry_price),
                    "current_price":  float(p.current_price or 0),
                    "market_value":   float(p.market_value or 0),
                    "unrealized_pl":  float(p.unrealized_pl or 0),
                    "unrealized_plpc":float(p.unrealized_plpc or 0) * 100,
                }
                for p in positions
            ]
        except Exception as e:
            print(f"   Could not fetch positions: {e}")
            return []

    # ── Earnings calendar ─────────────────────────────────────────────────────
    # Process-level cache: { "AAPL": "2026-07-30" | None }.
    # Yahoo's calendar endpoint is more aggressively rate-limited than price data.
    # Caching prevents redundant calls when both SignalGenerator and RiskGuardian
    # check the same ticker in the same run.
    _earnings_cache: dict[str, str | None] = {}

    def get_earnings_date(self, ticker: str) -> str | None:
        """
        Return next earnings date as 'YYYY-MM-DD', or None if unavailable.
        Results are cached for the lifetime of the process (one daily run).
        Uses a longer inter-request sleep to avoid Yahoo calendar 400 blocks.
        """
        if ticker in self._earnings_cache:
            return self._earnings_cache[ticker]

        result = self._fetch_earnings_date(ticker)
        self._earnings_cache[ticker] = result
        return result

    def _fetch_earnings_date(self, ticker: str) -> str | None:
        """Internal: actually calls Yahoo — always go through get_earnings_date() instead."""
        # Longer delay for calendar endpoint (more aggressively rate-limited)
        _CALENDAR_SLEEP = (1.5, 3.0)   # random sleep range in seconds

        try:
            with _YF_SEMAPHORE:
                time.sleep(random.uniform(*_CALENDAR_SLEEP))
                t   = yf.Ticker(ticker)
                cal = t.calendar
            # New yfinance: dict with 'Earnings Date' key
            if isinstance(cal, dict):
                dates = cal.get("Earnings Date", [])
                if dates:
                    d = dates[0]
                    return str(d)[:10] if hasattr(d, "__str__") else None
            # Old yfinance: DataFrame indexed by field name
            elif hasattr(cal, "columns"):
                for col in cal.columns:
                    if "earn" in str(col).lower():
                        val = cal[col].dropna()
                        if len(val):
                            return str(val.iloc[0])[:10]
        except Exception as e:
            err = str(e)
            if "400" in err or "429" in err:
                print(f"   Earnings calendar rate-limited ({ticker}) — skipping")
            elif "<!doctype" in err.lower() or "html" in err.lower():
                print(f"   Earnings calendar blocked ({ticker}) — skipping")
            else:
                print(f"   Earnings date unavailable ({ticker}): {e}")

        # Fallback: earnings_dates property (different endpoint)
        try:
            with _YF_SEMAPHORE:
                time.sleep(random.uniform(*_CALENDAR_SLEEP))
                t  = yf.Ticker(ticker)
                ed = t.earnings_dates
            if ed is not None and not ed.empty:
                future = ed[ed.index > pd.Timestamp.now(tz="UTC")]
                if not future.empty:
                    return str(future.index[0].date())
        except Exception:
            pass
        return None

    # ── Historical volatility ─────────────────────────────────────────────────
    @staticmethod
    def compute_hv(prices: pd.Series, period: int = 20) -> float | None:
        """Annualised close-to-close historical volatility (%)."""
        returns = prices.pct_change().dropna()
        if len(returns) < period:
            return None
        return float(returns.tail(period).std() * (252 ** 0.5) * 100)

    # ── Paper order ───────────────────────────────────────────────────────────
    def place_paper_order(self, symbol: str, qty: int, side: str):
        order_data = MarketOrderRequest(
            symbol=symbol, qty=qty,
            side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
            type=OrderType.MARKET,
        )
        return self.alpaca.submit_order(order_data)
