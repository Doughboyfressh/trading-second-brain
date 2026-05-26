# CRITIC REVIEW: SMA Crossover Strategy v3.0
**Reviewed**: 2026-05-25 | **Reviewer**: Critic Agent | **Verdict**: 🟡 CONDITIONAL — Significant Flaws Remain

---

## OVERALL ASSESSMENT

The v3.0 redesign shows genuine improvement over the catastrophic v1.0/v2.0 failures. The author correctly identified the four root causes and built rules to address them. However, **the strategy has not yet earned its "Active" status label**. Several logical contradictions, unvalidated assumptions, and structural risks remain that could cause the same class of failure in live trading.

**Brutally honest summary**: This is a well-formatted document describing a strategy that has never produced positive out-of-sample results. The walk-forward tests (AAPL: −26.25%, Sharpe −3.38; TSLA: −15.16%, Sharpe −1.06) are the only real data points, and both are deeply negative. Everything else — the projected Sharpe ranges, expected win rates, regime tables — is speculative. The document reads more confidently than the evidence warrants.

---

## CRITICAL FLAWS

### FLAW 1: Status Label Is Dishonest
**Severity**: 🔴 HIGH

```
Current Label: 🟡 Active — Redesigned | Pending Walk-Forward Validation
```

**Problem**: A strategy labeled "Active" implies it is deployable. This strategy has:
- Zero positive out-of-sample results across any version
- Walk-forward Sharpe of −3.38 (AAPL) and −1.06 (TSLA)
- No completed walk-forward validation on v3.0 parameters specifically

**The v3.0 rules have never been backtested.** The parameter sets, regime filters, and entry rules described are *proposed*, not validated. The document conflates "redesigned on paper" with "validated for deployment."

**Required Fix**:
```
Correct Label: 🔴 PAPER DESIGN ONLY — Not Validated | Do Not Trade Real Capital
```
Do not change status to Active until v3.0 parameters specifically pass the walk-forward schedule defined in Section 8.

---

### FLAW 2: The Backtest Performance Table Is Fabricated
**Severity**: 🔴 HIGH

The "Refined Edition" document embedded in context contains this table:

```
Total Trades: 47
Winning Trades: 28 (59.6%)
Sharpe Ratio: 1.34
Max Drawdown: -8.7%
CAGR: 18.3%
```

**This data does not correspond to any actual backtest in the record.** Every real backtest shows negative returns. This table appears to be a projection or hypothetical presented as historical fact. If a trader reads this document and acts on those numbers, they are trading on fabricated performance data.

**Required Fix**: Remove or clearly label any performance table that was not produced by an actual backtest engine run. Replace with:

```
⚠️ NOTE: Performance figures below are PROJECTED TARGETS based on 
parameter optimization theory, NOT historical backtest results. 
Actual backtested results for all prior versions are negative. 
See Section 1 (Version History) for real performance data.
```

---

### FLAW 3: Position Sizing Formula Produces Dangerous Notional Exposure
**Severity**: 🔴 HIGH

```
Example — AAPL (Set B, $100K account, 2% risk):
  = $2,000 ÷ $5.62 = 355 shares (~$66,600 notional)
```

**Problem**: A 2% risk allocation is producing **66.6% notional exposure** to a single stock. The formula is technically correct for risk-per-trade, but the document fails to flag that a 3% stop on a $66,600 position means a gap-down, halt, or earnings miss could produce losses far exceeding the 2% risk target.

**Specific failure modes not addressed**:
- **Gap risk**: TSLA regularly gaps 5–15% on earnings or macro events. A 3% hard stop does not protect against overnight gaps.
- **Liquidity risk**: 355 shares of AAPL is fine; but the formula scales dangerously if applied to less liquid names.
- **Correlation compounding**: Two simultaneous positions (AAPL + TSLA) at 66% notional each = 133% gross exposure on a $100K account. The 15% sector cap rule contradicts the sizing formula output.

**Required Fix**:
```
Add hard notional cap:
  Max notional per position: 20% of account ($20,000 on $100K)
  
If formula output exceeds notional cap, use notional cap instead.
This overrides the risk-per-trade formula when stop is very tight.

Add gap risk acknowledgment:
  All stop-loss levels assume orderly markets. 
  Earnings gaps, halts, or macro shocks can produce losses 
  2–5x the stated stop distance. Size accordingly.
```

---

### FLAW 4: Regime Filter Has Circular Logic
**Severity**: 🟠 MEDIUM-HIGH

The Bullish Trending regime requires:
```
✅ RSI(14) between 45–70
✅ Higher highs + higher lows on daily chart (last 10 bars)
```

The Consolidation regime triggers on:
```
⚠️ RSI between 45–55 (no directional momentum)
```

