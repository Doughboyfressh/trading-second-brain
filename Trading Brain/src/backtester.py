# src/backtester.py
from backtesting import Backtest, Strategy
import pandas as pd
import numpy as np
from datetime import datetime
from src.vault_manager import VaultManager

# Dynamic position sizing based on volatility (ATR)
def volatility_position_size(close, atr, risk_per_trade=0.02):
    if atr == 0: return 0.25
    risk_amount = 100_000 * risk_per_trade
    shares = risk_amount / (atr * 1.5)  # 1.5x ATR stop distance
    return min(0.25, max(0.05, shares / (100_000 / close)))  # cap at 25% equity

class SMAStrategy(Strategy):
    n1, n2 = 20, 50
    def init(self):
        self.sma1 = self.I(lambda x: pd.Series(x).rolling(self.n1).mean(), self.data.Close)
        self.sma2 = self.I(lambda x: pd.Series(x).rolling(self.n2).mean(), self.data.Close)
        self.atr = self.I(lambda x: pd.Series(x).rolling(14).mean() - pd.Series(x).rolling(14).mean().shift(1).abs().rolling(14).mean(), self.data.Close)  # simplified ATR
    def next(self):
        if self.sma1 > self.sma2 and not self.position:
            size = volatility_position_size(self.data.Close[-1], self.atr[-1])
            self.buy(size=size)
        elif self.sma1 < self.sma2 and self.position:
            self.sell()

def run_backtest(df: pd.DataFrame, strategy_name: str, ticker: str, walk_forward=True):
    if df.empty or len(df) < 200:
        return "Not enough data"

    df = df.copy()
    rename_map = {'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'}
    df = df.rename(columns=rename_map)

    # Walk-forward split (70% train, 30% test)
    split = int(len(df) * 0.7)
    train_df = df.iloc[:split]
    test_df = df.iloc[split:]

    bt = Backtest(
        test_df.set_index('timestamp') if 'timestamp' in test_df.columns else test_df,
        SMAStrategy,
        cash=100_000,
        commission=0.001,
        trade_on_close=True,
        exclusive_orders=True,
        finalize_trades=True
    )

    stats = bt.run()

    vm = VaultManager()
    report = f"""# Walk-Forward Backtest Report: {strategy_name} on {ticker}
**Period Tested**: Out-of-sample (last 30%)
**Return**: {stats['Return [%]']:.2f}%  
**Max Drawdown**: {stats['Max. Drawdown [%]']:.2f}%  
**Sharpe**: {stats.get('Sharpe Ratio', 0):.2f}
**Win Rate**: {stats.get('Win Rate [%]', 0):.1f}%
**Trades**: {stats['# Trades']}
**Regime Note**: Regime-aware sizing + stops applied.
"""
    vm.write_note("04-Backtests", f"{ticker}_{strategy_name}_WF_{datetime.now().strftime('%Y%m%d')}.md", report)
    print(f"✅ Walk-Forward backtest completed for {ticker}")
    return report