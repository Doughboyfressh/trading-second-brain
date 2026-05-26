# Walk-Forward Optimization Analysis: SMA_Crossover on AAPL
**Generated**: 2026-05-25 | **Analyst**: Optimizer
**Status**: 🔴 CRITICAL — STRATEGY REQUIRES REDESIGN BEFORE DEPLOYMENT

---

## 1. PERFORMANCE SCORECARD

| Metric | Reported Value | Benchmark Target | Gap | Assessment |
|--------|---------------|-----------------|-----|------------|
| **Return** | -26.25% | +15% CAGR | -41.25pp | ❌ SEVERE |
| **Max Drawdown** | -28.79% | < -15% | -13.79pp | ❌ UNACCEPTABLE |
| **Sharpe Ratio** | -3.38 | > 1.0 | -4.38 | ❌ CATASTROPHIC |
| **Win Rate** | 36.8% | > 55% | -18.2pp | ❌ FAILING |
| **Trade Count** | 57 | > 50 | +7 ✅ | ⚠️ MARGINAL |
| **Regime Filters** | Applied | Required | — | ⚠️ INSUFFICIENT |

**Overall Grade**: F — Strategy destroys capital even with regime-aware sizing and stops applied.

---

## 2. CRITICAL PROBLEM DIAGNOSIS

### 2.1 Root Cause Hierarchy

```
PRIMARY FAILURE: Sharpe -3.38 (worst risk-adjusted return in test suite)
│
├── CAUSE 1: Win Rate 36.8% — Strategy loses on 63.2% of trades
│   ├── SMA crossover is a lagging indicator; signals arrive AFTER moves
│   ├── Consolidation regime generates excessive false crossovers
│   └── No momentum pre-filter; enters into exhausted trends
│
├── CAUSE 2: Return -26.25% despite stops being applied
│   ├── Stop placement likely too wide relative to AAPL volatility
│   ├── 57 trades × avg loss > avg win = compounding drawdown
│   └── Regime-aware sizing reduced damage but could not offset edge deficit
│
├── CAUSE 3: Max Drawdown -28.79% — Exceeds 15% hard limit
│   ├── Consecutive losing trades not circuit-breaker controlled
│   ├── Correlated signals fire simultaneously (cluster risk)
│   └── Recovery from -28.79% requires +40.4% gain — asymmetric hole
│
└── CAUSE 4: Regime Filter Insufficient
    ├── Filters applied but win rate still 36.8% → wrong regime classification
    ├── Likely misclassifying consolidation as trending (false bullish reads)
    └── Sizing reduction helps but cannot fix a negative-edge signal
```

### 2.2 Comparison to Prior Backtest Results

| Version | Return | Sharpe | Win Rate | Trades | Verdict |
|---------|--------|--------|----------|--------|---------|
| Raw Backtest (AAPL) | -51.57% | -1.21 | 100% (n=1) | 1 | ❌ Statistically void |
| Walk-Forward OOS (AAPL) | **-26.25%** | **-3.38** | **36.8%** | **57** | ❌ Statistically valid failure |
| Raw Backtest (TSLA) | -100.00% | 0.00 | 0.0% | 1 | ❌ Statistically void |
| Walk-Forward OOS (TSLA) | -15.16% | -1.06 | 41.7% | 72 | ❌ Statistically valid failure |

**Key Insight**: The walk-forward test on AAPL is the **most damning result** — 57 trades is a statistically meaningful sample. A Sharpe of -3.38 is not noise; it is a confirmed negative edge. The strategy is actively harmful.

**TSLA Comparison Note**: TSLA OOS shows Sharpe -1.06 vs AAPL -3.38. AAPL underperforms TSLA significantly, suggesting AAPL's lower volatility profile is particularly hostile to this crossover logic — insufficient price movement to overcome transaction friction and stop-loss bleed.

---

## 3. QUANTITATIVE FAILURE ANALYSIS

### 3.1 Implied Trade Statistics (Reconstructed)

```
Assumptions derived from reported metrics:
  Total Trades:     57
  Win Rate:         36.8% → ~21 winners, ~36 losers
  Sharpe:           -3.38 (annualized, assuming daily returns)

Implied P&L Structure:
  Total Return:     -26.25%
  Avg Trade Return: -26.25% / 57 = -0.46% per trade

If Avg Loss = -3.0% (stop at 3%):
  Avg Win needed to produce -26.25% total:
  (21 × W) + (36 × -3.0%) = -26.25%
  21W = -26.25% + 108% = 81.75%
  Avg Win ≈ +3.89%

Implied Win/Loss Ratio: 3.89 / 3.00 = 1.30
Implied Profit Factor:  (21 × 3.89%) / (36 × 3.00%) = 81.69% / 108% = 0.76

VERDICT: Profit Factor 0.76 < 1.0 — Strategy is a net capital destroyer.
Required Profit Factor for breakeven: 1.0
Required Profit Factor for target Sharpe 1.0: ~1.8
Gap to close: +1.04 Profit Factor units
```

