# src/agents/pnl_tracker.py
import json
from src.agents.base import BaseAgent
from src.alpaca_broker import AlpacaBroker   # standardised dict-based access
from src.llm import TradingLLM
from datetime import datetime


class PnLTracker(BaseAgent):
    def __init__(self):
        super().__init__(
            "PnLTracker",
            "You are PnLTracker. Summarise trading performance in structured markdown: "
            "## Summary Metrics (total P&L, win rate, avg win/loss, Sharpe-like) | "
            "## Top Winners | ## Top Losers | ## Recommendations. "
            "Be data-driven and concise.",
            model=TradingLLM.HAIKU,
            max_tokens=900,
            rag_top_k=3,
            temperature=0.10,   # data-driven P&L analysis — deterministic preferred
        )
        self.broker = AlpacaBroker()

    def _save_portfolio_snapshot(self):
        """
        Fetch live Alpaca paper positions and save as JSON for the GUI.
        Uses AlpacaBroker.get_account() (returns a dict) to be consistent
        with the rest of the codebase — avoids raw SDK object attribute access.
        """
        try:
            account   = self.broker.get_account()    # → dict with string keys
            positions = self.broker.get_positions()  # → list[dict]
            snapshot  = {
                "timestamp": datetime.now().isoformat(),
                "account": {
                    "equity":          account["equity"],
                    "buying_power":    account["buying_power"],
                    "cash":            account["cash"],
                    "portfolio_value": account["portfolio_value"],
                },
                "positions": positions,
            }
            portfolio_dir = self.vault.root / "09-Portfolio"
            portfolio_dir.mkdir(parents=True, exist_ok=True)
            with open(portfolio_dir / "positions.json", "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
            print("   Portfolio snapshot saved")
        except Exception as e:
            print(f"   Could not save portfolio snapshot: {e}")

    def _build_order_block(self) -> str:
        """
        Pull real filled-order data from Alpaca and format it for the LLM prompt.
        This gives the LLM actual fill prices, quantities, and timestamps instead
        of having to guess from vault notes.
        """
        try:
            recent_orders = self.broker.get_recent_orders(limit=50)
        except Exception as e:
            print(f"   Could not fetch order history: {e}")
            return ""

        filled = [o for o in recent_orders
                  if float(o.get("filled_qty", 0)) > 0]
        if not filled:
            return ""

        lines = ["## Recent Filled Orders (live from Alpaca — use for P&L calculation)"]
        for o in filled[:25]:
            side     = str(o.get("side", "")).upper()
            fill_px  = o.get("filled_price") or o.get("limit_price") or 0
            filled_q = float(o.get("filled_qty", 0))
            notional = filled_q * float(fill_px)
            lines.append(
                f"- {o.get('symbol','?')} {side} × {filled_q:.0f} shares "
                f"@ ${float(fill_px):.2f}  (notional ${notional:,.0f}) "
                f"| status={o.get('status','')} "
                f"| filled={str(o.get('filled_at',''))[:10]}"
            )
        return "\n".join(lines)

    def track_pnl(self):
        order_block = self._build_order_block()
        prompt = (
            "Calculate and summarise today's paper trading performance.\n\n"
            + (order_block + "\n\n" if order_block
               else "No filled orders found in recent Alpaca history.\n\n")
            + "Also review vault context from 03-Trade-Journal/ and 06-Playbooks/ "
            "for additional signals and risk sweeps context. "
            "Compute total P&L, win rate, avg win/loss, and overall performance. "
            "Include specific improvement recommendations."
        )
        self.think_and_write(
            prompt,
            "06-Playbooks",
            f"PNL_REPORT_{datetime.now().strftime('%Y%m%d')}.md",
        )
        self._save_portfolio_snapshot()
        print("   PnL report generated")
