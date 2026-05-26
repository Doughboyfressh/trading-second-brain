# src/agents/sentiment_agent.py
from src.agents.base import BaseAgent
from datetime import datetime

class SentimentAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "SentimentAgent",
            "You are SentimentAgent. Analyze latest news and market sentiment for stocks. Combine with regime data to give actionable sentiment score."
        )
    
    def analyze_sentiment(self):
        self.think_and_write(
            "Pull latest sentiment for AAPL and TSLA. Combine with current regime and give overall market sentiment score (Bullish/Neutral/Bearish) + confidence.",
            "00-Daily",
            f"sentiment_{datetime.now().strftime('%Y-%m-%d')}.md"
        )