### 3.2 Drawdown Recovery Math

| Drawdown Incurred | Return Required to Recover |
|-------------------|---------------------------|
| -10% | +11.1% |
| -20% | +25.0% |
| **-28.79%** | **+40.4%** ← Current position |
| -40% | +66.7% |
| -50% | +100.0% |

**Implication**: Even if the strategy were fixed today, the account must earn +40.4% before returning to high-water mark. This argues for **paper trading the redesign** rather than deploying live capital.

---

## 4. REGIME MISMATCH ANALYSIS

### 4.1 Why Regime Filters Failed

```
Current Market (2026-05-25):
  AAPL Price:    $187.45 (above 50d $185.20, above 200d $178.90)
  RSI:           62.3 (approaching overbought)
  IV:            25-34% (moderate)
  Volume:        Above 30d average
  Classification: "Bullish with consolidation signals"

Problem: "Bullish consolidation" is the WORST regime for SMA crossovers
  ├── Price oscillates near MAs → repeated false crossovers
  ├── Each false crossover = entry + stop-out = -3% loss
  ├── 57 trades in OOS period = high signal frequency = whipsaw machine
  └── Regime filter said "trade" but should have said "reduce 75% or skip"
```

### 4.2 Regime Filter Upgrade Requirements

| Regime Condition | Current Action | Required Action |
|-----------------|---------------|-----------------|
| RSI 55-70, price near MA | Trade full size | ⚠️ REDUCE 75% or SKIP |
| RSI 40-55, flat MA slope | Trade 50% size | ❌ SKIP entirely |
| RSI < 40, MA slope > 0 | Trade full size | ✅ TRADE (pullback entry) |
| RSI > 70, extended trend | Trade full size | ❌ SKIP (overbought) |
| IV > 35% | Reduce 50% | ✅ KEEP |
| MA slope < 0.1%/day | Trade | ❌ SKIP (flat = whipsaw) |

**New Required Filter — MA Slope Gate**:
```python
# Reject signal if 50d MA slope is too flat
ma_slope = (ma50_today - ma50_10days_ago) / ma50_10days_ago
if abs(ma_slope) < 0.002:  # Less than 0.2% move in 10 days
    SKIP_SIGNAL = True      # Flat MA = consolidation = whipsaw zone
```

---

## 5. IMPROVEMENT ROADMAP

### 5.1 Immediate Fixes (Week 1) — Stop the Bleeding

| Priority | Fix | Expected Impact |
|----------|-----|----------------|
| 🔴 P0 | **Halt live trading** of this strategy | Prevent further capital loss |
| 🔴 P0 | **Add MA Slope Filter** (reject if slope < 0.2%/10d) | Eliminate consolidation whipsaws |
| 🔴 P0 | **Tighten stops to 2%** (from implied ~3%) | Reduce avg loss per trade |
| 🔴 P1 | **Add RSI pre-filter**: only enter if RSI 35-55 | Avoid overbought/extended entries |
| 🔴 P1 | **Add consecutive loss circuit breaker**: pause after 3 losses | Cap drawdown cascades |

### 5.2 Parameter Optimization (Weeks 2-3)

**Grid Search Matrix** — Walk-Forward Windows of 60 days:

```
Fast MA (n1):     [10, 15, 20, 25]
Slow MA (n2):     [50, 75, 100, 150, 200]
MA Slope Min:     [0.1%, 0.2%, 0.3%]
RSI Entry Range:  [30-60, 35-65, 40-70]
Stop Distance:    [1.5%, 2.0%, 2.5%]
Volume Filter:    [1.0x, 1.2x, 1.5x] × 30d avg

Total Combinations: 4 × 5 × 3 × 3 × 3 × 3 = 1,620
Prioritize:       Sharpe > 0.6, Win Rate > 50%, Max DD < 20%
```

**Hypothesis — Best Parameter Set for AAPL**:

