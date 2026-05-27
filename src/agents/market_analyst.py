# src/agents/market_analyst.py
"""
MarketAnalyst — writes the daily market narrative note.
Injects real SPY / QQQ / IWM indicator data so the LLM has concrete numbers.

Data source priority:
  1. Pre-saved CSV from Phase 1a (no extra network call needed if on watchlist)
  2. Live Polygon/yfinance fetch (fallback for ETFs not on the watchlist)
"""
import pandas as pd
from pathlib import Path
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from src.llm import TradingLLM
from datetime import datetime


class MarketAnalyst(BaseAgent):
    def __init__(self):
        super().__init__(
            "MarketAnalyst",
            "You are MarketAnalyst. Write a concise daily market note in structured markdown:\n"
            "## Regime\n## Key Levels\n## Opportunities\n## Risks\n## Action Items\n"
            "Each section max 3 bullets. Cite specific prices and percentages. "
            "Cross-reference the provided live indicator data with vault context.",
            model=TradingLLM.HAIKU,
            max_tokens=1200,
            rag_top_k=3,
        )
        self.fetcher = DataFetcher()

    def _load_etf_df(self, etf: str) -> pd.DataFrame:
        """
        Load ETF data from the pre-saved CSV when available (avoids duplicate
        network calls for ETFs already on the watchlist).  Falls back to a live
        fetch for ETFs not covered by Phase 1a prefetch.
        """
        csv_path = self.vault.root / "01-Assets" / "Stocks" / f"{etf}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(str(csv_path))
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                if not df.empty and len(df) >= 5:
                    return df
            except Exception:
                pass  # fall through to live fetch
        # Live fetch — only hits the network for ETFs not already in the vault CSVs
        return self.fetcher.fetch_historical(etf, days_back=60)

    def _build_market_context(self) -> str:
        """Fetch SPY, QQQ, IWM, DIA data; format as a concise indicator block."""
        lines = []
        for etf in ["SPY", "QQQ", "IWM", "DIA"]:
            try:
                df = self._load_etf_df(etf)
                if df.empty or len(df) < 5:
                    continue
                last  = df.iloc[-1]
                prev  = df.iloc[-2]
                close = float(last["close"])
                chg   = (close - float(prev["close"])) / float(prev["close"]) * 100

                def _f(col):
                    v = last.get(col, float("nan"))
                    return float(v) if not pd.isna(v) else None

                rsi    = _f("rsi")
                sma50  = _f("sma50")
                sma200 = _f("sma200")
                atr    = _f("atr")
                macd   = _f("macd")
                macd_s = _f("macd_signal")

                # 5-day return
                w1    = df.iloc[-5] if len(df) >= 5 else df.iloc[0]
                ret5d = (close - float(w1["close"])) / float(w1["close"]) * 100

                rsi_str = f"{rsi:.0f}" if rsi else "N/A"
                sma50_str  = (f"${sma50:.2f} ({'ABOVE' if sma50 and close > sma50 else 'BELOW'})"
                              if sma50 else "N/A")
                sma200_str = (f"${sma200:.2f} ({'ABOVE' if sma200 and close > sma200 else 'BELOW'})"
                              if sma200 else "N/A")
                macd_dir = ""
                if macd is not None and macd_s is not None:
                    macd_dir = " | MACD " + ("bullish ↑" if macd > macd_s else "bearish ↓")

                lines.append(
                    f"{etf}: ${close:.2f} ({chg:+.2f}% 1d | {ret5d:+.2f}% 5d) | "
                    f"RSI={rsi_str} | SMA50={sma50_str} | SMA200={sma200_str}"
                    f"{macd_dir}"
                )
            except Exception as e:
                lines.append(f"{etf}: data unavailable ({e})")

        return "\n".join(lines) if lines else "Market index data unavailable."

    def daily_analysis(self):
        market_context = self._build_market_context()
        self.think_and_write(
            f"Write today's daily market analysis note.\n\n"
            f"LIVE MARKET INDEX DATA (use these exact values):\n{market_context}\n\n"
            "Cross-reference with regime classification, sentiment scores, and sector rotation "
            "data from the vault. Be concise and actionable.",
            "00-Daily",
            f"daily_{datetime.now().strftime('%Y-%m-%d')}.md",
        )
