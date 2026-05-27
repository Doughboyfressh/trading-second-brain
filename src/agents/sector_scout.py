# src/agents/sector_scout.py
"""
SectorScout — tracks 11 US sector ETFs and identifies rotation patterns.
Saves sectors_latest.json for the GUI heatmap, plus a markdown summary.
"""
import json
import pandas as pd
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from src.llm import TradingLLM
from datetime import datetime

SECTOR_ETFS = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLE":  "Energy",
    "XLV":  "Healthcare",
    "XLP":  "Consumer Staples",
    "XLY":  "Consumer Discretionary",
    "XLI":  "Industrials",
    "XLB":  "Materials",
    "XLU":  "Utilities",
    "XLRE": "Real Estate",
    "XLC":  "Communication",
}


class SectorScout(BaseAgent):
    def __init__(self):
        super().__init__(
            "SectorScout",
            "You are SectorScout. Analyze US sector rotation from the data provided. "
            "Output:\n"
            "ROTATION SIGNAL: <Risk-On | Risk-Off | Mixed | Defensive>\n"
            "LEADING SECTORS: 2-3 bullets (name, % return, why leading)\n"
            "LAGGING SECTORS: 2-3 bullets (name, % return, why lagging)\n"
            "IMPLICATIONS: 2-3 bullets for swing traders\n"
            "Be specific with numbers. Never guess — only use provided data.",
            model=TradingLLM.HAIKU,
            max_tokens=1000,
            rag_top_k=2,
        )
        self.fetcher = DataFetcher()

    def scan_sectors(self):
        rows       = []
        data_lines = []

        for etf, sector in SECTOR_ETFS.items():
            try:
                df = self.fetcher.fetch_historical(etf, days_back=90)
            except Exception as e:
                print(f"   SectorScout: failed {etf}: {e}")
                continue
            if df.empty or len(df) < 5:
                continue

            last  = df.iloc[-1]
            prev  = df.iloc[-2]
            w1    = df.iloc[-5]  if len(df) >= 5  else df.iloc[0]
            m1    = df.iloc[-21] if len(df) >= 21 else df.iloc[0]
            m3    = df.iloc[0]
            rsi   = last.get("rsi",   float("nan"))
            atr   = last.get("atr",   float("nan"))
            close = float(last["close"])

            d1  = (close - float(prev["close"])) / float(prev["close"]) * 100
            d5  = (close - float(w1["close"]))   / float(w1["close"])   * 100
            d21 = (close - float(m1["close"]))   / float(m1["close"])   * 100
            d63 = (close - float(m3["close"]))   / float(m3["close"])   * 100

            rows.append({
                "ETF":    etf,
                "Sector": sector,
                "Close":  round(close, 2),
                "1D%":    round(d1,  2),
                "5D%":    round(d5,  2),
                "21D%":   round(d21, 2),
                "63D%":   round(d63, 2),
                "RSI":    round(rsi, 1) if not pd.isna(rsi) else None,
            })
            data_lines.append(
                f"{etf} ({sector}): "
                f"1d {d1:+.2f}%  5d {d5:+.2f}%  "
                f"21d {d21:+.2f}%  63d {d63:+.2f}%  RSI {rsi:.0f}"
            )

        # Save JSON for GUI sector heatmap
        if rows:
            sector_dir = self.vault.root / "00-Daily"
            sector_dir.mkdir(parents=True, exist_ok=True)
            with open(sector_dir / "sectors_latest.json", "w") as f:
                json.dump(rows, f, indent=2)
            print(f"   Sector snapshot saved ({len(rows)} sectors)")

        sector_table = "\n".join(data_lines) or "No sector data available."
        self.think_and_write(
            f"Analyze sector rotation from this data:\n\n{sector_table}",
            "00-Daily",
            f"sectors_{datetime.now().strftime('%Y-%m-%d')}.md",
        )
        print("Sector scan complete")
