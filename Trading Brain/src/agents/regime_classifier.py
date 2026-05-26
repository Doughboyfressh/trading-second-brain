# src/agents/regime_classifier.py
from src.agents.base import BaseAgent
from datetime import datetime

class RegimeClassifier(BaseAgent):
    def __init__(self):
        super().__init__(
            "RegimeClassifier",
            "You are RegimeClassifier. Analyze current market regime (Trending, Ranging, High-Volatility, Bull/Bear) using volatility, trend strength, and volume. Output clear regime label + confidence."
        )
    
    def classify_regime(self):
        self.think_and_write(
            "Analyze latest market data and determine the current regime for stocks. Output only: Regime: [Trending/Ranging/High-Vol] | Confidence: XX% | Implications for strategies.",
            "00-Daily",
            f"regime_{datetime.now().strftime('%Y-%m-%d')}.md"
        )