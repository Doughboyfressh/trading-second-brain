# src/agents/regime_classifier.py
import pandas as pd
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from src.llm import TradingLLM
from datetime import datetime


class RegimeClassifier(BaseAgent):
    def __init__(self):
        super().__init__(
            "RegimeClassifier",
            "You are RegimeClassifier. Classify the current market regime. "
            "Output EXACTLY these fields on separate lines:\n"
            "REGIME: <Bullish Trending | Bearish Trending | Ranging | High-Volatility>\n"
            "CONFIDENCE: <N>%\n"
            "VOLATILITY: <Low | Medium | High | Extreme>\n"
            "BIAS: <long | short | neutral>\n"
            "Then 3-5 bullet rationale points. Base everything on the real data provided.",
            model=TradingLLM.HAIKU,
            max_tokens=900,
            rag_top_k=3,
            temperature=0.10,   # classification — stable output preferred
        )
        self.fetcher = DataFetcher()

    def classify_regime(self):
        market_data = ""
        for ticker in ["SPY", "QQQ", "^VIX"]:
            df = self.fetcher.fetch_historical(ticker, days_back=180)
            if df.empty:
                market_data += f"\n{ticker}: data unavailable\n"
                continue
            last      = df.iloc[-1]
            prev      = df.iloc[-2] if len(df) > 1 else last
            chg       = ((last["close"] - prev["close"]) / prev["close"] * 100) if prev["close"] else 0
            sma50     = last.get("sma50",  float("nan"))
            sma200    = last.get("sma200", float("nan"))
            rsi       = last.get("rsi",    float("nan"))
            atr       = last.get("atr",    float("nan"))
            atr_pct   = (atr / last["close"] * 100) if not pd.isna(atr) and last["close"] else float("nan")
            # 5-day trend
            five_day  = ((last["close"] - df.iloc[-5]["close"]) / df.iloc[-5]["close"] * 100) if len(df) >= 5 else chg

            market_data += (
                f"\n{ticker}:\n"
                f"  Close: ${last['close']:.2f}  (1d {chg:+.2f}%, 5d {five_day:+.2f}%)\n"
                f"  50d SMA: ${sma50:.2f} — price is {'ABOVE' if last['close']>sma50 else 'BELOW'}\n"
                f"  200d SMA: ${sma200:.2f} — price is {'ABOVE' if last['close']>sma200 else 'BELOW'}\n"
                f"  RSI(14): {rsi:.1f}\n"
                f"  ATR%: {atr_pct:.2f}% (daily volatility)\n"
            )

        task = (
            f"Classify today's market regime using this real-time data:\n{market_data}\n\n"
            "Also cross-reference any relevant notes in the vault. "
            "Produce the REGIME, CONFIDENCE, VOLATILITY, BIAS fields then rationale bullets."
        )
        self.think_and_write(task, "00-Daily", f"regime_{datetime.now().strftime('%Y-%m-%d')}.md")
