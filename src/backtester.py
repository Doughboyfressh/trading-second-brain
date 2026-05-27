# src/backtester.py
"""
Backtesting engine for the Trading Brain.

Strategies
----------
Original (5):  SMA_Crossover, RSI_MeanReversion, MACD_Momentum,
               BB_Reversion, EMA_Momentum
New (3):       Volume_Breakout, Trend_Pullback, ROC_Momentum

All strategies are walk-forward tested: 70% in-sample (discarded) /
30% out-of-sample (reported).

Public API
----------
    run_backtest(df, strategy_name, ticker)          -> str  (markdown report)
    run_backtest_full(df, strategy_name, ticker)     -> (str, df | None)
    run_param_search(df, strategy_name, ticker)      -> dict (best params + OOS stats)
    STRATEGIES                                        dict[name -> class]
    _PARAM_GRIDS                                      dict[name -> grid kwargs]
"""
from backtesting import Backtest, Strategy
import pandas as pd
import numpy as np
import math
import warnings
from datetime import datetime
from src.vault_manager import VaultManager
from config import BACKTEST_CASH, BACKTEST_COMMISSION

# ── Suppress noisy-but-harmless warnings from backtesting.py ─────────────────
#
# 1. "insufficient margin"  — fires when a param combo loses so much that a
#    2%-risk order exceeds remaining equity.  Now fixed via self.equity sizing,
#    kept as belt-and-suspenders.
#
# 2. "divide by zero … equity_log_returns"  — numpy RuntimeWarning that fires
#    in _stats.py when a strategy's equity hits 0 (account ruin).  The scoring
#    function already returns -999 for runs with < 10 trades, so these combos
#    are discarded — the warning adds no information.
#
# 3. "multiprocessing.get_start_method() == 'spawn'"  — Windows-specific advisory
#    about thread vs process parallelism in bt.optimize().  We use thread-based
#    parallelism intentionally (avoids __main__ guard requirement on Windows).
#
warnings.filterwarnings("ignore", message=".*insufficient margin.*",
                        category=UserWarning)
warnings.filterwarnings("ignore", message=".*divide by zero.*",
                        category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*multiprocessing.*spawn.*",
                        category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*If you want to use multi-process.*",
                        category=RuntimeWarning)


