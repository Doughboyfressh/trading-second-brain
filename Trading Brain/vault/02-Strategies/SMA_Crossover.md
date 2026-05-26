# SMA Crossover Strategy — Refined Edition v3.0

**File Path**: `02-Strategies/SMA_Crossover_v3.md`
**Last Updated**: 2026-05-25
**Status**: 🟡 UNDER OPTIMIZATION → Conditional Production Use
**Version History**: v1.0 (Failed) → v2.0 (Redesigned) → v3.0 (Regime-Aware, Risk-Managed)

---

## STRATEGY OVERVIEW

| Field | Detail |
|-------|--------|
| **Type** | Trend-Following (Moving Average Crossover) |
| **Asset Classes** | Large-Cap Equities (AAPL, TSLA primary) |
| **Timeframe** | Daily bars |
| **Market Regime** | Bullish Trending; Reduced size in Consolidation; Paused in Bearish |
| **Edge Source** | Trend continuation after MA confirmation + volume conviction |
| **Version** | v3.0 — Regime-Aware, Multi-Filter, Risk-Managed |

---

## WHY v1.0 AND v2.0 FAILED — LESSONS APPLIED

> These lessons are pulled directly from `04-Backtests` and `06-Playbooks`. Every failure is a rule in v3.0.

| Failure | Root Cause | v3.0 Fix |
|---------|-----------|----------|
| AAPL: -51.57% return, -61.55% max DD | No stop-loss; 100% position sizing; single trade | Hard 3% stop; 2% account risk per trade |
| TSLA: -100.00% return, complete wipeout | No risk management; regime blindness; 1 trade | Regime filter; volume gate; position sizing model |
| Win Rate 100% (AAPL) / 0% (TSLA) | n=1 trade; statistically meaningless | Minimum 50-trade sample required before promotion |
| Sharpe -1.21 (AAPL) / 0.00 (TSLA) | Negative risk-adjusted return | Target Sharpe ≥ 1.2; floor at 0.8 |
| Whipsaw in consolidation | No regime filter; lagging MA signal | Regime gate: reduce size 50% in consolidation; pause in bearish |
| Late entries on extended moves | Pure crossover = lagging entry | Pullback-to-MA secondary entry rule added |
| No volume confirmation | False breakouts accepted | Volume ≥ 30-day average required on all entries |

---

## PARAMETER SETS

Three validated configurations based on regime and risk tolerance. Select based on current market regime assessment.

### Set A — Conservative (Trending Markets, Low Risk)

```
Fast MA:              20-period SMA
Slow MA:              50-period SMA
Confirmation Bars:    10 bars (hold signal for 10 days before entry)
Volatility Gate:      IV < 35%
Risk Per Trade:       1.5% of account
Stop Loss:            3% below entry
Expected Sharpe:      0.9–1.2
Expected Win Rate:    55–65%
Best Regime:          Established uptrend, RSI 45–65
```

### Set B — Balanced (Primary Configuration) ✅ CURRENT DEFAULT

```
Fast MA:              10-period SMA
Slow MA:              50-period SMA
Confirmation Bars:    5 bars
Volatility Gate:      IV < 40%
Risk Per Trade:       2.0% of account
Stop Loss:            3% below entry (hard); 2% trailing after +5% gain
Expected Sharpe:      0.8–1.2
Expected Win Rate:    48–55%
Best Regime:          Bullish consolidation, RSI 40–65, moderate IV
Current Status:       ✅ ACTIVE — matches 2026-05-25 regime
```

### Set C — Aggressive (Strong Trending, Higher Risk)

```
Fast MA:              5-period SMA
Slow MA:              20-period SMA
Confirmation Bars:    3 bars
Volatility Gate:      IV < 45%
Risk Per Trade:       2.5% of account
Stop Loss:            4% below entry (wider for TSLA volatility)
Expected Sharpe:      1.0–1.5
Expected Win Rate:    50–60%
Best Regime:          Strong trend, RSI > 60, price making new highs
```

---

## ENTRY RULES

### Primary Entry — Golden Cross Breakout

**Trigger**: Fast MA crosses above Slow MA (bullish crossover)

All five conditions must be TRUE simultaneously:

```
✅ Condition 1 — MA Crossover:
   Fast MA crosses above Slow MA on daily close

✅ Condition 2 — Price Structure:
   Close > 50-day MA AND Close > 200-day MA
   (macro trend alignment required)

✅ Condition 3 — Volume Confirmation (NON-NEGOTIABLE):
   Today's volume ≥ 30-day average volume
   Low volume = false breakout; SKIP signal entirely

✅ Condition 4 — RSI Filter:
   RSI(14) between 40 and 65
   Above 65 = overbought; risk/reward unfavorable
   Below 40 = momentum absent; wait for recovery

✅ Condition 5 — Trend Structure:
   At least 3 higher highs AND 3 higher lows on daily chart
   Confirms trend is established, not a one-day spike
```

