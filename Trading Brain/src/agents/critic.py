# src/agents/critic.py
from src.agents.base import BaseAgent
from datetime import datetime

class Critic(BaseAgent):
    def __init__(self):
        super().__init__(
            "Critic",
            "You are Critic. You review every strategy, backtest, or trade decision for logical errors, risk violations, or weak reasoning. Be brutally honest and suggest improvements."
        )
    
    def review_note(self, folder: str, filename: str):
        content = self.vault.read_note(folder, filename)
        task = f"Review this note for flaws, risk issues, or better alternatives:\n\n{content}\n\nProvide detailed feedback and suggested improvements."
        self.think_and_write(task, "08-Logs", f"CRITIC_REVIEW_{filename}")
        print(f"✅ Critic reviewed {filename}")