# ── ATR helper (numpy-safe) ───────────────────────────────────────────────────
def _true_atr(h, l, c, period=14):
    """True ATR from numpy arrays (for use inside backtesting.py Strategy.I)."""
    s_h, s_l, s_c = pd.Series(h), pd.Series(l), pd.Series(c)
    prev_c = s_c.shift(1)
    tr     = pd.concat([s_h - s_l, (s_h - prev_c).abs(), (s_l - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean().values


def _position_size(close: float, atr: float,
                   equity: float | None = None,
                   risk_per_trade: float = 0.02) -> float:
    """
    ATR-based fractional position size.

    Uses *equity* (the strategy's current account value) rather than the fixed
    BACKTEST_CASH constant so that the fraction scales down correctly after
    drawdowns — this eliminates the "insufficient margin" broker rejections
    that occur when equity < BACKTEST_CASH.

    Returns a fraction in [0.02, 0.18] of current equity.
    """
    if equity is None or equity <= 0:
        equity = BACKTEST_CASH
    if atr is None or (isinstance(atr, float) and (np.isnan(atr) or atr == 0)):
        return 0.08
    risk_amount = equity * risk_per_trade          # e.g. 2 % of current equity
    shares      = risk_amount / (atr * 1.5)        # shares to risk one stop-width
    fraction    = shares / max(equity / close, 1e-9)
    return float(np.clip(fraction, 0.02, 0.18))    # max 18 % — prevents margin cancels


# ── Original strategies ───────────────────────────────────────────────────────

class SMAStrategy(Strategy):
    n1, n2 = 20, 50

    def init(self):
        c = self.data.Close
        self.sma1 = self.I(lambda x: pd.Series(x).rolling(self.n1).mean().values, c)
        self.sma2 = self.I(lambda x: pd.Series(x).rolling(self.n2).mean().values, c)
        self.atr_ = self.I(_true_atr, self.data.High, self.data.Low, c)

    def next(self):
        if self.sma1[-1] > self.sma2[-1] and not self.position:
            self.buy(size=_position_size(self.data.Close[-1], self.atr_[-1], self.equity))
        elif self.sma1[-1] < self.sma2[-1] and self.position:
            self.sell()


class RSIMeanReversionStrategy(Strategy):
    rsi_period = 14
    oversold   = 32
    overbought = 68

    def init(self):
        def _rsi(x):
            s     = pd.Series(x)
            delta = s.diff()
            gain  = delta.clip(lower=0).ewm(com=self.rsi_period - 1, adjust=False).mean()
            loss  = (-delta).clip(lower=0).ewm(com=self.rsi_period - 1, adjust=False).mean()
            return (100 - 100 / (1 + gain / loss.replace(0, 1e-10))).values

        self.rsi  = self.I(_rsi, self.data.Close)
        self.atr_ = self.I(_true_atr, self.data.High, self.data.Low, self.data.Close)

    def next(self):
        if self.rsi[-1] < self.oversold and not self.position:
            self.buy(size=_position_size(self.data.Close[-1], self.atr_[-1], self.equity))
        elif self.rsi[-1] > self.overbought and self.position:
            self.sell()


class MACDMomentumStrategy(Strategy):
    fast, slow, sig = 12, 26, 9

    def init(self):
        def _macd_hist(x):
            s    = pd.Series(x)
            ema_f = s.ewm(span=self.fast, adjust=False).mean()
            ema_s = s.ewm(span=self.slow, adjust=False).mean()
            macd  = ema_f - ema_s
            sig_  = macd.ewm(span=self.sig, adjust=False).mean()
            return (macd - sig_).values

        self.hist = self.I(_macd_hist, self.data.Close)
        self.atr_ = self.I(_true_atr, self.data.High, self.data.Low, self.data.Close)

    def next(self):
        if self.hist[-1] > 0 and self.hist[-2] <= 0 and not self.position:
            self.buy(size=_position_size(self.data.Close[-1], self.atr_[-1], self.equity))
        elif self.hist[-1] < 0 and self.hist[-2] >= 0 and self.position:
            self.sell()


class BollingerReversionStrategy(Strategy):
    """Buy at lower Bollinger Band, sell at upper — pure mean-reversion."""
    period   = 20
    std_mult = 2.0

    def init(self):
        def _bb_pct(x):
            s     = pd.Series(x)
            mid   = s.rolling(int(self.period)).mean()
            std   = s.rolling(int(self.period)).std()
            upper = mid + self.std_mult * std
            lower = mid - self.std_mult * std
            return ((s - lower) / (upper - lower + 1e-9)).values

        self.bb   = self.I(_bb_pct, self.data.Close)
        self.atr_ = self.I(_true_atr, self.data.High, self.data.Low, self.data.Close)

    def next(self):
        if self.bb[-1] < 0.12 and not self.position:
            self.buy(size=_position_size(self.data.Close[-1], self.atr_[-1], self.equity))
        elif self.bb[-1] > 0.88 and self.position:
            self.sell()


class EMAMomentumStrategy(Strategy):
    """Triple EMA stack: 8/21/55 — trend-following with tight ATR stop."""
    f, m, s = 8, 21, 55

    def init(self):
        c = self.data.Close
        self.ema_f = self.I(lambda x: pd.Series(x).ewm(span=self.f,  adjust=False).mean().values, c)
        self.ema_m = self.I(lambda x: pd.Series(x).ewm(span=self.m,  adjust=False).mean().values, c)
        self.ema_s = self.I(lambda x: pd.Series(x).ewm(span=self.s,  adjust=False).mean().values, c)
        self.atr_  = self.I(_true_atr, self.data.High, self.data.Low, c)
        self._stop  = None

    def next(self):
        bullish_stack = self.ema_f[-1] > self.ema_m[-1] > self.ema_s[-1]
        bearish_stack = self.ema_f[-1] < self.ema_m[-1] < self.ema_s[-1]

        if bullish_stack and not self.position:
            self._stop = self.data.Close[-1] - 2.0 * self.atr_[-1]
            self.buy(size=_position_size(self.data.Close[-1], self.atr_[-1], self.equity))
        elif self.position:
            trail = self.data.Close[-1] - 2.0 * self.atr_[-1]
            if self._stop:
                self._stop = max(self._stop, trail)
            if bearish_stack or (self._stop and self.data.Close[-1] < self._stop):
                self.sell()
                self._stop = None


# ── NEW strategies ────────────────────────────────────────────────────────────

class VolumeBreakoutStrategy(Strategy):
    """
    Buy when price breaks above the N-day high *and* volume spikes above
    vol_mult × 20-day average.  High-volume breakouts confirm institutional
    participation and have significantly lower false-positive rates.
    """
    breakout_period = 20   # rolling high lookback
    vol_mult        = 1.5  # volume must be this × 20d avg to qualify

    def init(self):
        h = self.data.High
        v = self.data.Volume
        c = self.data.Close
        self.high_n  = self.I(
            lambda x: pd.Series(x).rolling(self.breakout_period).max().shift(1).values, h
        )
        self.avg_vol = self.I(lambda x: pd.Series(x).rolling(20).mean().values, v)
        self.atr_    = self.I(_true_atr, h, self.data.Low, c)

    def next(self):
        vol_ok   = self.data.Volume[-1] > self.vol_mult * (self.avg_vol[-1] or 1)
        breakout = self.data.Close[-1] > (self.high_n[-1] or 0)

        if breakout and vol_ok and not self.position:
            self.buy(size=_position_size(self.data.Close[-1], self.atr_[-1], self.equity))
        elif self.position:
            # Exit when price falls back below breakout level (failed breakout)
            if self.data.Close[-1] < (self.high_n[-1] or 0) * 0.97:
                self.sell()


class TrendPullbackStrategy(Strategy):
    """
    Buys a pullback to the fast EMA during a confirmed uptrend
    (medium EMA above long EMA = golden-cross regime).
    Exits below the medium EMA.

    Logic: in uptrends, dips to EMA are buying opportunities.
    Regime filter prevents buying in downtrends.
    """
    ema_fast    = 20    # fast EMA for the pullback level
    ema_trend   = 50    # medium EMA — must be above ema_primary
    ema_primary = 200   # primary trend filter
    pullback_pct = 2    # price within this % of fast EMA to qualify (integer for optimizer)

    def init(self):
        c = self.data.Close
        self.ema_f = self.I(lambda x: pd.Series(x).ewm(span=self.ema_fast,    adjust=False).mean().values, c)
        self.ema_t = self.I(lambda x: pd.Series(x).ewm(span=self.ema_trend,   adjust=False).mean().values, c)
        self.ema_p = self.I(lambda x: pd.Series(x).ewm(span=self.ema_primary, adjust=False).mean().values, c)
        self.atr_  = self.I(_true_atr, self.data.High, self.data.Low, c)

    def next(self):
        uptrend  = (self.ema_t[-1] or 0) > (self.ema_p[-1] or 0)
        ema_f    = self.ema_f[-1] or self.data.Close[-1]
        near_ema = abs(self.data.Close[-1] - ema_f) / ema_f < (self.pullback_pct / 100)
        above_f  = self.data.Close[-1] >= ema_f

        if uptrend and near_ema and above_f and not self.position:
            self.buy(size=_position_size(self.data.Close[-1], self.atr_[-1], self.equity))
        elif self.position:
            if self.data.Close[-1] < (self.ema_t[-1] or 0):
                self.sell()


class ROCMomentumStrategy(Strategy):
    """
    Rate-of-Change momentum: buy when the N-period ROC is positive AND
    price is above a long-term SMA (trend filter).  Sells when momentum
    reverses.

    ROC momentum is one of the most robust factors in academic research
    (Jegadeesh & Titman 1993 and many replications).
    """
    roc_period  = 20    # lookback for rate-of-change
    roc_thresh  = 2     # minimum ROC % to trigger entry (integer for optimizer)
    sma_filter  = 100   # long-term SMA trend filter

    def init(self):
        c = self.data.Close
        self.roc = self.I(
            lambda x: (pd.Series(x).pct_change(self.roc_period) * 100).values, c
        )
        self.sma = self.I(
            lambda x: pd.Series(x).rolling(self.sma_filter).mean().values, c
        )
        self.atr_ = self.I(_true_atr, self.data.High, self.data.Low, c)

    def next(self):
        above_sma = self.data.Close[-1] > (self.sma[-1] or 0)
        strong_momentum = (self.roc[-1] or 0) > self.roc_thresh

        if above_sma and strong_momentum and not self.position:
            self.buy(size=_position_size(self.data.Close[-1], self.atr_[-1], self.equity))
        elif self.position:
            if (self.roc[-1] or 0) < 0 or not above_sma:
                self.sell()


# ── Strategy registry ─────────────────────────────────────────────────────────
STRATEGIES = {
    "SMA_Crossover":      SMAStrategy,
    "RSI_MeanReversion":  RSIMeanReversionStrategy,
    "MACD_Momentum":      MACDMomentumStrategy,
    "BB_Reversion":       BollingerReversionStrategy,
    "EMA_Momentum":       EMAMomentumStrategy,
    # New strategies
    "Volume_Breakout":    VolumeBreakoutStrategy,
    "Trend_Pullback":     TrendPullbackStrategy,
    "ROC_Momentum":       ROCMomentumStrategy,
}


# ── Parameter grids for grid-search optimisation ──────────────────────────────
# Each key is a strategy name; values are keyword arguments passed to bt.optimize().
# 'constraint' (if present) is a callable(params) -> bool filtering invalid combos.
# Keep grids small (≤30 combos per strategy) for fast batch optimisation.

_PARAM_GRIDS: dict[str, dict] = {
    "SMA_Crossover": {
        "n1":         [10, 15, 20, 25],
        "n2":         [40, 50, 60, 70],
        "constraint": lambda p: p.n1 < p.n2,
    },
    "RSI_MeanReversion": {
        "rsi_period": [10, 14],
        "oversold":   [25, 30, 35],
        "overbought": [65, 70, 75],
    },
    "MACD_Momentum": {
        "fast":       [8, 12],
        "slow":       [21, 26],
        "sig":        [7, 9],
        "constraint": lambda p: p.fast < p.slow,
    },
    "BB_Reversion": {
        "period":     [15, 20, 25],
        "std_mult":   [1.8, 2.0, 2.2],
    },
    "EMA_Momentum": {
        "f":          [5, 8, 10],
        "m":          [18, 21, 25],
        "s":          [45, 55, 65],
        "constraint": lambda p: p.f < p.m < p.s,
    },
    "Volume_Breakout": {
        "breakout_period": [15, 20, 25],
        "vol_mult":        [1.3, 1.5, 2.0],
    },
    "Trend_Pullback": {
        "ema_fast":    [15, 20, 25],
        "ema_trend":   [45, 50, 60],
        "pullback_pct": [1, 2, 3],
        "constraint":  lambda p: p.ema_fast < p.ema_trend,
    },
    "ROC_Momentum": {
        "roc_period":  [15, 20, 25],
        "roc_thresh":  [1, 2, 3],
        "sma_filter":  [80, 100, 120],
    },
}


# ── Shared backtest core ──────────────────────────────────────────────────────

def _prep_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rename OHLCV columns, set DatetimeIndex, split 70/30."""
    df = df.copy()
    rename = {"open": "Open", "high": "High", "low": "Low",
              "close": "Close", "volume": "Volume"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    split   = int(len(df) * 0.7)
    test_df = df.iloc[split:].copy()

    idx_col = "timestamp" if "timestamp" in test_df.columns else None
    if idx_col:
        test_df = test_df.set_index(idx_col)
    if not isinstance(test_df.index, pd.DatetimeIndex):
        test_df.index = pd.to_datetime(test_df.index, errors="coerce")

    return df, test_df


def _run_bt_core(df: pd.DataFrame, strategy_name: str,
                 extra_params: dict | None = None) -> tuple:
    """
    Prepare data, run backtest on the 30% out-of-sample slice.
    *extra_params* are applied as class-level attributes on the strategy.
    Returns (stats, test_df).
    """
    strat_cls = STRATEGIES.get(strategy_name, SMAStrategy)

    # Apply overridden parameters via a dynamic subclass
    if extra_params:
        strat_cls = type(f"{strategy_name}_Custom", (strat_cls,), dict(extra_params))

    df, test_df = _prep_df(df)

    bt    = Backtest(test_df, strat_cls, cash=BACKTEST_CASH, commission=BACKTEST_COMMISSION,
                     trade_on_close=False, exclusive_orders=True, finalize_trades=True)
    stats = bt.run()
    return stats, test_df


def _safe(val, fmt=".2f", default="N/A"):
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f) or abs(f) > 1e9:
            return default
        return format(f, fmt)
    except Exception:
        return default


def _build_report(stats, strategy_name: str, ticker: str,
                  note: str = "") -> str:
    n_trades     = int(stats.get("# Trades", 0))
    ret          = float(stats.get("Return [%]", 0))
    dd           = float(stats.get("Max. Drawdown [%]", 0) or 0)
    calmar_raw   = abs(ret / dd) if dd and dd != 0 else 0
    win_rate_pct = float(stats.get("Win Rate [%]", 0) or 0)
    n_wins       = round(win_rate_pct / 100 * n_trades)
    n_losses     = n_trades - n_wins
    pnl_usd      = ret / 100 * BACKTEST_CASH
    wl_ratio     = (f"1:{n_losses/n_wins:.2f} loss ratio"
                    if n_wins > 0 else "no winners")
    sample_note  = ""
    if n_trades < 20:
        sample_note = f"\n> WARNING: Only {n_trades} trades — Sharpe unreliable"
    extra = f"\n**Note**: {note}" if note else ""
    return (
        f"# Walk-Forward Backtest: {strategy_name} on {ticker}\n"
        f"**Return**: {ret:.2f}%  \n"
        f"**P&L**: ${pnl_usd:+,.0f} (on ${BACKTEST_CASH:,.0f} capital)\n"
        f"**Max Drawdown**: {dd:.2f}%  \n"
        f"**Sharpe**: {_safe(stats.get('Sharpe Ratio'))}\n"
        f"**Win Rate**: {_safe(stats.get('Win Rate [%]'), '.1f')}%\n"
        f"**Wins**: {n_wins} | **Losses**: {n_losses} | **Total Trades**: {n_trades}\n"
        f"**Win:Loss Ratio**: {n_wins}:{n_losses} ({wl_ratio})\n"
        f"**Calmar**: {calmar_raw:.2f}\n"
        f"**Profit Factor**: {_safe(stats.get('Profit Factor'))}\n"
        f"**Expectancy**: {_safe(stats.get('Expectancy [%]'))}%\n"
        f"**Backtest cash**: ${BACKTEST_CASH:,.0f}\n"
        f"**Execution**: next-bar open (no lookahead bias)  "
        f"| **Commission**: {BACKTEST_COMMISSION*100:.2f}% per trade (covers spread + slippage){sample_note}{extra}\n"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, strategy_name: str, ticker: str,
                 extra_params: dict | None = None) -> str:
    """Run walk-forward backtest; save to vault; return markdown report."""
    if df.empty or len(df) < 200:
        return "Not enough data (need >= 200 bars)"
    try:
        stats, _ = _run_bt_core(df, strategy_name, extra_params)
    except Exception as e:
        return f"Backtest failed: {e}"

    note   = f"params={extra_params}" if extra_params else ""
    report = _build_report(stats, strategy_name, ticker, note=note)
    vm = VaultManager()
    vm.write_note(
        "04-Backtests",
        f"{ticker}_{strategy_name}_WF_{datetime.now().strftime('%Y%m%d')}.md",
        report,
    )
    print(f"   Backtest complete: {strategy_name} on {ticker}")
    return report


def run_backtest_full(df: pd.DataFrame, strategy_name: str, ticker: str
                      ) -> tuple[str, "pd.DataFrame | None"]:
    """Like run_backtest() but also returns the equity-curve DataFrame."""
    if df.empty or len(df) < 200:
        return "Not enough data (need >= 200 bars)", None
    try:
        stats, _ = _run_bt_core(df, strategy_name)
    except Exception as e:
        return f"Backtest failed: {e}", None

    report = _build_report(stats, strategy_name, ticker)
    vm = VaultManager()
    vm.write_note(
        "04-Backtests",
        f"{ticker}_{strategy_name}_WF_{datetime.now().strftime('%Y%m%d')}.md",
        report,
    )
    print(f"   Backtest complete: {strategy_name} on {ticker}")

    try:
        eq = stats._equity_curve[["Equity", "DrawdownPct"]].copy()
        return report, eq
    except Exception:
        return report, None


def run_param_search(df: pd.DataFrame, strategy_name: str,
                     ticker: str) -> dict:
    """
    Grid-search strategy parameters on the 70% in-sample data; validate
    best params on the 30% out-of-sample slice.

    Uses ``backtesting.Backtest.optimize()`` (exhaustive grid search) and
    maximises Sharpe Ratio while requiring >= 10 trades (via constraint).

    Returns
    -------
    dict with keys:
        best_params  : {param_name: value, ...}
        oos_calmar   : float
        oos_sharpe   : float
        oos_return   : float
        oos_win_rate : float
        oos_trades   : int
        oos_report   : str  (markdown)
    Or empty dict if optimisation fails / no grid defined.
    """
    if df.empty or len(df) < 300:
        return {}

    strat_cls = STRATEGIES.get(strategy_name)
    grid      = _PARAM_GRIDS.get(strategy_name, {})
    if not strat_cls or not grid:
        return {}

    # ── Prepare in-sample (70%) slice ────────────────────────────────────────
    df = df.copy()
    rename = {"open": "Open", "high": "High", "low": "Low",
              "close": "Close", "volume": "Volume"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    split    = int(len(df) * 0.7)
    train_df = df.iloc[:split].copy()
    test_df  = df.iloc[split:].copy()

    for frame in (train_df, test_df):
        if "timestamp" in frame.columns:
            frame.set_index("timestamp", inplace=True)
        if not isinstance(frame.index, pd.DatetimeIndex):
            frame.index = pd.to_datetime(frame.index, errors="coerce")

    try:
        # Build optimize() kwargs — exclude 'constraint' (passed separately)
        opt_kwargs   = {k: v for k, v in grid.items() if k != "constraint"}
        constraint   = grid.get("constraint")

        bt_train = Backtest(train_df, strat_cls, cash=BACKTEST_CASH,
                            commission=BACKTEST_COMMISSION, trade_on_close=False,
                            exclusive_orders=True, finalize_trades=True)

        # Require min 10 trades to get a reliable Sharpe; penalise below that
        def _score(s):
            trades = int(s.get("# Trades", 0))
            if trades < 10:
                return -999.0
            sh = float(s.get("Sharpe Ratio", 0) or 0)
            return sh if math.isfinite(sh) else -999.0

        call_kw: dict = {"maximize": _score, "return_heatmap": False,
                         "return_optimization": False, **opt_kwargs}
        if constraint:
            call_kw["constraint"] = constraint

        best_stats = bt_train.optimize(**call_kw)

        # Extract best parameter values from the winning strategy class
        best_params: dict = {}
        for param_name in opt_kwargs.keys():
            val = getattr(best_stats._strategy, param_name, None)
            if val is not None:
                best_params[param_name] = val

        # ── Validate on out-of-sample ─────────────────────────────────────────
        OptCls = type(f"{strategy_name}_Opt", (strat_cls,), dict(best_params))
        bt_test = Backtest(test_df, OptCls, cash=BACKTEST_CASH,
                           commission=BACKTEST_COMMISSION, trade_on_close=False,
                           exclusive_orders=True, finalize_trades=True)
        oos = bt_test.run()

        calmar   = float(oos.get("Calmar Ratio",    0) or 0)
        sharpe   = float(oos.get("Sharpe Ratio",    0) or 0)
        ret_pct  = float(oos.get("Return [%]",      0) or 0)
        wr       = float(oos.get("Win Rate [%]",    0) or 0)
        trades   = int(oos.get("# Trades",          0))

        # Sanitise infinities / NaN
        calmar  = calmar  if math.isfinite(calmar)  else 0.0
        sharpe  = sharpe  if math.isfinite(sharpe)  else 0.0
        ret_pct = ret_pct if math.isfinite(ret_pct) else 0.0

        oos_report = _build_report(
            oos, f"{strategy_name}_Optimized", ticker,
            note=f"Best params from grid-search: {best_params}",
        )

        print(f"   [{strategy_name}@{ticker}] best={best_params} | "
              f"OOS Sharpe={sharpe:.2f} Calmar={calmar:.2f} Return={ret_pct:.1f}%")

        return {
            "best_params":  best_params,
            "oos_calmar":   round(calmar,  3),
            "oos_sharpe":   round(sharpe,  3),
            "oos_return":   round(ret_pct, 2),
            "oos_win_rate": round(wr,      1),
            "oos_trades":   trades,
            "oos_report":   oos_report,
        }

    except Exception as e:
        print(f"   Param search FAILED [{strategy_name}@{ticker}]: {e}")
        return {}
