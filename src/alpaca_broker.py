# src/alpaca_broker.py
"""
AlpacaBroker — clean wrapper around alpaca-py for paper (and live) trading.
Handles bracket orders, position queries, order history, and market-hours checks.
"""
from alpaca.trading.client  import TradingClient
from alpaca.trading.requests import (
    LimitOrderRequest, MarketOrderRequest,
    StopLossRequest, TakeProfitRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import (
    OrderSide, OrderClass, TimeInForce, QueryOrderStatus,
)
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY


class AlpacaBroker:
    def __init__(self):
        self.client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

    # ── Clock / market hours ─────────────────────────────────────────────────
    def market_is_open(self) -> bool:
        """Return True if the US equity market is currently open."""
        try:
            return self.client.get_clock().is_open
        except Exception:
            return False

    def market_hours(self) -> dict:
        """Return dict with is_open, next_open, next_close."""
        try:
            clk = self.client.get_clock()
            return {
                "is_open":    clk.is_open,
                "next_open":  str(clk.next_open)[:19].replace("T", " "),
                "next_close": str(clk.next_close)[:19].replace("T", " "),
            }
        except Exception:
            return {"is_open": False, "next_open": "—", "next_close": "—"}

    def is_trading_day(self, check_date=None) -> bool:
        """
        Return True if *check_date* (default: today) is a US market trading day.

        Queries the Alpaca market calendar API, which accounts for weekends AND
        US market holidays (e.g. July 4th, Thanksgiving, Christmas).

        Falls back to a simple weekday check (Mon–Fri) if the SDK version doesn't
        support GetCalendarRequest or the API call fails — so the daily loop is
        never blocked by a network hiccup.
        """
        from datetime import date as _date
        if check_date is None:
            check_date = _date.today()
        try:
            from alpaca.trading.requests import GetCalendarRequest
            date_str = check_date.isoformat()
            calendar = self.client.get_calendar(
                GetCalendarRequest(start=date_str, end=date_str)
            )
            return bool(calendar)
        except ImportError:
            # Older alpaca-py without GetCalendarRequest — weekday fallback
            return check_date.weekday() < 5
        except Exception:
            # API error (network down, bad keys, etc.) — assume trading day
            return check_date.weekday() < 5

    # ── Account ──────────────────────────────────────────────────────────────
    def get_account(self) -> dict:
        acc = self.client.get_account()
        return {
            "equity":             float(acc.equity),
            "cash":               float(acc.cash),
            "buying_power":       float(acc.buying_power),
            "portfolio_value":    float(acc.portfolio_value),
            "status":             str(acc.status),
            "pattern_day_trader": bool(acc.pattern_day_trader),
            "daytrade_count":     int(acc.daytrade_count or 0),
        }

    # ── Positions ────────────────────────────────────────────────────────────
    def get_positions(self) -> list[dict]:
        try:
            return [self._pos_to_dict(p) for p in self.client.get_all_positions()]
        except Exception:
            return []

    def has_position(self, symbol: str) -> bool:
        """True if we already hold a filled position OR a pending order for this symbol."""
        # Check filled positions
        try:
            pos = self.client.get_open_position(symbol)
            if float(pos.qty) > 0:
                return True
        except Exception:
            pass
        # Also check pending/open orders — prevents doubling up on same-day re-runs
        try:
            open_orders = self.client.get_orders(
                filter=GetOrdersRequest(status=QueryOrderStatus.OPEN)
            )
            for o in open_orders:
                if o.symbol == symbol:
                    return True
        except Exception:
            pass
        return False

    def close_position(self, symbol: str) -> dict | None:
        """Market-close a single position. Returns order dict or None."""
        try:
            o = self.client.close_position(symbol)
            return self._order_to_dict(o)
        except Exception as e:
            print(f"   close_position({symbol}) failed: {e}")
            return None

    def close_all_positions(self) -> int:
        """Emergency flatten — cancel all orders then close every position.
        Returns number of close orders submitted."""
        try:
            self.client.cancel_orders()
        except Exception:
            pass
        try:
            orders = self.client.close_all_positions(cancel_orders=True)
            return len(orders) if orders else 0
        except Exception as e:
            print(f"   close_all_positions failed: {e}")
            return 0

    def _pos_to_dict(self, p) -> dict:
        return {
            "symbol":          p.symbol,
            "qty":             float(p.qty),
            "side":            str(p.side),
            "avg_entry":       float(p.avg_entry_price),
            "current_price":   float(p.current_price or 0),
            "market_value":    float(p.market_value or 0),
            "unrealized_pl":   float(p.unrealized_pl or 0),
            "unrealized_plpc": float(p.unrealized_plpc or 0) * 100,
        }

    # ── Orders ───────────────────────────────────────────────────────────────
    def get_open_orders(self) -> list[dict]:
        try:
            orders = self.client.get_orders(
                filter=GetOrdersRequest(status=QueryOrderStatus.OPEN)
            )
            return [self._order_to_dict(o) for o in orders]
        except Exception:
            return []

    def get_recent_orders(self, limit: int = 30) -> list[dict]:
        try:
            orders = self.client.get_orders(
                filter=GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
            )
            return [self._order_to_dict(o) for o in orders]
        except Exception:
            return []

    def cancel_all_orders(self) -> int:
        try:
            cancelled = self.client.cancel_orders()
            return len(cancelled) if cancelled else 0
        except Exception:
            return 0

    def _order_to_dict(self, o) -> dict:
        return {
            "id":            str(o.id),
            "symbol":        o.symbol,
            "qty":           float(o.qty or 0),
            "filled_qty":    float(o.filled_qty or 0),
            "side":          str(o.side),
            "type":          str(o.type),
            "status":        str(o.status),
            "order_class":   str(o.order_class or ""),
            "limit_price":   float(o.limit_price)      if o.limit_price      else None,
            "stop_price":    float(o.stop_price)        if o.stop_price       else None,
            "filled_price":  float(o.filled_avg_price) if o.filled_avg_price else None,
            "created_at":    str(o.created_at)[:19]    if o.created_at       else "",
            "filled_at":     str(o.filled_at)[:19]     if o.filled_at        else "",
            "legs":          len(o.legs) if o.legs else 0,
        }

    # ── Order placement ──────────────────────────────────────────────────────
    def place_bracket_order(
        self,
        symbol:           str,
        side:             str,
        qty:              float,
        limit_price:      float,
        stop_price:       float,
        take_profit_price: float,
    ) -> dict:
        """
        Limit entry + attached stop-loss + take-profit bracket.
        Alpaca manages the exit legs automatically after fill.
        Raises on failure — caller should catch and handle.
        """
        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        req = LimitOrderRequest(
            symbol=symbol,
            qty=round(qty),                    # whole shares only
            side=order_side,
            time_in_force=TimeInForce.GTC,     # Good-Till-Cancelled: survives overnight
            limit_price=round(limit_price, 2),
            order_class=OrderClass.BRACKET,
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
            take_profit=TakeProfitRequest(limit_price=round(take_profit_price, 2)),
        )
        order = self.client.submit_order(req)
        return self._order_to_dict(order)

    def place_market_order(self, symbol: str, side: str, qty: float) -> dict:
        """Simple market order — for manual GUI trades."""
        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=symbol,
            qty=round(qty),
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )
        order = self.client.submit_order(req)
        return self._order_to_dict(order)

    def place_limit_order(
        self, symbol: str, side: str, qty: float, limit_price: float
    ) -> dict:
        """Limit order without bracket — for manual GUI trades."""
        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        req = LimitOrderRequest(
            symbol=symbol,
            qty=round(qty),
            side=order_side,
            time_in_force=TimeInForce.DAY,
            limit_price=round(limit_price, 2),
        )
        order = self.client.submit_order(req)
        return self._order_to_dict(order)

    # ── Position sizing ──────────────────────────────────────────────────────
    @staticmethod
    def compute_position_size(
        equity:    float,
        entry:     float,
        stop:      float,
        risk_pct:  float = 0.01,   # 1% equity at risk per trade
        max_pct:   float = 0.05,   # max 5% of portfolio per position
    ) -> int:
        """
        ATR-based Kelly sizing: risk_pct of equity / dollar risk per share.
        Returns integer share count ≥ 1, capped at max_pct of portfolio.
        """
        risk_per_share = abs(entry - stop)
        if risk_per_share < 0.01:
            return 1
        risk_amount = equity * risk_pct
        raw_shares  = risk_amount / risk_per_share
        max_shares  = int((equity * max_pct) / max(entry, 0.01))
        shares      = int(min(raw_shares, max_shares))
        return max(1, shares)
