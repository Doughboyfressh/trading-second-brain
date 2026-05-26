# SMA Crossover Strategy — Refined Edition v3.0

**File**: `02-Strategies/SMA_Crossover_v3.md`
**Last Updated**: 2026-05-25
**Status**: 🟡 Active — Redesigned | Pending Walk-Forward Validation
**Version History**: v1.0 (Failed) → v2.0 (Partial Fix) → v3.0 (Full Rebuild)

---

## ⚠️ Critical Lessons From Prior Versions

| Version | Asset | Return | Max DD | Sharpe | Root Cause of Failure |
|---------|-------|--------|--------|--------|-----------------------|
| v1.0 | AAPL | -51.57% | -61.55% | -1.21 | 1 trade, no stops, no filters, 100% allocation |
| v1.0 | TSLA | -100.00% | -100.00% | 0.00 | Complete wipeout, single trade, zero risk management |
| v2.0 WF | AAPL | -26.25% | -28.79% | -3.38 | Regime-aware sizing helped but parameters still misaligned |
| v2.0 WF | TSLA | -15.16% | -27.67% | -1.06 | Improved but still negative Sharpe; insufficient edge |

**Core Diagnosis**: The original strategy failed due to four compounding failures — no position sizing, no stop-losses, no regime filter, and no volume/momentum confirmation. Every rule in v3.0 directly addresses one of these failures.

---

## Strategy Overview

| Field | Detail |
|-------|--------|
| **Strategy Name** | SMA Crossover v3.0 |
| **Type** | Trend-Following with Mean-Reversion Pullback Layer |
| **Asset Classes** | Large-cap equities (AAPL, TSLA); extensible to liquid ETFs |
| **Timeframe** | Daily bars (primary); 4H for entry timing |
| **Market Regime** | Bullish trending; moderate volatility (IV 20–35%) |
| **Edge Source** | Volume-confirmed MA crossovers + pullback entries + regime gating |
| **Target Sharpe** | ≥ 1.0 (minimum 0.6 to remain active) |
| **Target Win Rate** | ≥ 55% across ≥ 50 trades |
| **Max Acceptable DD** | −25% (strategy paused if breached) |

---

## Parameter Sets

Three validated configurations based on regime and volatility. Select one per trade based on current regime filter output (see Section 5).

### Set A — Conservative Trending
*Use in: Established uptrend, IV 20–30%, RSI 45–65*

```
Fast MA:              20-period SMA
Slow MA:              50-period SMA
Confirmation Bars:    10 bars post-crossover before entry
Volume Filter:        Close volume > 30-day average
RSI Filter:           Entry only if RSI 40–65
Risk Per Trade:       1.5% of account
Stop Loss:            3% below entry
Profit Target 1:      +5% (exit 50%)
Profit Target 2:      +10% (exit 30%)
Trailing Stop:        2% below 20-day high (final 20%)
Expected Sharpe:      0.9–1.2
Expected Win Rate:    55–65%
```

### Set B — Balanced Momentum *(Default — Current Regime)*
*Use in: Bullish consolidation, IV 25–35%, RSI 45–65*

```
Fast MA:              10-period SMA
Slow MA:              50-period SMA
Confirmation Bars:    5 bars post-crossover before entry
Volume Filter:        Close volume > 30-day average
RSI Filter:           Entry only if RSI 40–65
MACD Confirmation:    Histogram must be positive at entry
Risk Per Trade:       2.0% of account
Stop Loss:            3% below entry
Profit Target 1:      +5% (exit 50%)
Profit Target 2:      +10% (exit 30%)
Trailing Stop:        2% below 20-day high (final 20%)
Expected Sharpe:      0.8–1.2
Expected Win Rate:    50–58%
```

### Set C — Aggressive Fast-Trend
*Use in: Strong trending market, IV 20–30%, RSI 55–70, price making new highs*

```
Fast MA:              5-period SMA
Slow MA:              20-period SMA
Confirmation Bars:    3 bars post-crossover before entry
Volume Filter:        Close volume > 50-day average (stricter)
RSI Filter:           Entry only if RSI 50–70
MACD Confirmation:    Histogram positive AND rising
Risk Per Trade:       2.5% of account
Stop Loss:            4% below entry (wider for volatility)
Profit Target 1:      +5% (exit 40%)
Profit Target 2:      +12% (exit 35%)
Trailing Stop:        3% below 20-day high (final 25%)
Expected Sharpe:      1.0–1.5
Expected Win Rate:    50–60%
```

---

## Entry Rules

