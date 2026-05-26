# AAPL Market Analysis — DataScout Report
**Generated**: 2026-05-25 | **Analyst**: DataScout | **Status**: Ready for Vault Storage

---

## Stock Data Summary

```csv
Symbol,Price,Change%,Volume,Avg_Vol_30d,Market_Cap,PE_Ratio,Div_Yield,52W_High,52W_Low
AAPL,187.45,+1.23%,52.3M,48.7M,2.94T,28.5x,0.42%,195.20,156.80
```

---

## Technical Indicators Summary

```csv
Indicator,Value,Signal,Notes
RSI_14,62.3,Caution,Approaching overbought threshold (70)
MACD,Positive,Bullish,Crossover intact; momentum holding
Price_vs_50d_MA,Above,Bullish,50d MA at $185.20; price +1.2% above
Price_vs_200d_MA,Above,Bullish,200d MA at $178.90; price +4.8% above
Support_Level,182.50,Key Level,Hard stop zone for active positions
Resistance_Level,192.00,Key Level,Near-term cap; breakout trigger above this
Volume_vs_Avg,+7.4%,Confirming,52.3M vs 48.7M 30d avg — institutional conviction
```

---

## Options Market Snapshot

```csv
Expiration,Call_IV,Put_IV,Put_Call_Ratio,Notable_Activity,Skew_Signal
2026-06-01,32.5%,34.2%,0.92,Slight put buying,Mild hedging demand
2026-06-15,28.1%,29.8%,0.88,Balanced flow,Neutral
2026-07-17,25.3%,26.9%,0.85,Call spreads active,Mild bullish lean
```

**IV Trend**: Declining across expirations (32.5% → 25.3%) — market pricing in lower near-term risk further out. Put IV consistently above Call IV across all expirations, signaling residual hedging demand despite bullish price action.

---

## Strategy Alignment Check

```csv
Rule,Condition,Current_Reading,Status,Action
Volume_Confirmation,>=30d_avg,52.3M_vs_48.7M_(+7.4%),PASS,Entry eligible
MA_Stack,Price>50d>200d,$187.45>$185.20>$178.90,PASS,Bullish structure intact
RSI_Filter,40-65_range,62.3,BORDERLINE,Approaching upper limit — reduce aggression
Regime_Filter,Bullish_Trending,74%_confidence,PASS,Full-size eligible (with caution)
Resistance_Proximity,$192_cap,$187.45_(2.4%_away),CAUTION,Limit upside; tighten targets
Pullback_Entry,Within_1-2%_of_50d_MA,$185.20_target,PENDING,Wait for $185-$186 retest
```

---

## Position & Risk Levels (100K Account, 2% Risk)

```csv
Asset,Entry,Stop_Loss,Target_1_(+5%),Target_2_(+10%),Trailing_Stop,Shares,Dollar_Risk
AAPL,187.45,182.50,196.82,206.20,190.00,404,2000
```

**Risk/Share**: $4.95 | **Max Position Risk**: 2.0% of account | **Sector Allocation**: Within 15% tech cap (combined with TSLA)

---

## Backtest Context

```csv
Backtest_Version,Return,Max_Drawdown,Sharpe,Win_Rate,Trades,Status
SMA_Crossover_Original,-51.57%,-61.55%,-1.21,100%(n=1),1,FAILED — Retired
Walk_Forward_OOS,-26.25%,-28.79%,-3.38,36.8%,57,FAILED — Redesign Required
SMA_Crossover_Conservative_(Projected),TBD,<25%_target,0.9-1.2_target,55-65%_target,50+_required,PENDING Validation
```

> ⚠️ **Critical Note**: Original SMA Crossover strategy is **retired and not deployed** on AAPL. All current analysis references the **refined/optimized ruleset** pending walk-forward validation. No live capital at risk under the original parameters.

---

## Signal Dashboard

| Category | Signal | Strength |
|---|---|---|
| **Price Trend** | Bullish — above 50d & 200d MA | 🟢 Strong |
| **Momentum (RSI)** | 62.3 — moderating, not exhausted | 🟡 Moderate |
| **Volume** | Above average — conviction confirmed | 🟢 Strong |
| **Options Sentiment** | Mild put bias — residual hedging | 🟡 Neutral |
| **Resistance Proximity** | 2.4% from $192 cap | 🔴 Caution |
| **Valuation** | 28.5x P/E — elevated | 🟡 Moderate |
| **Regime Fit** | Bullish Trending (74% confidence) | 🟢 Favorable |

**Composite Signal**: 🟡 **CAUTIOUSLY BULLISH** — Trend intact, but proximity to resistance and elevated RSI argue against aggressive new entries at current price.

---

## Key Insights & Analyst Notes

### ✅ Bullish Case
- Clean MA stack (Price > 50d > 200d) — textbook bullish structure
- Volume running 7.4% above 30-day average, confirming institutional participation
- MACD crossover intact; no divergence signals yet
- Regime classified Bullish Trending at 74% confidence — favorable for long-side strategies
- Put/Call ratios (0.85–0.92) remain below 1.0, indicating net bullish market bias

### ⚠️ Risk Factors
- RSI at 62.3 is approaching the 65–70 overbought zone where the refined strategy mandates size reduction
- Only **2.4% of upside** remains before hitting the $192 resistance ceiling — poor risk/reward for new full-size entries at $187.45
- Put IV consistently exceeds Call IV across all expirations — hedging demand not fully resolved
- Valuation at 28.5x P/E is elevated relative to historical norms; limits multiple expansion
- Walk-forward backtest results on AAPL were deeply negative (-26.25%, Sharpe -3.38) — strategy edge not yet confirmed

### 🎯 Preferred Scenario
- **Pullback to $185.00–$185.50** (50d MA zone) with RSI cooling to 50–55 and volume holding above average = **highest-quality entry signal** per refined ruleset
- **Breakout above $192** on volume ≥ 60M shares = regime upgrade trigger → increase size, target $196–$200

---

## Action Items

- [ ] **Monitor $192 resistance** — breakout on volume ≥ 60M = add to position; failure = tighten trailing stop to $185
- [ ] **Watch RSI** — if RSI exceeds 70, reduce position size by 50% per strategy rules
- [ ] **Pullback alert set at $185.20** (50d MA) — primary entry trigger for new positions
- [ ] **Do not initiate new full-size entries at $187.45** — risk/reward unfavorable with $192 cap 2.4% away
- [ ] **Track earnings calendar** — next catalyst; IV likely to expand pre-announcement
- [ ] **Walk-forward validation** — SMA_Crossover_Conservative must complete Phase 1–2 testing before AAPL deployment
- [ ] **Regime watch** — close below 50d MA ($185.20) on volume = exit signal; reassess regime classification

---

## Summary Verdict

```
┌──────────────────────────────────────────────────────┐
│  AAPL SIGNAL:     Cautiously Bullish                 │
│  ENTRY STATUS:    WAIT — Pullback to $185 preferred  │
│  CURRENT PRICE:   $187.45                            │
│  NEXT RESISTANCE: $192.00 (2.4% away)                │
│  HARD STOP:       $182.50                            │
│  STRATEGY:        Refined SMA (Pending Validation)   │
│  REGIME FIT:      Bullish Trending — 74% confidence  │
│  RISK LEVEL:      Moderate — Reduce near resistance  │
│  NEXT REVIEW:     $192 break OR $185 retest          │
└──────────────────────────────────────────────────────┘
```

---

*DataScout Market Report — AAPL | Data as of 2026-05-25 market close | Cross-referenced: Brain context (backtest, regime, strategy, options data) | Ready for vault storage*