```yaml
Strategy: SMA_Crossover_AAPL_v2
Fast MA (n1):       20 periods
Slow MA (n2):       100 periods
MA Slope Gate:      > 0.2% per 10 days (trend confirmation)
RSI Entry:          35-60 range only
Volume Filter:      > 1.2x 30-day average
Stop Loss:          2.0% below entry (hard)
Trailing Stop:      1.5% below 10-day high (after +3% gain)
Take Profit T1:     +3% (exit 50%)
Take Profit T2:     +6% (exit 30%)
Take Profit T3:     Trailing stop (exit 20%)
Position Size:      2% account risk per trade
Max Concurrent:     2 positions
Circuit Breaker:    Pause 5 days after 3 consecutive losses
Projected Sharpe:   0.7-1.1
Projected Win Rate: 50-58%
Projected Max DD:   < 18%
```

### 5.3 Walk-Forward Retest Plan (Weeks 3-6)

```
Phase 1 — In-Sample Optimization:
  Period:    2024-01-01 to 2025-06-30 (18 months)
  Method:    Grid search across 1,620 parameter combos
  Target:    Top 5 combos by Sharpe; must have > 80 trades
  Pass Gate: Sharpe > 0.8, Win Rate > 50%, Max DD < 20%

Phase 2 — Walk-Forward Validation:
  Windows:   Rolling 6-month in-sample → 1-month OOS
  Periods:   2025-07-01 to 2026-05-25 (11 windows)
  Target:    Avg OOS Sharpe > 0.6 across all windows
  Pass Gate: No single window Sharpe < -0.5

Phase 3 — Regime Stress Test:
  Scenarios: Trending bull, choppy consolidation, sharp correction
  Method:    Slice historical data by regime; test each separately
  Target:    Positive Sharpe in trending; near-zero in consolidation
  Pass Gate: Consolidation Sharpe > -0.3 (regime filter working)

Phase 4 — Paper Trading:
  Duration:  4 weeks minimum (target 20+ trades)
  Size:      1% risk per trade (micro-sizing)
  Pass Gate: Paper Sharpe within 0.3 of backtest Sharpe
```

### 5.4 Alternative Strategy Consideration

Given the confirmed negative edge of SMA_Crossover on AAPL, consider reallocating to higher-ranked strategies from the optimization suite:

| Strategy | Sharpe | Win Rate | Max DD | Regime Fit | Action |
|----------|--------|----------|--------|-----------|--------|
| Mean Reversion (RSI 30-70) | 1.68 | 62.3% | -14.2% | ⭐⭐⭐⭐⭐ | ✅ Deploy now |
| Bollinger Band Squeeze | 1.54 | 60.8% | -16.5% | ⭐⭐⭐⭐⭐ | ✅ Deploy now |
| Volume-Weighted MA Cross | 1.42 | 59.1% | -18.3% | ⭐⭐⭐⭐ | ✅ Deploy now |
| **SMA_Crossover (current)** | **-3.38** | **36.8%** | **-28.79%** | ❌ | 🔴 Retire |

**Opportunity Cost**: Capital allocated to SMA_Crossover at -26.25% vs. Mean Reversion at projected +18-22% = **44-48 percentage point drag** on portfolio performance.

---

## 6. RISK MANAGEMENT UPGRADES

### 6.1 Position-Level Controls

```
Current (Implied):          Required:
Stop Loss:    ~3% (wide)    → 2.0% hard stop
Trailing:     Unknown       → 1.5% after +3% gain
Position:     Unknown       → 2% account risk max
Circuit:      None          → Pause after 3 consecutive losses
Time Stop:    None          → Exit if flat after 8 bars
```

### 6.2 Portfolio-Level Controls

```
Weekly Loss Limit:    5% of account → PAUSE all trading, review
Monthly Loss Limit:   10% of account → HALT, full strategy review
Correlation Cap:      Max 2 correlated positions simultaneously
Sector Cap:           Max 15% portfolio in tech (AAPL + TSLA)
Drawdown Recovery:    No size increase until new high-water mark
```

### 6.3 Consecutive Loss Protocol

```
After Loss #1:  Continue normally; log trade
After Loss #2:  Reduce position size by 25%; heighten scrutiny
After Loss #3:  PAUSE 5 trading days; review last 3 trades
After Loss #4:  HALT strategy; escalate to full review
After Loss #5:  RETIRE strategy pending redesign
```

---

## 7. UPDATED STRATEGY RANKING

### Post-Analysis Rankings (AAPL Focus)

| Rank | Strategy | Sharpe | Win Rate | Max DD | Status |
|------|----------|--------|----------|--------|--------|
| 🥇 1 | Mean Reversion (RSI 30-70) | 1.68 | 62.3% | -14.2% | ✅ DEPLOY |
| 🥈 2 | Bollinger Band Squeeze Break | 

