# src/agents/strategist.py
from src.agents.base import BaseAgent
from src.historical_loader import load_performance_stats
from src.llm import TradingLLM
from datetime import datetime


class Strategist(BaseAgent):
    def __init__(self):
        super().__init__(
            "Strategist",
            "You are Strategist, an expert trading strategist. "
            "Create and refine high-edge strategies with: name, type, entry/exit rules, "
            "position sizing, regime filters, and risk parameters. "
            "Integrate backtest lessons. Output clean actionable markdown.",
            model=TradingLLM.SONNET,   # needs deep reasoning
            max_tokens=2000,
            rag_top_k=4,
            temperature=0.30,   # creative strategy refinement — higher variance = better exploration
        )

    def _load_strategy_stats(self, strategy_name: str) -> str:
        """
        Load per-ticker win/loss/PF stats for *strategy_name* from
        performance_stats.json. Returns a formatted block the LLM can
        use to make data-driven refinement decisions.
        """
        stats = load_performance_stats()
        if not stats:
            return ""

        sessions = [s for s in stats.get("by_session", [])
                    if s.get("strategy") == strategy_name]
        if not sessions:
            return ""

        agg = stats.get("by_strategy", {}).get(strategy_name, {})
        lines = [
            f"\n\nHISTORICAL PERFORMANCE DATA FOR {strategy_name}:",
            f"Source: 10-year walk-forward backtest ({stats.get('generated', '')[:10]})",
            f"Capital: ${stats.get('capital', 100000):,.0f} | "
            f"Overall: {agg.get('total_wins', 0)}W / {agg.get('total_losses', 0)}L "
            f"({agg.get('avg_win_rate', 0):.1f}% avg win rate) | "
            f"Avg PF: {agg.get('avg_profit_factor', 0):.3f} | "
            f"Avg Return: {agg.get('avg_return_pct', 0):+.1f}% | "
            f"Avg P&L: ${agg.get('avg_pnl_usd', 0):+,.0f}",
            "",
            f"  {'Ticker':<7} {'Wins':<6} {'Losses':<8} {'Win%':<7} "
            f"{'PF':<7} {'Expect/trade':<14} {'Return%':<10} {'P&L($100k)'}",
            "  " + "-" * 72,
        ]
        for s in sorted(sessions, key=lambda x: -x.get("profit_factor", 0)):
            pf_tag = " <<BEST>>" if s["profit_factor"] >= 0.85 else (
                     " <<AVOID>>" if s["profit_factor"] < 0.40 else "")
            lines.append(
                f"  {s['ticker']:<7} {s['wins']:<6} {s['losses']:<8} "
                f"{s['win_rate']:.1f}%  {s['profit_factor']:<7.3f} "
                f"{s['expectancy_pct']:+.3f}%        "
                f"{s['return_pct']:+.1f}%     ${s['pnl_usd']:+,.0f}{pf_tag}"
            )
        lines += [
            "",
            "REFINEMENT PRIORITIES (based on the data above):",
            "  - Tickers marked <<BEST>> have the highest profit factor — "
            "study what makes them work and generalise those conditions.",
            "  - Tickers marked <<AVOID>> historically destroyed capital — "
            "identify what structural incompatibility causes failure and add a filter.",
            f"  - A PF of {agg.get('avg_profit_factor', 0):.3f} means for every $1 won, "
            f"${1/agg['avg_profit_factor']:.2f} is lost on average. "
            "To break even PF must reach 1.0.",
        ]
        return "\n".join(lines)

    def create_new_strategy(self, idea: str):
        self.think_and_write(
            f"Create a complete trading strategy from this idea: {idea}",
            "02-Strategies",
            f"NEW_{idea.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.md",
        )

    def refine_strategy(self, strategy_name: str):
        perf_block = self._load_strategy_stats(strategy_name)
        self.think_and_write(
            f"Refine '{strategy_name}' using all backtest results and risk lessons in the vault."
            f"{perf_block}\n\n"
            f"Using the win/loss data above, identify EXACTLY which tickers and conditions "
            f"produce the best profit factor, then update the strategy rules to:\n"
            f"  1. Add a regime/condition filter that isolates high-PF setups.\n"
            f"  2. Add a ticker-exclusion rule for those with PF < 0.40.\n"
            f"  3. Adjust entry thresholds based on which parameter combos survived best.\n"
            f"Output the updated full strategy document with specific rule changes cited.",
            "02-Strategies",
            f"{strategy_name.replace(' ','_')}.md",
        )

    def distill_backtest_lessons(self, backtest_report: str):
        self.think_and_write(
            f"Distill key lessons and rule changes from this backtest:\n\n{backtest_report}",
            "02-Strategies",
            f"lessons_distilled_{datetime.now().strftime('%Y%m%d')}.md",
        )
