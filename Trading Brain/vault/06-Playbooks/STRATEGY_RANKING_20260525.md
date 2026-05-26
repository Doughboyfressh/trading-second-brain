# Strategy Rankings: Walk-Forward Backtest Analysis
**Generated**: 2026-05-25
**Regime**: Bullish Trending with Consolidation Overlay | Confidence: 74% | IV: 25–34%
**Scope**: All available walk-forward backtest reports in `04-Backtests/`

---

## Data Integrity Notice

> ⚠️ **Limited Walk-Forward Sample**: Only **2 confirmed walk-forward backtest reports** exist in `04-Backtests/` as of this analysis date. Additional entries are drawn from optimization reports and refined strategy documents where walk-forward methodology is explicitly noted. Rankings reflect **actual reported data only** — no figures are extrapolated or fabricated. Strategies without walk-forward results are flagged accordingly.

---

## Ranked Strategy Table

### Ranking Criteria (in order of weight)
1. **Sharpe Ratio** — Primary risk-adjusted return metric
2. **Return / Max Drawdown Ratio** — Capital efficiency under stress
3. **Win Rate** — Signal reliability
4. **Trade Count** — Statistical significance (minimum viable: 30 trades)
5. **Regime Suitability** — Alignment with 2026-05-25 Bullish Trending classification

---

| Rank | Strategy | Asset | Data Source | Sharpe | Return | Max DD | Return/DD Ratio | Win Rate | Trades | Regime Fit | Status |
|------|----------|-------|-------------|--------|--------|--------|-----------------|----------|--------|------------|--------|
| **1** | SMA Crossover (Refined Edition) | AAPL | Strategy Doc (Backtest Summary) | **1.34** | +18.3% CAGR | -8.7% | **2.10** | 59.6% | 47 | ⭐⭐⭐⭐ | ✅ Active |
| **2** | SMA Crossover (Walk-Forward) | TSLA | Walk-Forward Report | **-1.06** | -15.16% | -27.67% | **-0.55** | 41.7% | 72 | ⭐ | 🔴 Retired |
| **3** | SMA Crossover (Walk-Forward) | AAPL | Walk-Forward Report | **-3.38** | -26.25% | -28.79% | **-0.91** | 36.8% | 57 | ⭐ | 🔴 Retired |
| **—** | SMA Crossover (Original) | AAPL | Backtest Report | **0.00** | -51.57% | -61.55% | **-0.84** | 100%* | 1 | ❌ | ❌ Failed |
| **—** | SMA Crossover (Original) | TSLA | Backtest Report | **0.00** | -100.00% | -100.00% | **-1.00** | 0.0% | 1 | ❌ | ❌ Failed |

*100% win rate on n=1 is statistically meaningless — flagged as misleading*

---

## Regime-Ranked Strategy Reference

> The following table incorporates the broader optimization report rankings (not walk-forward confirmed) for regime-alignment context. These are **projected/backtested figures**, not walk-forward validated. Treat as directional guidance only.

| Regime Rank | Strategy | Sharpe (Backtest) | Max DD | Win Rate | Trades/Yr | Regime Fit | Walk-Forward Validated |
|-------------|----------|-------------------|--------|----------|-----------|------------|----------------------|
| 1 | Mean Reversion (RSI 30–70) | 1.68 | -14.2% | 62.3% | ~50 | ⭐⭐⭐⭐⭐ | ❌ Not yet |
| 2 | Bollinger Band Squeeze Break | 1.54 | -16.5% | 60.8% | ~40 | ⭐⭐⭐⭐⭐ | ❌ Not yet |
| 3 | Volume-Weighted MA Crossover | 1.42 | -18.3% | 59.1% | ~37 | ⭐⭐⭐⭐ | ❌ Not yet |
| 4 | Dual MA + RSI Confirmation | 1.38 | -19.1% | 57.9% | ~35 | ⭐⭐⭐⭐ | ❌ Not yet |
| 5 | SMA Crossover (Refined) | 1.34 | -8.7% | 59.6% | 47 | ⭐⭐⭐⭐ | ⚠️ Partial |
| 6 | MACD Histogram Divergence | 1.18 | -21.7% | 56.4% | ~30 | ⭐⭐⭐⭐ | ❌ Not yet |
| 7 | Support/Resistance Bounce | 1.12 | -23.4% | 55.2% | ~25 | ⭐⭐⭐ | ❌ Not yet |
| 8 | Stochastic Oversold Entry | 1.08 | -24.1% | 54.7% | ~20 | ⭐⭐⭐ | ❌ Not yet |
| 9 | ATR-Based Breakout | 1.05 | -25.6% | 53.9% | ~22 | ⭐⭐⭐ | ❌ Not yet |
| 10 | SMA Crossover (Walk-Fwd TSLA) | -1.06 | -27.67% | 41.7% | 72 | ⭐ | ✅ Yes — FAILED |
| 11 | SMA Crossover (Walk-Fwd AAPL) | -3.38 | -28.79% | 36.8% | 57 | ⭐ | ✅ Yes — FAILED |

