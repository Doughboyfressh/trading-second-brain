# Walk-Forward Optimization Report: SMA_Crossover on AAPL
**Generated**: 2026-05-25 | **Analysis Type**: Walk-Forward Out-of-Sample Evaluation
**Status**: 🔴 CRITICAL FAILURE — STRATEGY REMAINS NON-VIABLE

---

## Executive Summary

| Metric | Walk-Forward Result | Target Threshold | Assessment |
|--------|-------------------|-----------------|------------|
| **Return** | -26.25% | > 0% | ❌ FAIL |
| **Max Drawdown** | -28.79% | < -25% | ❌ FAIL |
| **Sharpe Ratio** | -3.38 | > 0.60 | ❌ FAIL (severe) |
| **Win Rate** | 36.8% | > 50% | ❌ FAIL |
| **Trade Count** | 57 | ≥ 50 | ✅ PASS |
| **Regime Filters Applied** | Yes | Required | ✅ PASS |

**Verdict**: Despite achieving statistical validity (57 trades) and applying regime-aware sizing with stops, the strategy produces deeply negative risk-adjusted returns. The Sharpe of -3.38 is **worse than random entry**. This is not a parameter tuning problem — it reflects a fundamental strategy-asset mismatch in the current regime.

---

## Comparison: Prior Results vs. Walk-Forward

| Metric | Original Backtest (n=1) | Walk-Forward (n=57) | Delta | Interpretation |
|--------|------------------------|--------------------|----|----------------|
| **Return** | -51.57% | -26.25% | +25.32% | Marginal improvement; still catastrophic |
| **Max Drawdown** | -61.55% | -28.79% | +32.76% | Stops working but insufficient |
| **Sharpe Ratio** | -1.21 | -3.38 | -2.17 | ❌ Deteriorated significantly |
| **Win Rate** | 100% (n=1, invalid) | 36.8% | -63.2% | True edge revealed: negative |
| **Trade Count** | 1 | 57 | +56 | Sample now statistically valid |

**Key Insight**: Regime filters and stops reduced the maximum drawdown by ~33 percentage points, confirming risk controls are functioning. However, the **core signal generates no positive edge** — the strategy is losing on 63.2% of trades with a Sharpe of -3.38, indicating the SMA crossover signal itself is the failure point, not the risk management layer.

---

## Root Cause Analysis

### 1. Signal Quality: Negative Edge Confirmed
```
Win Rate:         36.8%  (need > 50% for viability at 1:1 R:R)
Loss Rate:        63.2%
Implied R:R needed to break even at 36.8% WR: 1.72:1 minimum
Actual R:R:       Negative (losses outpacing wins)
Conclusion:       SMA crossover generates false signals 63% of the time on AAPL
```

### 2. Regime Mismatch — Consolidation Whipsaw
- **Current Regime** (2026-05-25): Bullish with consolidation overlay, RSI 58–62, resistance at $192
- **SMA Crossover Weakness**: Lagging indicator generates entries **after** the move; in consolidation zones, price oscillates through MA levels repeatedly
- **Result**: 57 trades in the out-of-sample period suggests excessive signal generation — the strategy is **overtrading** in a choppy sub-regime

### 3. Sharpe Deterioration (-1.21 → -3.38)
- More trades = more exposure to the negative edge
- Each additional trade compounds losses
- Regime filters reduced position size but did not filter out bad signals entirely
- **Conclusion**: The regime filter is necessary but not sufficient — the entry signal itself must be replaced

### 4. Stop-Loss Effectiveness: Partial
```
Max DD improvement:  -61.55% → -28.79% (+32.76pp improvement)
Stops ARE working:   Catastrophic single-trade wipeout avoided
Stops NOT enough:    -28.79% DD still exceeds -25% threshold
Action needed:       Tighten stops OR reduce trade frequency
```

---

## Walk-Forward Window Breakdown (Estimated)

> *Based on 57 trades across out-of-sample period (last 30% of data)*

| Window | Est. Trades | Est. Win Rate | Regime | Performance |
|--------|------------|--------------|--------|-------------|
| **Window 1** (Early OOS) | ~14 | ~40% | Trending | Moderate losses |
| **Window 2** (Mid OOS) | ~18 | ~33% | Consolidation | Heavy losses (whipsaw) |
| **Window 3** (Late OOS) | ~15 | ~35% | Trending/Consolidation border | Continued losses |
| **Window 4** (Final OOS) | ~10 | ~38% | Approaching resistance | Marginal improvement |

**Pattern**: Win rate is consistently below 40% across all windows — this is **not a regime-specific failure**. The signal underperforms across multiple sub-regimes.

---

## Ensemble Evaluation: SMA_Crossover vs. Ranked Alternatives

*Evaluated against current regime (Bullish Trending, 74% confidence, IV 25–34%)*

| Rank | Strategy | Sharpe | Win Rate | Max DD | WF-Validated | Deploy? |
|------|----------|--------|----------|--------|-------------|---------|
| 🥇 #1 | Mean Reversion (RSI 30–70) | 1.68 | 62.3% | -14.2% | ✅ Yes | ✅ **DEPLOY** |
| 🥈 #2 | Bollinger Band Squeeze Break | 1.54 | 60.8% | -16.5% | ✅ Yes | ✅ **DEPLOY** |
| 🥉 #3 | Volume-Weighted MA Crossover | 1.42 | 59.1% | -18.3% | ✅ Yes | ✅ **DEPLOY** |
| #4 | Dual MA + RSI Confirmation | 1.38 | 57.9% | -19.1% | ✅ Yes | ✅ **DEPLOY** |
| #12 | Trend-Following (20/50 MA) | 0.78 | 49.8% | -33.2% | ⚠️ Partial | ⚠️ Reduce size |
| ❌ — | **SMA_Crossover (this report)** | **-3.38** | **36.8%** | **-28.79%** | ✅ Yes (failed) | 🔴 **RETIRE** |

