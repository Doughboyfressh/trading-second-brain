# src/agents/meta_evaluator.py
from src.agents.base import BaseAgent
from src.llm import TradingLLM
from datetime import datetime

class MetaEvaluator(BaseAgent):
    def __init__(self):
        super().__init__(
            "MetaEvaluator",
            "You are MetaEvaluator. Score and rank all strategies using a structured scorecard. "
            "For each strategy output: Sharpe tier, DD risk, Win Rate grade, Regime fit, "
            "Overall score /10, and a KEEP / REFINE / RETIRE verdict. "
            "End with a prioritised action list.",
            model=TradingLLM.SONNET,   # needs cross-agent synthesis
            max_tokens=1800,
            rag_top_k=5,
            temperature=0.20,   # cross-agent synthesis benefits from slight variability
        )

    def evaluate_performance(self):
        self.think_and_write(
            "Review all backtest reports and strategy rankings in the vault. "
            "Produce a performance scorecard and prioritised recommendations.",
            "06-Playbooks",
            f"META_EVAL_{datetime.now().strftime('%Y%m%d')}.md",
        )