---

## Dimension-by-Dimension Rankings

### 1. By Sharpe Ratio (Walk-Forward Confirmed Only)

| Rank | Strategy | Asset | Sharpe | Note |
|------|----------|-------|--------|------|
| 1 | SMA Crossover Refined | AAPL | 1.34 | Backtest only; partial WF |
| 2 | SMA Crossover WF | TSLA | -1.06 | Walk-forward confirmed |
| 3 | SMA Crossover WF | AAPL | -3.38 | Walk-forward confirmed |

> **Gap Alert**: No walk-forward confirmed strategy currently holds a positive Sharpe. The Refined Edition's 1.34 Sharpe is from a historical backtest window, not a rolling out-of-sample test. **Priority action: run walk-forward on Tier 1 strategies.**

---

### 2. By Return / Max Drawdown Ratio (Walk-Forward Confirmed Only)

| Rank | Strategy | Asset | Return | Max DD | Ratio | Assessment |
|------|----------|-------|--------|--------|-------|------------|
| 1 | SMA Crossover Refined | AAPL | +18.3% CAGR | -8.7% | **+2.10** | Best capital efficiency |
| 2 | SMA Crossover WF | TSLA | -15.16% | -27.67% | **-0.55** | Negative — unacceptable |
| 3 | SMA Crossover WF | AAPL | -26.25% | -28.79% | **-0.91** | Negative — unacceptable |

---

### 3. By Win Rate (Walk-Forward Confirmed Only)

| Rank | Strategy | Asset | Win Rate | Trades | Statistical Confidence |
|------|----------|-------|----------|--------|----------------------|
| 1 | SMA Crossover Refined | AAPL | 59.6% | 47 | ⚠️ Moderate (borderline sample) |
| 2 | SMA Crossover WF | TSLA | 41.7% | 72 | ✅ Adequate sample — below threshold |
| 3 | SMA Crossover WF | AAPL | 36.8% | 57 | ✅ Adequate sample — below threshold |

---

### 4. By Trade Count (Statistical Significance)

| Rank | Strategy | Asset | Trades | Min Threshold (30) | Valid? |
|------|----------|-------|--------|--------------------|--------|
| 1 | SMA Crossover WF | TSLA | 72 | ✅ | ✅ Yes |
| 2 | SMA Crossover WF | AAPL | 57 | ✅ | ✅ Yes |
| 3 | SMA Crossover Refined | AAPL | 47 | ✅ | ✅ Yes |
| — | SMA Crossover Original | AAPL | 1 | ❌ | ❌ No |
| — | SMA Crossover Original | TSLA | 1 | ❌ | ❌ No |

---

### 5. By Regime Suitability (2026-05-25 Bullish Trending, 74% Confidence)

| Rank | Strategy | Regime Fit Score | Rationale | Deploy? |
|------|----------|-----------------|-----------|---------|
| 1 | Mean Reversion (RSI 30–70) | ⭐⭐⭐⭐⭐ | RSI 58–62 is sweet spot; consolidation ideal | ✅ Yes — await WF validation |
| 2 | Bollinger Band Squeeze Break | ⭐⭐⭐⭐⭐ | IV compression active; breakout imminent | ✅ Yes — await WF validation |
| 3 | Volume-Weighted MA Crossover | ⭐⭐⭐⭐ | Volume +7.4% above avg confirms signals | ✅ Yes — await WF validation |
| 4 | SMA Crossover Refined | ⭐⭐⭐⭐ | Above MAs; pullback entries valid | ⚠️ Reduced size only |
| 5 | SMA Crossover WF (TSLA/AAPL) | ⭐ | Negative Sharpe; regime mismatch confirmed | 🔴 Do not deploy |

---

## Composite Score Summary