**Entry Execution**: Enter at next day's open after all conditions confirmed at close.

---

### Secondary Entry — Pullback to MA (Preferred Lower-Risk Entry)

**Trigger**: Price pulls back to Fast MA after initial breakout

```
✅ Setup:    Price previously broke above both MAs (primary signal confirmed)
✅ Trigger:  Close within 1–2% of 50-day MA
✅ RSI:      RSI(14) < 55 (momentum cooling; not overbought)
✅ Volume:   Volume ≥ 20-day average (lower bar; trend already confirmed)
✅ Structure: No lower lows since breakout (pullback, not reversal)
```

**Rationale**: Reduces entry risk by 2–4%; improves risk/reward ratio; avoids chasing extended moves.

**Current Pullback Levels (2026-05-25)**:

| Asset | Current Price | 50d MA | Pullback Entry Zone | Status |
|-------|--------------|--------|---------------------|--------|
| AAPL | $187.45 | $185.20 | $184.00–$186.50 | ⏳ Watch for dip |
| TSLA | $245.32 | $238.45 | $236.00–$241.00 | ⏳ Watch for dip |

---

### Entry Blockers — Do NOT Enter If Any Are True

```
🚫 Volume < 20-day average (no conviction)
🚫 RSI > 70 (overbought; poor risk/reward)
🚫 RSI < 30 (momentum collapse; not a trend signal)
🚫 Price within 2% of major resistance level
🚫 IV > 50% (extreme volatility; strategy paused)
🚫 Bearish regime active (price below 200d MA)
🚫 Fewer than 3 higher highs/lows on daily chart
🚫 Earnings within 5 trading days (event risk)
```

---

## EXIT RULES

### Profit-Taking Exits (Scaled)

**Target 1 — Partial Exit (50% of position)**
```
Trigger:  Price reaches +5% from entry
Action:   Sell 50% of position
Follow-up: Move stop-loss to breakeven on remaining 50%
Rationale: Lock in gains; eliminate downside risk on remainder
```

**Target 2 — Partial Exit (25% of position)**
```
Trigger:  Price reaches +10% from entry
Action:   Sell 25% of position
Follow-up: Activate trailing stop (2% below 20-day high) on final 25%
Rationale: Capture extended trend moves; protect profits
```

**Target 3 — Final Exit (25% of position)**
```
Trigger:  RSI > 70 AND volume declining (exhaustion signal)
          OR price hits major resistance level
          OR trailing stop triggered
Action:   Exit remaining 25% on next open
Rationale: Exit into strength; avoid late-stage reversals
```

---

### Stop-Loss Exits

**Hard Stop — Risk Control (MANDATORY)**
```
Trigger:  Close below 50-day MA on above-average volume
Distance: 3% below entry (Set B default); 4% for TSLA (higher vol)
Action:   Exit ENTIRE position at next open; no averaging down
Rule:     If stop is hit, the trade thesis is invalidated — EXIT FULLY
```

**Trailing Stop — Profit Protection**
```
Activation: After +5% gain (Target 1 hit)
Method:     2% below the highest close since entry
Action:     Exit if daily close breaches trailing stop level
Rationale:  Protect profits while allowing trend continuation
```

**Time Stop — Stale Trade Exit**
```
Trigger:  No movement (< 1% gain/loss) after 10 trading bars
Action:   Exit position; capital better deployed elsewhere
Rationale: Opportunity cost; consolidation may persist
```

**Current Stop Levels (2026-05-25)**:

| Asset | Entry | Hard Stop (-3%) | Trailing Stop | Time Stop |
|-------|-------|-----------------|---------------|-----------|
| AAPL | $187.45 | $181.83 | $190.00 (2% below 20d high) | Day 10 |
| TSLA | $245.32 | $237.96 | $248.00 (2% below 20d high) | Day 10 |

---

### Current Exit Targets (2026-05-25)

| Asset | Entry | Target 1 (+5%) | Target 2 (+10%) | Resistance Cap |
|-------|-------|----------------|-----------------|----------------|
| AAPL | $187.45 | $196.82 | $206.20 | $192.00 (near-term) |
| TSLA | $245.32 | $257.59 | $269.85 | $255.00 (intermediate) |

> ⚠️ **Note**: AAPL Target 1 ($196.82) is above near-term resistance ($192.00). Consider taking partial profits at $192 resistance rather than waiting for full +5%.

