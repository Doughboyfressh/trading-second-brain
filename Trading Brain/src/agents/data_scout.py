# src/agents/data_scout.py
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher

class DataScout(BaseAgent):
    def __init__(self):
        super().__init__(
            "DataScout",
            "You are DataScout. Fetch and summarize market data for stocks. Write clean CSV summaries and analysis to the vault."
        )
        self.fetcher = DataFetcher()
    
    def update_asset_data(self, ticker: str):
        df = self.fetcher.fetch_historical(ticker)
        
        if df.empty:
            print(f"⚠️ Skipped {ticker} - no data")
            return
        
        df.to_csv(f"vault/01-Assets/Stocks/{ticker}.csv", index=False)
        self.think_and_write(f"Analyze latest data for {ticker}", "07-Research", f"{ticker}_analysis.md")
        print(f"✅ Saved + analyzed {ticker}")