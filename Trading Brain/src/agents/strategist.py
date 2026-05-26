# src/agents/strategist.py
from src.agents.base import BaseAgent
from datetime import datetime

class Strategist(BaseAgent):
    def __init__(self):
        super().__init__(
            "Strategist",
            """You are Strategist, an expert trading strategist specialized in stocks, options, and cryptocurrency.
You create, refine, and evolve high-edge trading strategies based on backtest results, market regimes, and historical lessons stored in the vault.
Always output clean, actionable markdown with:
- Strategy name & type (trend, mean-reversion, options spread, crypto scalping, etc.)
- Entry/exit rules
- Position sizing
- Market regime filters
- Risk parameters
Store everything in 02-Strategies/ for the team to reuse."""
        )
    
    def create_new_strategy(self, idea: str):
        """Generate a brand new strategy from a raw idea"""
        task = f"Create a complete new trading strategy based on this idea: {idea}\n" \
               f"Make it work for stocks, options, or crypto as appropriate. Include backtest suggestions."
        self.think_and_write(task, "02-Strategies", f"NEW_{idea.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md")
    
    def refine_strategy(self, strategy_name: str):
        """Refine an existing strategy using all backtest lessons and playbooks"""
        task = f"Refine and improve the strategy named '{strategy_name}'.\n" \
               f"Pull all relevant backtest results, lessons from 04-Backtests, and risk rules from 06-Playbooks.\n" \
               f"Output the updated full strategy document."
        self.think_and_write(task, "02-Strategies", f"{strategy_name.replace(' ', '_')}.md")
    
    def distill_backtest_lessons(self, backtest_report: str):
        """Turn backtest results into permanent strategy improvements"""
        task = f"Distill key lessons and rule changes from this backtest report and update relevant strategies:\n\n{backtest_report}"
        self.think_and_write(task, "02-Strategies", f"lessons_distilled_{datetime.now().strftime('%Y%m%d')}.md")