**Problem**: RSI 45–55 satisfies BOTH the Bullish Trending condition (45–70) AND the Consolidation condition (45–55) simultaneously. A trader at RSI 50 gets contradictory signals from the same framework. There is no tiebreaker rule.

**Additionally**: "Higher highs + higher lows on last 10 bars" is subjective. Two traders will disagree on whether bar 7 of 10 constitutes a higher high. This is not a mechanical rule — it is a judgment call dressed as a rule.

**Required Fix**:
```
Revised Regime Logic (non-overlapping):

BULLISH:       RSI > 55 AND Price > 50d MA AND 50d MA slope > +0.15%/week
CONSOLIDATION: RSI 40–55 AND (Price within 3% of 50d MA OR 50d MA slope < 0.1%/week)
BEARISH:       RSI < 45 AND Price < 50d MA on above-avg volume

Replace "higher highs/lows" with mechanical rule:
  "10-bar linear regression slope of closing prices > 0" (bullish)
  "10-bar linear regression slope within ±0.05% of flat" (consolidation)
```

---

### FLAW 5: Confirmation Bar Delay Is Untested and Potentially Counterproductive
**Severity**: 🟠 MEDIUM-HIGH

```
Set A: Wait 10 bars post-crossover before entry
Set B: Wait 5 bars post-crossover before entry
Set C: Wait 3 bars post-crossover before entry
```

**Problem**: SMA crossovers are already lagging indicators. Adding a 5–10 bar confirmation delay on top of a lagging signal means entries occur 1–2 weeks after the actual trend change. On a stock like TSLA with 3–8% weekly moves, this delay could mean entering after 60–80% of the move has already occurred.

**No evidence is provided that confirmation delays improve performance.** The walk-forward tests used "regime-aware sizing + stops" but it is unclear whether confirmation delays were included. If they were, the −26.25% and −15.16% results already reflect them.

**Required Fix**:
```
Test confirmation delays explicitly in walk-forward:
  - 0 bars (immediate entry)
  - 3 bars
  - 5 bars
  - 10 bars

Report win rate and average entry slippage for each.
Do not assume delays help without data.

Interim rule: Use 3-bar maximum until tested. 
10-bar delay on a daily chart = 2 calendar weeks of missed move.
```

---

### FLAW 6: Earnings Disqualifier Is Incomplete
**Severity**: 🟠 MEDIUM

```
❌ Earnings announcement within 5 trading days
```

**Problem**: This rule only blocks new entries. It does not address:
- What happens to **existing positions** when earnings approach within 5 days
- Whether to exit before earnings or hold through
- Post-earnings re-entry rules (gap-up or gap-down scenarios)

TSLA and AAPL both have quarterly earnings that can move the stock 8–15%. A position entered 10 days before earnings and held through the announcement faces binary risk that the stop-loss cannot protect against (gap risk, as noted in Flaw 3).

**Required Fix**:
```
Earnings Protocol (add to Exit Rules):

PRE-EARNINGS (5 days before):
  - No new entries (existing rule — keep)
  - Existing positions: Exit 50% at market open 5 days before earnings
  - Move stop on remaining 50% to breakeven
  - Rationale: Eliminate gap risk on majority of position

POST-EARNINGS (gap-up scenario):
  - If price gaps up > 5%: Do not chase; wait for pullback to Fast MA
  - If price gaps down > 5%: Exit remaining position at open; 
    stop-loss cannot protect against overnight gaps

POST-EARNINGS (gap-down scenario):
  - Accept loss; do not average down
  - Re-evaluate regime before any new entry
```

---

### FLAW 7: The "Expected Sharpe" Ranges Are Unjustified
**Severity**: 🟠 MEDIUM

Throughout the document:
```
Set A Expected Sharpe: 0.9–1.2
Set B Expected Sharpe: 0.8–1.2
Set C Expected Sharpe: 1.0–1.5
```

**Problem**: These ranges have no basis in actual backtest data. The only real Sharpe ratios produced by this strategy family are:
- v1.0 AAPL: −1.21
- v1.0 TSLA: 0.00
- v2.0 WF AAPL: −3.38
- v2.0 WF TSLA: −1.06

Projecting Sharpe of 1.0–1.5 for Set C when the best result ever achieved is 0.00 is not optimization — it is wishful thinking presented as analysis. A trader reading this document could anchor on these numbers and deploy capital prematurely.

**Required Fix**:
```
Replace all "Expected Sharpe" fields with:

  "Target Sharpe (unvalidated): X.X–X.X"
  "Actual Sharpe (best historical): −1.06 (v2.0 WF TSLA)"
  
Do not publish expected performance ranges until at least one 
walk-forward test of v3.0 parameters produces a positive Sharpe.
```