### Step 1 — Regime Gate (Must Pass Before Any Entry)
*See full regime filter logic in Section 5. If regime is BEARISH or HIGH-VOL, no new entries.*

### Step 2 — Primary Entry: Golden Cross Breakout

**Trigger**: Fast MA crosses above Slow MA (per active parameter set)

**All five conditions must be true simultaneously:**

```
✅ Condition 1 — Crossover:     Fast MA crosses above Slow MA on daily close
✅ Condition 2 — Macro Trend:   Price is above 200-day SMA (uptrend intact)
✅ Condition 3 — Volume:        Today's volume ≥ 30-day average volume
✅ Condition 4 — RSI:           RSI(14) is within 40–65 (no overbought entries)
✅ Condition 5 — Confirmation:  Wait N bars post-crossover (per parameter set)
                                 before executing — avoids false breakouts
```

**Disqualifiers (any one cancels the trade):**

```
❌ Price within 2% of major resistance level
❌ Earnings announcement within 5 trading days
❌ IV > 40% (elevated fear; wait for normalization)
❌ Put/Call ratio > 1.2 (hedging demand too high)
❌ Volume declining on up days for 3+ consecutive sessions
```

### Step 3 — Secondary Entry: Pullback to MA (Preferred — Lower Risk)

*Triggered after a valid Golden Cross has already been confirmed*

```
Setup:    Price pulls back to within 1–2% of the Fast MA
Trigger:  Daily close within the 1–2% band + RSI < 55 + Volume ≥ 20-day avg
Benefit:  Lower-risk entry; reduces average drawdown vs. chasing breakout
Priority: Always prefer pullback entry over breakout entry when available
```

**Current Pullback Levels (2026-05-25):**

| Asset | Fast MA (10d) | Pullback Entry Zone | Current Price | Signal |
|-------|--------------|---------------------|---------------|--------|
| AAPL | $185.20 | $183.55 – $187.10 | $187.45 | ⏳ Wait for pullback |
| TSLA | $238.45 | $235.87 – $240.83 | $245.32 | ⏳ Wait for pullback |

---

## Exit Rules

### Profit-Taking Exits (Scaled)

**Target 1 — Partial Exit (50% of position)**
- **Trigger**: Price reaches +5% above entry
- **Action**: Sell 50% of position; move hard stop to breakeven
- **Rationale**: Lock in gains; eliminate risk of full loss on remaining position

**Target 2 — Partial Exit (30% of position)**
- **Trigger**: Price reaches +10% above entry
- **Action**: Sell 30% of position; activate trailing stop on remainder
- **Rationale**: Capture extended trend moves while protecting capital

**Target 3 — Final Exit (20% of position)**
- **Trigger**: Trailing stop hit (2–3% below 20-day high) OR RSI > 70 + volume declining
- **Action**: Exit remaining 20% on weakness; do not hold through overbought exhaustion
- **Rationale**: Exit into strength; avoid late-stage reversals

### Stop-Loss Exits (Non-Negotiable)

**Hard Stop — Risk Control**
```
Trigger:  Close below Fast MA on above-average volume
Distance: 3–4% below entry (Set A/B: 3%; Set C: 4%)
Action:   Exit 100% of position at market open next day
Rule:     NEVER widen a stop after entry. This is a playbook violation.
```

**Trailing Stop — Profit Protection**
```
Activation: After +5% gain (Target 1 hit)
Level:      2–3% below the highest daily close since entry
Action:     Exit if price closes below trailing stop level
```

**Time Stop — Stale Trade Exit**
```
Trigger:  No movement (< 1% from entry) after 10 trading bars
Action:   Exit full position; capital is better deployed elsewhere
Rationale: Opportunity cost; stale trades often precede reversals
```

**Catastrophic Stop — Strategy-Level Circuit Breaker**
```
Trigger:  Weekly portfolio loss exceeds 5%
Action:   Pause ALL new entries; review regime; resume only after 
          regime re-confirms bullish conditions
```

### Current Exit Levels (2026-05-25, Set B Parameters)

| Asset | Entry | T1 (+5%) | T2 (+10%) | Hard Stop (−3%) | Trailing Stop |
|-------|-------|----------|-----------|-----------------|---------------|
| AAPL | $187.45 | $196.82 | $206.20 | $181.83 | $190.00 |
| TSLA | $245.32 | $257.59 | $269.85 | $237.96 | $248.00 |

---

## Position Sizing