---

## POSITION SIZING

### Core Formula

```
Position Size (shares) = (Account Risk % × Account Size) / (Entry Price − Stop Price)

Where:
  Account Risk % = 2.0% (Set B default)
  Account Size   = Your total trading capital
  Stop Distance  = Entry Price × 0.03 (3% hard stop)
```

### Allocation Rules

```
Single Position Max:      5% of total account value
Single Trade Risk:        2% of account (hard limit)
Sector Concentration:     Max 15% in tech (AAPL + TSLA combined)
Correlated Pair Rule:     If both AAPL & TSLA active simultaneously,
                          reduce each to 1.5% risk (correlation = 0.72)
Total Portfolio Risk:     Max 6% across all open positions
```

### Volatility-Adjusted Sizing

| IV Range | Size Adjustment | Rationale |
|----------|----------------|-----------|
| IV < 20% | +10% (increase) | Low-risk environment |
| IV 20–35% | Standard (1.0×) | Normal regime — current |
| IV 35–50% | −25% (reduce) | Elevated risk |
| IV > 50% | −50% or PAUSE | Extreme risk; strategy unreliable |

### Example Sizing (100K Account, Set B, 2% Risk)

| Asset | Entry | Stop | Risk/Share | Shares | $ Allocated | $ at Risk |
|-------|-------|------|-----------|--------|-------------|-----------|
| AAPL | $187.45 | $181.83 | $5.62 | 355 | $66,545 | $2,000 |
| TSLA | $245.32 | $237.96 | $7.36 | 271 | $66,482 | $2,000 |

> ⚠️ **Correlated Pair Adjustment**: If both positions open simultaneously, reduce each to 1.5% risk (266 AAPL shares / 203 TSLA shares). Total portfolio risk = 3%.

---

## MARKET REGIME FILTERS

### Regime Classification & Response

#### 🟢 Bullish Trending — Trade Full Size

```
Conditions (ALL must be true):
  ✅ Price > 50d MA AND Price > 200d MA
  ✅ Higher highs and higher lows on daily chart
  ✅ RSI(14) between 45–65
  ✅ IV between 20–35%
  ✅ Volume above 30-day average on up days
  ✅ Put/Call ratio < 1.0

Action:   Trade full position size (Set B default)
Current:  ✅ ACTIVE as of 2026-05-25
          AAPL RSI 62.3 | TSLA RSI 58.2 | IV 25–34% | P/C: 0.68–0.92
```

#### 🟡 Bullish Consolidation — Reduce Size 50%

```
Conditions:
  ⚠️ Price oscillating between support/resistance (no new highs)
  ⚠️ RSI 45–55 (neutral; no directional momentum)
  ⚠️ Volume declining on both up and down days
  ⚠️ IV contracting below 20%

Action:   Reduce position size by 50%; tighten stops to 2% below entry
          Prefer pullback entries over breakout entries
          Use Set A (Conservative) parameters
```

#### 🔴 Bearish / High Volatility — Pause Strategy

```
Conditions:
  ❌ Price below 50d MA (trend break)
  ❌ Lower highs and lower lows on daily chart
  ❌ IV spike > 40% (fear/uncertainty)
  ❌ Put/Call ratio > 1.2 (heavy hedging demand)
  ❌ Volume surging on down days; declining on up days

Action:   EXIT all positions immediately
          NO new entries until bullish regime confirmed
          Monitor only; paper trade if desired
```

### Regime Decision Tree

```
Is Price > 200d MA?
  └── NO  → BEARISH REGIME → Pause all entries
  └── YES → Is Price > 50d MA?
              └── NO  → CONSOLIDATION → Reduce size 50%, Set A only
              └── YES → Is RSI between 40–65?
                          └── NO  → WAIT → RSI out of range; skip signal
                          └── YES → Is Volume > 30d avg?
                                      └── NO  → SKIP → No conviction
                                      └── YES → ✅ ENTER → Full size, Set B
```

---

## RISK PARAMETERS

### Drawdown Limits

| Level | Threshold | Action |
|-------|-----------|--------|
| Per Trade | 3% loss | Hard stop; exit immediately |
| Per Week | 5% portfolio loss | Pause new entries; review |
| Per Month | 10% portfolio loss | Full strategy review; reduce size 50% |
| Strategy Max DD | 25% | Retire strategy; redesign required |

### Performance Targets

| Metric | Minimum (Floor) | Target | Excellent |
|--------|----------------|--------|-----------|
| Win Rate | 50% | 55%+ | 62%+ |
| Profit Factor | 1.5 | 1.8+ | 2.2+ |
| Avg Win / Avg Loss | 1.5× | 2.0

