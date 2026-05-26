# src/agents/market_analyst.py
from src.agents.base import BaseAgent
from datetime import datetime   # ← This was missing

class MarketAnalyst(BaseAgent):
    def __init__(self):
        super().__init__(
            "MarketAnalyst",
            "You are MarketAnalyst. Provide daily regime analysis, volatility, and sentiment for stocks only. Write to 00-Daily."
        )
    
    def daily_analysis(self):
        self.think_and_write(
            "Write today's market regime analysis for stocks (trend, volatility, key levels, sentiment).",
            "00-Daily",
            f"daily_{datetime.now().strftime('%Y-%m-%d')}.md"
        )