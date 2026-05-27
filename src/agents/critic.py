# src/agents/critic.py
from src.agents.base import BaseAgent
from src.llm import TradingLLM
from pathlib import Path
from datetime import datetime


class Critic(BaseAgent):
    def __init__(self):
        super().__init__(
            "Critic",
            "You are Critic. Brutally and concisely review strategies, backtests, signals, "
            "or risk decisions.\n"
            "Structure every review with exactly these sections:\n"
            "## Fatal Flaws — what could cause real losses (max 3 bullets, cite numbers)\n"
            "## Risk Violations — position sizing, stop placement, regime mismatches\n"
            "## Weak Reasoning — where the logic is vague, circular, or overfitted\n"
            "## Concrete Fixes — specific parameter changes or rule additions\n\n"
            "For SIGNAL reviews: flag any ticker with R:R < 1:2, confidence < 65%, "
            "stop too tight (< 0.5× ATR), or entry chasing extended moves.\n"
            "For RISK SWEEP reviews: check if rejections are correctly reasoned and "
            "approvals are not rubber-stamped.",
            model=TradingLLM.SONNET,   # needs adversarial reasoning
            max_tokens=1400,
            rag_top_k=3,
            temperature=0.20,   # adversarial review — some variability catches more issues
        )

    def review_note(self, folder: str, filename: str):
        """Review a vault note and save the critique to 08-Logs/."""
        # Try to load file directly first (avoids RAG staleness for fresh files)
        direct_path = self.vault.root / folder / filename
        if direct_path.exists():
            content = direct_path.read_text(encoding="utf-8", errors="replace")
        else:
            content = self.vault.read_note(folder, filename)

        if not content or not content.strip():
            print(f"⚠️  Critic: {filename} is empty or not found — skipping")
            return

        review_type = self._classify_note(folder, filename)
        self.think_and_write(
            f"Review this {review_type} for flaws, risk issues, and improvements:\n\n{content}",
            "08-Logs",
            f"CRITIC_REVIEW_{filename}",
        )
        print(f"✅ Critic reviewed {filename}")

    @staticmethod
    def _classify_note(folder: str, filename: str) -> str:
        """Return a short description of note type to make the prompt more specific."""
        name = filename.lower()
        if "signal" in name:
            return "signals report — check each signal's R:R, confidence, stop placement"
        if "risk_sweep" in name or "risk" in name:
            return "risk sweep — verify each APPROVE/REJECT decision is correctly reasoned"
        if "strategy" in name or "sma" in name or "ema" in name or "macd" in name:
            return "trading strategy"
        if "backtest" in name or "optimized" in name:
            return "backtest report — focus on curve-fitting, sample size, and realistic assumptions"
        if "ranking" in name:
            return "strategy ranking — verify tier assignments and action bullets are actionable"
        return "trading note"