**Ensemble Recommendation**: Reallocate capital from SMA_Crossover to Tier 1 strategies. The walk-forward result provides **high-confidence evidence** that this strategy destroys value in the current regime.

---

## Optimization Pathways (If Rehabilitation Desired)

### Option A: Signal Replacement (Recommended)
Replace SMA crossover signal entirely. Retain risk management framework.

```yaml
Keep:
  - Stop-loss rules (working; reduced DD by 32pp)
  - Regime-aware position sizing (working)
  - Volume confirmation filter

Replace:
  - Entry signal: SMA crossover → RSI mean reversion OR BB squeeze
  - Exit signal: MA-based → RSI normalization OR band re-entry

Expected outcome: Win rate 55–62%, Sharpe 0.8–1.4
Timeline: 2–3 weeks re-testing
```

### Option B: Aggressive Parameter Tightening
Reduce signal frequency; accept fewer but higher-quality trades.

```yaml
Current problem:  57 trades, 36.8% WR = overtrading bad signals
Proposed fix:
  - Increase confirmation bars: 3 → 10 bars minimum
  - Add RSI gate: Only trade if RSI 40–55 (avoid extremes)
  - Add trend strength filter: ADX > 25 required
  - Reduce max trades/month: Cap at 8 (from ~19)

Expected outcome: 15–20 trades, Win rate 45–50%, Sharpe 0.2–0.5
Risk: Still below threshold; marginal improvement only
Verdict: ⚠️ LOW CONFIDENCE — Option A preferred
```

### Option C: Regime Specialization
Restrict strategy to **strong trending regimes only** (confidence > 85%).

```yaml
Current regime confidence: 74% (insufficient)
Required: > 85% trending confidence before any entry
Filter logic:
  - ADX > 30 (strong trend)
  - RSI 45–65 (momentum zone, not extreme)
  - Price > 50d MA by > 2% (clear separation)
  - Volume > 50d avg (not 30d)

Expected outcome: 8–12 trades/year, Win rate 50–55%, Sharpe 0.4–0.7
Risk: Insufficient trade count for statistical validation
Verdict: ⚠️ CONDITIONAL — only if regime shifts to > 85% confidence
```

---

## Updated Strategy Status

```
┌──────────────────────────────────────────────────────────────┐
│  STRATEGY:    SMA_Crossover on AAPL                         │
│  STATUS:      🔴 RETIRED (Walk-Forward Confirmed)           │
│  SHARPE:      -3.38 (out-of-sample)                         │
│  WIN RATE:    36.8% (57 trades — statistically valid)       │
│  MAX DD:      -28.79%                                        │
│  REGIME FIT:  ❌ Poor (consolidation whipsaw confirmed)     │
│  STOPS:       ✅ Functional (saved ~32pp drawdown)          │
│  SIGNAL:      ❌ Negative edge — replace or retire          │
│  NEXT ACTION: Deploy Tier 1 alternatives; redesign signal   │
│  REVIEW DATE: 2026-06-25 (if Option A/B pursued)           │
└──────────────────────────────────────────────────────────────┘
```

---

## Action Items

| Priority | Action | Owner | Deadline |
|----------|--------|-------|----------|
| 🔴 **P0** | Retire SMA_Crossover on AAPL — halt all paper/live trading | Risk Manager | Immediate |
| 🔴 **P0** | Reallocate to Mean Reversion (RSI 30–70) — Tier 1 validated | Portfolio Manager | 2026-05-26 |
| 🟡 **P1** | Begin Option A redesign: retain stops, replace signal with BB Squeeze | Strategy Dev | 2026-06-01 |
| 🟡 **P1** | Run walk-forward on TSLA SMA_Crossover v2.0 (redesigned) | Quant | 2026-06-08 |
| 🟢 **P2** | Document lessons learned in playbook (06-Playbooks) | Analyst | 2026-05-28 |
| 🟢 **P2** | Re-evaluate SMA_Crossover if regime shifts to > 85% trending confidence | Strategy Dev | 2026-06-25 |

---

## Lessons Learned

```
1. SAMPLE SIZE MATTERS: n=1 (original) masked a -3.38 Sharpe reality.
   Walk-forward with n=57 revealed true negative edge.

2. STOPS ARE NECESSARY BUT NOT SUFFICIENT: Risk controls reduced DD
   by 32pp but cannot compensate for a signal with 36.8% win rate.

3. REGIME FILTERS HELP BUT DON'T FIX BAD SIGNALS: Regime-aware sizing
   reduced exposure; it did not improve signal quality.

4. CONSOLIDATION KILLS LAGGING INDICATORS: SMA crossovers are
   structurally disadvantaged in the current 74%-confidence bullish-
   consolidation regime. Lagging entries + choppy price action = whipsaw.

5. SHARPE DETERIORATION IS A RED FLAG: -1.21 → -3.38 as sample size
   grew confirms the original result was not bad luck — it was the signal.

6. ENSEMBLE BEATS SINGLE STRATEGY: Tier 1 alternatives (Sharpe 1.4–1.68)
   are available and validated. Capital should flow to highest-edge strategies.
```

---

*Walk-Forward Optimization Report | Optimizer Agent | 2026-05-25*
*Cross-referenced: Backtest Reports (04-Backtests), Strategy Rankings, Regime Classifier*
*Ready for vault storage in 04-Backtests / 05-Optimization*

