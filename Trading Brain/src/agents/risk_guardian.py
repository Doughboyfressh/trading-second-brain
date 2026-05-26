# src/agents/risk_guardian.py
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from datetime import datetime

class RiskGuardian(BaseAgent):
    def __init__(self):
        super().__init__(
            "RiskGuardian",
            "You are RiskGuardian. Enforce strict risk rules and ONLY approve trades that meet all criteria. Execute paper trades via Alpaca when safe."
        )
        self.fetcher = DataFetcher()
    
    def pre_trade_check(self, signal: str, symbol: str, qty: int, side: str):
        account = self.fetcher.get_alpaca_account()
        
        task = f"""Pre-trade risk check for {side} {qty} shares of {symbol}:
Signal: {signal}
Account equity: {account.equity}

Apply ALL risk rules from the vault and approve or REJECT.
If APPROVED, execute the paper trade immediately."""
        
        response = self.think_and_write(task, "03-Trade-Journal", f"PRETRADE_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}.md")
        
        if "APPROVE" in response.upper() or "EXECUTE" in response.upper():
            try:
                order = self.fetcher.place_paper_order(symbol, qty, side)
                self.vault.write_note("03-Trade-Journal", f"EXECUTED_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}.md", f"✅ PAPER TRADE EXECUTED:\n{order}")
                print(f"✅ Paper trade executed: {side} {qty} {symbol}")
            except Exception as e:
                self.vault.write_note("08-Logs", "risk_errors.md", f"Order failed: {e}", append=True)
    
    def daily_risk_sweep(self):
        self.think_and_write(
            "Perform full daily portfolio risk review and update the master risk playbook.",
            "06-Playbooks",
            f"RISK_SWEEP_{datetime.now().strftime('%Y%m%d')}.md"
        )