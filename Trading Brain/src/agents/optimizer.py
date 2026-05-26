# src/agents/optimizer.py
from src.agents.base import BaseAgent
from src.backtester import run_backtest
from src.data_fetcher import DataFetcher
from datetime import datetime

class Optimizer(BaseAgent):
    def __init__(self):
        super().__init__(
            "Optimizer",
            "You are Optimizer. Run walk-forward optimization, evaluate strategies across regimes, and rank them by performance. Be quantitative and objective."
        )
        self.fetcher = DataFetcher()
    
    def run_optimization_loop(self, tickers: list = None):
        if tickers is None:
            tickers = ["AAPL", "TSLA"]
        
        for ticker in tickers:
            print(f"   Optimizing {ticker}...")
            df = self.fetcher.fetch_historical(ticker)
            if df.empty:
                continue
            report = run_backtest(df, "SMA_Crossover", ticker)
            self.think_and_write(
                f"Analyze this walk-forward backtest report and suggest improvements:\n{report}",
                "04-Backtests",
                f"OPTIMIZED_{ticker}_{datetime.now().strftime('%Y%m%d')}.md"
            )
    
    def rank_strategies(self):
        """Rank all strategies based on latest backtests and write ranking to playbooks"""
        task = """Read all the latest walk-forward backtest reports in 04-Backtests/.
Create a ranked list of strategies by:
1. Sharpe Ratio
2. Return / Max Drawdown
3. Win Rate
4. Number of trades
5. Suitability for current regime (from regime_*.md)

Output in clean markdown table format for the vault."""
        self.think_and_write(task, "06-Playbooks", f"STRATEGY_RANKING_{datetime.now().strftime('%Y%m%d')}.md")
        print("✅ Strategy ranking completed")