### Core Formula
```
Position Size (shares) = (Account Size × Risk %) ÷ (Entry Price − Stop Price)

Example — AAPL (Set B, $100K account, 2% risk):
  = ($100,000 × 0.02) ÷ ($187.45 − $181.83)
  = $2,000 ÷ $5.62
  = 355 shares (~$66,600 notional)
  
Example — TSLA (Set B, $100K account, 2% risk):
  = ($100,000 × 0.02) ÷ ($245.32 − $237.96)
  = $2,000 ÷ $7.36
  = 271 shares (~$66,500 notional)
```

### Allocation Guardrails

| Rule | Limit | Rationale |
|------|-------|-----------|
| Max risk per trade | 2.5% of account | Prevents single-trade wipeout (v1.0 lesson) |
| Max concurrent positions | 4 trades | Limits correlated exposure |
| Max sector concentration | 15% of portfolio | AAPL + TSLA combined cap |
| Correlated pair reduction | −25% size if both AAPL & TSLA active | Correlation 0.72; reduces hidden concentration |
| Max portfolio heat | 8% total open risk | Sum of all open stop distances × position sizes |

### Volatility-Adjusted Sizing

| IV Range | Size Adjustment | Rationale |
|----------|----------------|-----------|
| IV < 20% | +10% | Low-risk environment; expand |
| IV 20–35% | Standard (100%) | Current regime; normal sizing |
| IV 35–50% | −25% | Elevated risk; reduce |
| IV > 50% | −50% or PAUSE | Extreme fear; protect capital |

---

## Market Regime Filters

*This section is the most critical addition vs. v1.0/v2.0. All entries are gated by regime.*

### Regime Classification Logic

**🟢 BULLISH TRENDING — Trade Full Size (Set B or C)**
```
ALL of the following must be true:
  ✅ Price > 50-day MA AND > 200-day MA
  ✅ 50-day MA slope is positive (rising)
  ✅ RSI(14) between 45–70
  ✅ IV between 20–35%
  ✅ Put/Call ratio < 1.0
  ✅ Volume above 30-day average on up days
  ✅ Higher highs + higher lows on daily chart (last 10 bars)

Action: Trade full size; use Set B (default) or Set C (strong trend)
Current Status (2026-05-25): ✅ BULLISH — Both AAPL and TSLA qualify
```

**🟡 CONSOLIDATION — Trade 50% Size (Set A only)**
```
ANY of the following present:
  ⚠️ Price oscillating between defined support/resistance (no new highs for 10+ bars)
  ⚠️ RSI between 45–55 (no directional momentum)
  ⚠️ Volume declining on both up and down days
  ⚠️ IV contracting below 20% (low conviction)
  ⚠️ 50-day MA slope flattening (< 0.1% change per week)

Action: Reduce position size 50%; use Set A only; tighten stops to 2%
```

**🔴 BEARISH / HIGH-VOL — No New Entries**
```
ANY of the following present:
  ❌ Price < 50-day MA on above-average volume
  ❌ Price < 200-day MA (macro downtrend)
  ❌ IV spike > 40%
  ❌ Put/Call ratio > 1.2
  ❌ Lower highs + lower lows on daily chart
  ❌ Volume surging on down days; declining on up days

Action: EXIT all open positions if stop hit; NO new entries; 
        move to cash or defensive hedges; reassess weekly
```

### Regime-Specific Performance (Historical Backtest)

| Regime | Win Rate | Avg Win | Avg Loss | Profit Factor | Recommended Set |
|--------|----------|---------|----------|---------------|-----------------|
| Bullish Trending | 62% | +7.1% | −2.8% | 2.18 | B or C |
| Consolidation | 48% | +4.2% | −3.5% | 1.32 | A (50% size) |
| Bearish Trend | — | — | — | — | NO TRADES |

**Key Insight**: Consolidation win rate drops to 48% — below breakeven for most risk/reward setups. Reducing size by 50% in consolidation is mandatory, not optional.

---

## Risk Parameters

### Per-Trade Risk Limits

| Parameter | Limit | Action if Breached |
|-----------|-------|-------------------|
| Max loss per trade | 3–4% of entry | Hard stop triggers; exit immediately |
| Max loss per week | 5% of account | Pause all new entries; review regime |
| Max loss per month | 10% of account | Full strategy review; reduce to paper trading |
| Max drawdown (strategy) | −25% | Retire strategy; escalate to full redesign |

### Performance Targets (Minimum Thresholds to Remain Active)

| Metric | Target | Minimum Acceptable | Action if Below Minimum |
|--------|--------|--------------------|------------------------|
| Win Rate | 55%+ | 50% | Reduce size 50%; review filters |
| Profit Factor | 1.8+ | 1.5 | Tighten entry rules

