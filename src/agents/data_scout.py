# src/agents/data_scout.py
"""
DataScout — fetches OHLCV data, computes technical indicators, saves CSV,
then writes a concise LLM summary to the vault.

Supports two-phase operation for the daily loop:
  Phase 1 (parallel): prefetch + save CSV via DataFetcher directly
  Phase 2 (sequential): analyze_from_csv() — reads saved CSV, makes LLM call
"""
import pandas as pd
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from src.llm import TradingLLM


class DataScout(BaseAgent):
    def __init__(self):
        super().__init__(
            "DataScout",
            "You are DataScout. Write a concise, structured market data summary. "
            "Cover: close & % change, volume vs average, MA position, "
            "RSI signal, MACD direction, Bollinger Band position, and ATR. "
            "Max 6 bullets. Be factual — all numbers are provided.",
            model=TradingLLM.HAIKU,
            max_tokens=700,
            rag_top_k=2,
        )
        self.fetcher = DataFetcher()

    # ── Full fetch + analyse (original flow) ─────────────────────────────────
    def update_asset_data(self, ticker: str):
        df = self.fetcher.fetch_historical(ticker)
        if df.empty:
            print(f"Skipped {ticker} — no data")
            return
        self._save_csv(ticker, df)
        self._llm_analyze(ticker, df)

    # ── Phase 1: fetch & save only (no LLM — called from thread pool) ────────
    def prefetch_and_save(self, ticker: str) -> bool:
        """
        Build the vault CSV for *ticker* using the 10-year pre-downloaded
        history as the base, then appending only the recent bars from the
        network.  This is vastly faster than a full 2-year network fetch
        and gives agents access to much deeper historical context.

        If data/historical/{ticker}_10y.csv does not exist, falls back to
        a standard 2-year network fetch.
        """
        try:
            from src.historical_loader import load_historical
            import time, random

            # Load full history (10y CSV + any existing vault CSV for recent bars)
            df = load_historical(ticker, years=10, compute_indicators=False)

            if not df.empty:
                # Check how stale the most recent bar is
                last_ts   = df["timestamp"].max()
                days_stale = (pd.Timestamp.now() - last_ts).days

                if days_stale >= 1:
                    # Quick fetch of last 10 days to catch any new market sessions
                    time.sleep(random.uniform(0.2, 0.8))   # polite jitter
                    recent = self.fetcher._yfinance_fetch(ticker, days_back=10)
                    if not recent.empty and "timestamp" in recent.columns:
                        new_rows = recent[recent["timestamp"] > last_ts][
                            ["timestamp", "open", "high", "low", "close", "volume"]
                        ].copy()
                        if not new_rows.empty:
                            df = pd.concat(
                                [df[["timestamp","open","high","low","close","volume"]],
                                 new_rows],
                                ignore_index=True
                            )
                            df = df.sort_values("timestamp").reset_index(drop=True)
                            print(f"   Prefetch {ticker}: appended {len(new_rows)} new bar(s)")

                # Compute indicators on the full merged history
                df = self.fetcher.compute_indicators(df)
                self._save_csv(ticker, df)
                print(f"   Prefetch {ticker}: {len(df)} bars saved (10y history base)")
                return True

            # Fallback: standard 2-year network fetch
            df = self.fetcher.fetch_historical(ticker)
            if df.empty:
                return False
            self._save_csv(ticker, df)
            return True

        except Exception as e:
            print(f"   Prefetch failed {ticker}: {e}")
            return False

    # ── Phase 2: read CSV + LLM (called sequentially) ────────────────────────
    def analyze_from_csv(self, ticker: str):
        """LLM analysis from the pre-saved CSV (no re-fetch)."""
        csv_path = self.vault.root / "01-Assets" / "Stocks" / f"{ticker}.csv"
        if not csv_path.exists():
            # CSV doesn't exist — fall back to full fetch
            return self.update_asset_data(ticker)
        try:
            df = pd.read_csv(str(csv_path))
            if df.empty or len(df) < 2:
                return self.update_asset_data(ticker)
            # timestamp may be a string; coerce quietly
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            self._llm_analyze(ticker, df)
        except Exception:
            self.update_asset_data(ticker)

    # ── Shared helpers ────────────────────────────────────────────────────────
    def _save_csv(self, ticker: str, df: pd.DataFrame):
        csv_path = self.vault.root / "01-Assets" / "Stocks" / f"{ticker}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(str(csv_path), index=False)

    def _llm_analyze(self, ticker: str, df: pd.DataFrame):
        """Build a rich indicator summary and write to vault via LLM."""
        if df.empty or len(df) < 2:
            return

        last    = df.iloc[-1]
        prev    = df.iloc[-2]
        chg     = ((float(last["close"]) - float(prev["close"])) / float(prev["close"]) * 100)
        avg_vol = df["volume"].tail(30).mean() if "volume" in df.columns else 1
        vol_r   = float(last["volume"]) / avg_vol if avg_vol else 1

        def _f(col):
            v = last.get(col, float("nan"))
            return float(v) if not pd.isna(v) else None

        close  = float(last["close"])
        rsi    = _f("rsi");    sma50  = _f("sma50");  sma200 = _f("sma200")
        macd   = _f("macd");   macd_s = _f("macd_signal"); macd_h = _f("macd_hist")
        bb_pct = _f("bb_pct"); bb_u   = _f("bb_upper");    bb_l   = _f("bb_lower")
        atr    = _f("atr")

        # RSI interpretation
        if rsi is None:          rsi_note = "N/A"
        elif rsi >= 70:          rsi_note = f"{rsi:.1f} — OVERBOUGHT ⚠️"
        elif rsi <= 30:          rsi_note = f"{rsi:.1f} — OVERSOLD (potential bounce)"
        else:                    rsi_note = f"{rsi:.1f} — neutral"

        # MACD
        if macd is None:         macd_note = "N/A"
        else:
            cross = "bullish ↑" if macd > (macd_s or 0) else "bearish ↓"
            macd_note = f"{macd:+.4f} / sig {macd_s:+.4f} / hist {macd_h:+.4f} ({cross})"

        # Bollinger
        if bb_pct is None:       bb_note = "N/A"
        elif bb_pct >= 88:       bb_note = f"{bb_pct:.0f}%B — near UPPER ${bb_u:.2f}, watch reversal"
        elif bb_pct <= 12:       bb_note = f"{bb_pct:.0f}%B — near LOWER ${bb_l:.2f}, possible bounce"
        else:                    bb_note = f"{bb_pct:.0f}%B mid-range (${bb_l:.2f}–${bb_u:.2f})"

        # MAs
        ma_note = ""
        if sma50:
            ma_note += f"50d SMA ${sma50:.2f} ({'ABOVE' if close>sma50 else 'BELOW'})  "
        if sma200:
            ma_note += f"200d SMA ${sma200:.2f} ({'ABOVE' if close>sma200 else 'BELOW'})"

        atr_note = f"${atr:.2f}" if atr else "N/A"

        summary = (
            f"Ticker: {ticker}\n"
            f"Close: ${close:.2f}  ({chg:+.2f}% vs prev)\n"
            f"Volume: {float(last.get('volume', 0)):,.0f}  ({vol_r:.1f}x 30d avg)\n"
            f"Moving Averages: {ma_note.strip()}\n"
            f"RSI(14): {rsi_note}\n"
            f"MACD(12/26/9): {macd_note}\n"
            f"Bollinger Bands: {bb_note}\n"
            f"ATR(14): {atr_note}  (daily risk/stop reference)\n"
            f"Bars available: {len(df)}"
        )

        self.think_and_write(
            f"Write a concise market data summary for {ticker}:\n\n{summary}",
            "07-Research",
            f"{ticker}_analysis.md",
        )
        print(f"Analysed {ticker}")
