# src/agents/meta_evaluator.py
from src.agents.base import BaseAgent
from datetime import datetime

class MetaEvaluator(BaseAgent):
    def __init__(self):
        super().__init__(
            "MetaEvaluator",
            "You are MetaEvaluator. Review all backtests, strategies, and agent performance over time. Score them and suggest which ones to promote or retire."
        )
    
    def evaluate_performance(self):
        self.think_and_write(
            "Review all backtest reports and strategy rankings. Create a performance scorecard and recommend which strategies to keep using.",
            "06-Playbooks",
            f"META_EVAL_{datetime.now().strftime('%Y%m%d')}.md"
        )