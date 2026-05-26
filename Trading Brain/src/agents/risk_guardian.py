# src/agents/risk_guardian.py
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from datetime import datetime
import requests
import os

class RiskGuardian(BaseAgent):
    def __init__(self):
        super().__init__(
            "RiskGuardian",
            "You are RiskGuardian. Enforce risk rules and execute paper trades. Send Telegram alerts on important events."
        )
        self.fetcher = DataFetcher()
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    def send_telegram(self, message: str):
        if self.telegram_token and self.chat_id:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                    json={"chat_id": self.chat_id, "text": message}
                )
            except:
                pass
    
    def daily_risk_sweep(self):
        response = self.think_and_write(
            "Perform full daily portfolio risk review and update the master risk playbook.",
            "06-Playbooks",
            f"RISK_SWEEP_{datetime.now().strftime('%Y%m%d')}.md"
        )
        self.send_telegram(f"🛡️ Daily Risk Sweep Complete\n{response[:300]}...")