---

### FLAW 8: Correlated Pair Reduction Rule Is Mathematically Insufficient
**Severity**: 🟡 MEDIUM

```
Correlated pair reduction: −25% size if both AAPL & TSLA active
Correlation: 0.72
```

**Problem**: At correlation 0.72, two positions sized at 75% each produce an effective single-position risk of approximately 1.47x (not 0.75x). The −25% reduction is cosmetic, not mathematically meaningful for correlation management.

**Additionally**: The 0.72 correlation figure is presented without a time period. AAPL-TSLA correlation varies significantly — it can spike to 0.90+ during broad market selloffs (exactly when you most need the hedge) and drop to 0.40 during idiosyncratic moves.

**Required Fix**:
```
Replace flat −25% rule with correlation-adjusted sizing:

  If correlation(AAPL, TSLA, 30d) > 0.70:
    Treat as single position for risk purposes
    Combined risk cap: 2.5% of account (not 2% × 2 = 4%)
    
  If correlation < 0.50:
    Standard independent sizing applies
    
  If correlation > 0.85 (market stress):
    Exit one position; do not hold both simultaneously
    
Note: Recalculate rolling 30-day correlation weekly.
```

---

## MODERATE ISSUES

### ISSUE 1: Time Stop Logic Is Vague
```
Trigger: No movement (< 1% from entry) after 10 trading bars
```
"No movement" is undefined. Does this mean the close is within 1% of entry? The high/low range? The average of the last 3 bars? This needs a precise mechanical definition or it will not be applied consistently.

**Fix**: Define as: *"If the closing price on bar 10 is within ±1% of the entry price AND the position has not hit Target 1, exit at next open."*

---

### ISSUE 2: 4H Entry Timing Is Mentioned But Never Defined
```
Timeframe: Daily bars (primary); 4H for entry timing
```
The document mentions 4H charts for entry timing but provides zero rules for how to use them. This creates ambiguity — does a trader wait for a 4H close above the Fast MA? A 4H volume confirmation? This is an incomplete rule that will be applied inconsistently.

**Fix**: Either define the 4H entry timing rules explicitly or remove the reference until they are developed.

---

### ISSUE 3: "Never Average Down" Rule Is Stated But Not Enforced
The playbook states "Never Average Down" but the position sizing section has no explicit prohibition on adding to losing positions. In live trading, the temptation to average down is strongest when a position is underwater. The rule needs to appear in the Exit Rules section with a mechanical enforcement mechanism.

**Fix**: Add to Exit Rules: *"If price moves against entry by more than 1.5%, no additional shares may be purchased in this position under any circumstances. Violation of this rule is a playbook breach requiring trade journal documentation."*

---

### ISSUE 4: Put/Call Ratio Thresholds Are Arbitrary
```
Bullish: Put/Call ratio < 1.0
Bearish: Put/Call ratio > 1.2
```
The gap between 1.0 and 1.2 creates a dead zone with no defined action. More importantly, these thresholds are not calibrated to AAPL or TSLA specifically — they appear to be generic market-level thresholds applied to individual stocks. TSLA's options market has structurally different put/call dynamics than AAPL's.

**Fix**: Either use equity-specific put/call ratios with historically calibrated thresholds, or remove this filter until it is properly backtested as a signal component.

---

### ISSUE 5: The Strategy Ranking Matrix Conflicts With This Document
The optimization report ranks "Mean Reversion (RSI 30-70)" as the #1 strategy with Sharpe 1.68 and win rate 62.3%. If that data is credible, it directly argues against deploying SMA Crossover v3.0 at all. The document does not acknowledge this contradiction.

**Fix**: Add a section explicitly comparing SMA Crossover v3.0 to the top-ranked alternatives and justify why this strategy is being pursued over Mean Reversion or Bollinger Band Squeeze, which have superior documented performance.

---

## STRUCTURAL IMPROVEMENTS REQUIRED

### Improvement 1: Add a Validation Gate Table

Before the strategy can be labeled Active, it must pass explicit gates. Add this table:

```markdown
## Validation Gates (v3.0 Must Pass ALL Before Deployment)

| Gate | Test | Required Result | Status |
|------|------|-----------------|--------|
| G1 | In-sample backtest (2024–2025, v3.0 params) | Sharpe > 0.8, Win Rate > 50%, Max DD < 25% | ❌ NOT RUN |
| G2 | Out-of-sample Q1 2026 | Sharpe > 0.5, Win Rate > 45% | ❌ NOT RUN |
| G3 | Walk-forward (rolling 6-month windows) | Avg OOS Sharpe > 0.6 | ❌ NOT RUN |
| G4 | Paper trading (minimum 20 trades) | Sharpe within 0.2 of backtest | 