> Composite score = weighted average across all 5 dimensions.
> Weights: Sharpe 30% | Return/DD 25% | Win Rate 20% | Trade Count 15% | Regime Fit 10%

| Strategy | Asset | Sharpe Score | Return/DD Score | Win Rate Score | Trade Count Score | Regime Score | **Composite** | Verdict |
|----------|-------|-------------|-----------------|----------------|-------------------|--------------|---------------|---------|
| SMA Crossover Refined | AAPL | 7/10 | 9/10 | 7/10 | 6/10 | 7/10 | **7.35** | ⚠️ Conditional |
| SMA Crossover WF | TSLA | 2/10 | 2/10 | 3/10 | 9/10 | 2/10 | **3.05** | 🔴 Retired |
| SMA Crossover WF | AAPL | 1/10 | 1/10 | 2/10 | 8/10 | 2/10 | **2.45** | 🔴 Retired |

---

## Critical Findings & Action Items

### 🔴 Finding 1: Walk-Forward Gap is the Primary Risk

All walk-forward confirmed strategies have **negative Sharpe ratios**. The only positive-performing strategy (Refined Edition, Sharpe 1.34) is **not walk-forward validated**. This is the single most important gap in the current backtest library.

```
Action: Immediately run walk-forward tests on:
  Priority 1 → Mean Reversion (RSI 30-70)
  Priority 2 → Bollinger Band Squeeze Break
  Priority 3 → SMA Crossover Refined Edition
  Timeline:    Complete before any capital deployment
```

### 🔴 Finding 2: SMA Crossover (Original) is Permanently Retired

Both original SMA Crossover instances produced catastrophic results:
- AAPL: -51.57% return, -61.55% drawdown, n=1 trade
- TSLA: -100% return, -100% drawdown, n=1 trade

```
Action: Archive to 04-Backtests/retired/
  Do not reference in future optimization without full redesign
  Redesign path documented in Optimization Report (3 parameter sets)
```

### ⚠️ Finding 3: Walk-Forward SMA Crossover Shows Regime Mismatch

Even with regime-aware sizing applied, walk-forward results were negative:
- TSLA: Sharpe -1.06, Win Rate 41.7%
- AAPL: Sharpe -3.38, Win Rate 36.8%

```
Action: Do not deploy SMA Crossover in any form until:
  ✅ Minimum 50 trades in backtest
  ✅ Sharpe > 0.6 in walk-forward
  ✅ Win Rate > 50% in walk-forward
  ✅ Max DD < 30% in walk-forward
```

### ✅ Finding 4: Regime-Favored Strategies Lack Walk-Forward Confirmation

Tier 1 strategies (Mean Reversion, BB Squeeze, VWMA Crossover) show strong backtest metrics but have **zero walk-forward reports** in `04-Backtests/`. They cannot be ranked against confirmed strategies.

```
Action: Prioritize walk-forward testing pipeline for Tier 1 strategies
  These are the highest-probability candidates for deployment
  Current regime (74% Bullish Trending) is optimal test environment
```

---

## Deployment Decision Matrix

| Strategy | Walk-Forward Passed? | Regime Aligned? | Deploy? | Size |
|----------|---------------------|-----------------|---------|------|
| Mean Reversion (RSI 30–70) | ❌ Not tested | ✅ Yes | ⏳ Pending WF | — |
| Bollinger Band Squeeze Break | ❌ Not tested | ✅ Yes | ⏳ Pending WF | — |
| Volume-Weighted MA Crossover | ❌ Not tested | ✅ Yes | ⏳ Pending WF | — |
| SMA Crossover Refined | ⚠️ Partial | ✅ Yes | ⚠️ Paper only | 1% max |
| SMA Crossover WF (TSLA) | ✅ Yes — Failed | ❌ No | 🔴 No | 0% |
| SMA Crossover WF (AAPL) | ✅ Yes — Failed | ❌ No | 🔴 No | 0% |
| SMA Crossover Original | ✅ Yes — Failed | ❌ No | 🔴 No | 0% |

---

## Next Steps (Prioritized)

| Priority | Action | Owner | Deadline |
|----------|--------|-------|----------|
| 🔴 P1 | Run walk-forward on Mean Reversion (RSI 30–70) on AAPL + TSLA | Optimizer | Week 1 |
| 🔴 P1 | Run walk-forward on Bollinger Band Squeeze Break | Optimizer | Week 1 |
| 🟡 P2 | Run walk-forward on SMA

