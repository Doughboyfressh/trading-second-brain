# src/agents/volatility_agent.py
"""
VolatilityAgent — tracks VIX, computes HV20/HV60 per watchlist ticker,
classifies the volatility regime, and saves a JSON snapshot for the GUI.

Output files:
  vault/00-Daily/volatility_latest.json  ← GUI reads this
  vault/00-Daily/volatility_YYYY-MM-DD.md ← LLM narrative
"""
import json
import pandas as pd
from datetime import datetime
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from src.llm import TradingLLM
from config import WATCHLIST


class VolatilityAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "VolatilityAgent",
            "You are VolatilityAgent. Analyze the current volatility regime. Output:\n"
            "VOLATILITY REGIME: <Low|Normal|Elevated|Spike>\n"
            "VIX ASSESSMENT: 1-2 sentences on current VIX vs historical norms\n"
            "EXPANDING VOL: list tickers where HV20 > HV60 (vol expanding)\n"
            "CONTRACTING VOL: list tickers where HV20 < HV60 (vol compressing)\n"
            "POSITION SIZING NOTE: 1-2 sentences on how to size given current vol\n"
            "OPTIONS NOTE: brief comment on whether IV is likely cheap or expensive\n"
            "Use only the provided data — no guessing.",
            model=TradingLLM.HAIKU,
            max_tokens=800,
            rag_top_k=2,
            temperature=0.10,   # measurement / classification — stable output preferred
        )
        self.fetcher = DataFetcher()

    # ── Internal helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _vix_regime(vix: float) -> str:
        if vix < 13:   return "Low (extreme complacency)"
        if vix < 18:   return "Normal"
        if vix < 25:   return "Elevated"
        if vix < 35:   return "High (fear)"
        return "Spike (panic)"

    def _ticker_hvs(self) -> dict:
        """Read saved CSVs and compute HV20/HV60 for each WATCHLIST ticker."""
        result = {}
        for ticker in WATCHLIST:
            csv_path = self.vault.root / "01-Assets" / "Stocks" / f"{ticker}.csv"
            if not csv_path.exists():
                continue
            try:
                df = pd.read_csv(str(csv_path))
                if "close" not in df.columns or len(df) < 65:
                    continue
                prices = df["close"].dropna()
                hv20 = DataFetcher.compute_hv(prices, 20)
                hv60 = DataFetcher.compute_hv(prices, 60)
                if hv20 is not None and hv60 is not None:
                    result[ticker] = {
                        "hv20":       round(hv20, 1),
                        "hv60":       round(hv60, 1),
                        "expanding":  hv20 > hv60,
                        "ratio":      round(hv20 / hv60, 2) if hv60 else None,
                    }
            except Exception as e:
                print(f"   VolatilityAgent: HV failed for {ticker}: {e}")
        return result

    # ── Main entry ────────────────────────────────────────────────────────────
    def analyze_volatility(self):
        # ── Fetch VIX ────────────────────────────────────────────────────────
        vix_close = None
        vix_pct   = None
        try:
            vix_df = self.fetcher.fetch_historical("^VIX", days_back=252)
            if not vix_df.empty and "close" in vix_df.columns:
                series    = vix_df["close"].dropna()
                vix_close = float(series.iloc[-1])
                # 1-year percentile rank
                vix_pct   = int((series < vix_close).mean() * 100)
        except Exception as e:
            print(f"   VolatilityAgent: VIX fetch failed: {e}")

        vix_regime = self._vix_regime(vix_close) if vix_close else "Unknown"

        # ── Historical vol per ticker ─────────────────────────────────────────
        ticker_vol = self._ticker_hvs()

        # ── Save JSON snapshot for GUI ─────────────────────────────────────────
        snapshot = {
            "timestamp":           datetime.now().isoformat(),
            "vix":                 round(vix_close, 2) if vix_close else None,
            "vix_regime":          vix_regime,
            "vix_percentile_1yr":  vix_pct,
            "tickers":             ticker_vol,
        }
        vol_dir = self.vault.root / "00-Daily"
        vol_dir.mkdir(parents=True, exist_ok=True)
        with open(vol_dir / "volatility_latest.json", "w") as f:
            json.dump(snapshot, f, indent=2)
        print(f"   Volatility snapshot saved — VIX: {vix_close}")

        # ── Build LLM prompt ──────────────────────────────────────────────────
        vix_line = (
            f"VIX: {vix_close:.1f} — {vix_regime} — {vix_pct}th percentile vs past 1 year"
            if vix_close else "VIX: unavailable"
        )
        hv_lines = []
        for ticker, v in ticker_vol.items():
            trend = "EXPANDING ↑" if v["expanding"] else "contracting ↓"
            hv_lines.append(
                f"  {ticker}: HV20={v['hv20']:.1f}%  HV60={v['hv60']:.1f}%  "
                f"({trend}, ratio={v['ratio']:.2f})"
            )
        hv_block = "\n".join(hv_lines) or "  No ticker HV data available."

        self.think_and_write(
            f"Analyze the current volatility environment:\n\n"
            f"{vix_line}\n\n"
            f"Historical Volatility by ticker (HV20 vs HV60):\n{hv_block}",
            "00-Daily",
            f"volatility_{datetime.now().strftime('%Y-%m-%d')}.md",
        )
        print("VolatilityAgent analysis complete")
