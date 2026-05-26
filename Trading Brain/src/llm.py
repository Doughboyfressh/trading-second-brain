# src/llm.py
import anthropic
from config import ANTHROPIC_API_KEY

class TradingLLM:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        # Upgrade #1: Claude 3.5 Sonnet (much smarter than Haiku)
        self.model = "claude-sonnet-4-6"
    
    def query(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0.15,          # Lower = more consistent & logical trading decisions
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text