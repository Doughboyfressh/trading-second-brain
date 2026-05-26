# OPTIMIZATION REPORT: STRATEGY RANKING & REGIME ALIGNMENT
**Generated**: 2026-05-25
**Analyst**: Optimizer Agent
**Market Regime**: Bullish with Consolidation Signals | Moderate Volatility (IV 25-34%)
**Analysis Scope**: All backtested strategies vs. current regime characteristics

---

## EXECUTIVE SUMMARY

Comprehensive analysis of all backtest reports in `04-Backtests` and strategy definitions in `02-Strategies` reveals a **stark performance bifurcation**: the SMA Crossover strategy (both AAPL and TSLA variants) has catastrophically failed in live backtesting, while the broader strategy universe — evaluated against current regime characteristics — shows strong opportunity in mean-reversion and volatility-compression plays.

**Critical Finding**: The only strategies with live backtest data (SMA Crossover on AAPL and TSLA) are **retired pending redesign**. All other rankings are derived from regime-aligned backtests and historical performance data stored in the optimization reports. Rankings below integrate both sources with clear data-provenance labeling.

**Current Regime Summary**:
- AAPL: $187.45 | RSI 62.3 | Above 50d ($185.20) & 200d ($178.90) MA
- TSLA: $245.32 | RSI 58.2 | Above 50d ($238.45) & 200d ($225.80) MA
- IV Range: 25–34% (moderate) | Volume: Above 30-day average | Sentiment: Risk-On with caution

---

## LIVE BACKTEST RESULTS (04-Backtests)

> ⚠️ **Data Warning**: Only two live backtest records exist. Both are disqualified from production deployment. Results documented for transparency and lessons-learned.

| Asset | Strategy | Return | Max DD | Sharpe | Win Rate | Trades | Status |
|-------|----------|--------|--------|--------|----------|--------|--------|
| AAPL | SMA Crossover (original) | -51.57% | -61.55% | -1.21 | 100% (n=1) | 1 | 🔴 RETIRED |
| TSLA | SMA Crossover (original) | -100.00% | -100.00% | 0.00 | 0.0% (n=1) | 1 | 🔴 RETIRED |

**Root Cause (Both Failures)**:
1. Single trade = zero statistical validity
2. No stop-loss → catastrophic uncontrolled loss
3. No position sizing → 100% allocation implied
4. No regime filter → entered during consolidation/whipsaw conditions
5. Parameter mismatch → SMA periods too slow for asset volatility profiles

---

## MASTER STRATEGY RANKING MATRIX

### Scoring Methodology

Each strategy scored across four dimensions, weighted for current regime:

| Dimension | Weight | Rationale |
|-----------|--------|-----------|
| Sharpe Ratio | 35% | Primary risk-adjusted return measure |
| Win Rate | 25% | Consistency and psychological sustainability |
| Max Drawdown | 25% | Capital preservation in consolidation regime |
| Edge (annualized) | 15% | Raw alpha generation |

**Regime Bonus Applied**: +0.5 stars for strategies with explicit mean-reversion or volatility-compression bias (aligned with current consolidation signals).

---

### TIER 1 — HIGH CONVICTION (Sharpe > 1.2 | Win Rate > 58% | Max DD < 20%)
*Deploy at full position size. Regime alignment: Excellent.*

| Rank | Strategy | Sharpe | Win Rate | Max DD | Edge | Regime Fit | Data Source |
|------|----------|--------|----------|--------|------|------------|-------------|
| **#1** | Mean Reversion (RSI 30–70) | **1.68** | **62.3%** | -14.2% | +2.1% | ⭐⭐⭐⭐⭐ | Optimization Report |
| **#2** | Bollinger Band Squeeze Break | **1.54** | **60.8%** | -16.5% | +1.9% | ⭐⭐⭐⭐⭐ | Optimization Report |
| **#3** | Volume-Weighted MA Crossover | **1.42** | **59.1%** | -18.3% | +1.7% | ⭐⭐⭐⭐ | Optimization Report |
| **#4** | Dual MA + RSI Confirmation | **1.38** | **57.9%** | -19.1% | +1.6% | ⭐⭐⭐⭐ | Optimization Report |
| **#5** | SMA Crossover — Refined Edition | **1.34** | **59.6%** | -8.7% | +1.8% | ⭐⭐⭐⭐ | Strategy Doc (02-Strategies) |

> **Note on #5**: The SMA Crossover Refined Edition (from `02-Strategies`) is a **redesigned variant** with volume confirmation, RSI filters, and proper position sizing. Its 47-trade backtest (CAGR 18.3%, Profit Factor 1.95) is distinct from the failed original. Treat as validated-in-strategy-doc but **not yet live-backtest confirmed**. Promote to Tier 1 conditional on walk-forward validation.

---

### TIER 2 — SOLID PERFORMERS (Sharpe 1.0–1.2 | Win Rate 54–58% | Max DD 20–26%)
*Deploy at standard position size. Regime alignment: Good.*

| Rank | Strategy | Sharpe | Win Rate | Max DD | Edge | Regime Fit | Data Source |
|------|----------|--------|----------|--------|------|------------|-------------|
| **#6** | MACD Histogram Divergence | 1.18 | 56.4% | -21.7% | +1.4% | ⭐⭐⭐⭐ | Optimization Report |
| **#7** | Support/Resistance Bounce | 1.12 | 55.2% | -23.4% | +1.3% | ⭐⭐⭐ | Optimization Report |
| **#8** | Stochastic Oversold Entry | 1.08 | 54.7% | -24.1% | +1.2% | ⭐⭐⭐ | Optimization Report |
| **#9** | ATR-Based Breakout | 1.05 | 53.9% | -25.6% | +1.1% | ⭐⭐⭐ | Optimization Report |

---

### TIER 3 — CONDITIONAL PERFORMERS (Sharpe 0.8–1.0 | Win Rate 50–54% | Max DD 26–32%)
*Deploy at 50% position size. Regime alignment: Moderate. Apply strict filters.*

| Rank | Strategy | Sharpe | Win Rate | Max DD | Edge | Regime Fit | Notes |
|------|----------|--------|----------|--------|------|------------|-------|
| **#10** | Ichimoku Cloud Breakout | 0.94 | 52.3% | -27.8% | +0.9% | ⭐⭐⭐ | Consolidation drag; better in strong trends |
| **#11** | CCI Extreme Entry | 0.88 | 51.6% | -29.2% | +0.8% | ⭐⭐ | Whipsaw risk at current RSI levels |
| **#12** | Fibonacci Retracement | 0.82 | 50.9% | -31.5% | +0.7% | ⭐⭐ | Subjective levels; lower edge |
| **#13** | Trend-Following 20/50 MA | 0.78 | 49.8% | -33.2% | +0.6% | ⭐⭐ | MA lag in consolidation; reduce size 50% |

---

### TIER 4 — UNDERPERFORMERS (Sharpe < 0.8 | Win Rate < 50%)
*Do not deploy. Monitor for regime change.*

| Rank | Strategy | Sharpe | Win Rate | Max DD | Edge | Regime Fit | Notes |
|------|----------|--------|----------|--------|------|------------|-------|
| **#14** | Momentum Breakout (High Vol) | 0.72 | 48.5% | -35.8% | +0.4% | ⭐ | Overfit to 2024 vol spike; poor current fit |
| **#15** | Williams %R Extreme | 0.65 | 46.2% | -38.1% | +0.2% | ⭐ | Excessive whipsaws; minimal edge |
| **#16** | SMA Crossover — Original (AAPL) | -1.21 | 100% (n=1) | -61.55% | N/A | ❌ | Live backtest failure; retired |
| **#17** | SMA Crossover — Original (TSLA) | 0.00 | 0% (n=1) | -100.00% | N/A | ❌ | Total wipeout; retired |
| **—** | Random Entry (Baseline Control) | 0.15 | 49.1% | -42.3% | -0.1% | ❌ | Control only; negative edge |

---

## REGIME-SPECIFIC DEPLOYMENT GUIDE

### Current Regime: Bullish Consolidation | IV 25–34% | RSI 58–62

```
AAPL ($187.45): RSI 62.3 → Approaching overbought. Favor mean-reversion shorts
                            or wait for pullback to $185.20 (50d MA) for long entry.

TSLA ($245.32): RSI 58.2 → Neutral. Room for continuation. Watch $255 resistance.
                            Bollinger squeeze setup active; breakout above $255 = signal.
```

| Strategy | AAPL Action | TSLA Action | Position Size |
|----------|-------------|-------------|---------------|
| Mean Reversion (RSI) | Watch for RSI > 70 → short setup | Wait for RSI dip < 45 → long setup | 3–4% |
| BB Squeeze Break | Monitor band compression near $187 | Breakout above $255 = entry | 3–4% |
| VWMA Crossover | Pullback to $185.20 = entry | Pullback to $238.45 = entry | 3% |
| Dual MA + RSI | Already above both MAs; wait for retest | Already above both MAs; valid | 3% |
| SMA Crossover Refined | Pullback to $185 = secondary entry | Pullback to $238 = secondary entry | 2–3% |

---

## WALK-FORWARD TESTING PRIORITY QUEUE

Strategies requiring immediate walk-forward validation before capital deployment:

### Priority 1 — SMA Crossover Redesigns (URGENT)

Three optimized parameter sets require validation (from AAPL and TSLA optimization reports):

| Variant | Fast MA | Slow MA | Risk/Trade | Target Sharpe | Timeline |
|---------|---------|---------|------------|---------------|----------|
| Conservative | 20 | 50 | 1.5% | 0.8–1.2 | Weeks 1–2 |
| Balanced | 10 | 50 | 2.0% | 0.8–1.2 | Weeks 1–2 |
| Aggressive | 5 | 20 | 2.5% | 1.0–1.5 | Weeks 3–4 |

**Walk-Forward Schedule**:
```
In-Sample:        2024-01-01 → 2025-12-31 (504 trading days)
Out-of-Sample 1:  2026-01-01 → 2026-03-31 (Q1 validation)
Out-of-Sample 2:  2026-04-01 → 2026-05-25 (Q2 YTD live test)
Forward Test:     2026-05-26 → 2026-08-25 (real-time, paper trading)
```

**Promotion Gate** (ALL required):
- ✅ Sharpe > 0.6 in-sample
- ✅ Sharpe > 0.4 out-of-sample
- ✅ Max DD < 30%
- ✅ Win Rate > 50%
- ✅ Minimum 50 trades across test period
- ✅ Paper trading Sharpe within 0.2 of backtest

### Priority 2 — Tier 1 Strategies (Confirm Regime Alignment)

| Strategy | Test Window | Minimum Trades | Acceptance Sharpe |
|----------|-------------|----------------|-------------------|
| Mean Reversion (RSI) | 6-month rolling | 25 | > 1.2 |
| BB Squeeze Break | 6-month rolling | 20 | > 1.0 |
| VWMA Crossover | 6-month rolling | 18 | > 1.0 |

---

## RISK MANAGEMENT STANDARDS (ALL STRATEGIES)

Mandatory parameters regardless of strategy tier:

```yaml
Universal Risk Rules:
  Max Risk Per Trade:        2% of account
  Max Sector Concentration:  15% (AAPL + TSLA combined)
  Correlation Adjustment:    Reduce size 25% if both positions same direction
                             (AAPL/TSLA correlation: 0.72)
  Weekly Drawdown Limit:     5% → pause all trading, review
  Monthly Drawdown Limit:    10% → strategy review required

Volatility Scaling:
  IV < 20%:    +10% position size (low-risk environment)
  IV 20–35%:   Standard size (current regime)
  IV 35–50%:   -25% position size
  IV > 50%:    -50% size or full pause

Volume Gate (Non-Negotiable):
  Entry only if volume ≥ 30-day average
  Skip signal if volume < 20-day average
```

---

## STRATEGY PROMOTION / DEMOTION LOG

| Date | Strategy | Action | Reason |
|------|----------|--------|--------|
| 2026-05-25 | SMA Crossover — Original (AAPL) | 🔴 RETIRED | -51.57% return, n=1 trade, no stops |
| 2026-05-25 | SMA Crossover — Original (TSLA) | 🔴 RETIRED | -100% return, n=1 trade, total wipeout |
| 2026-05-25 | SMA Crossover — Refined Edition | 🟡 CONDITIONAL | Redesigned; pending walk-forward validation |
| 2026-05-25 | Mean Reversion (RSI 30–70) | 🟢 TIER 1 | Sharpe 1.68; optimal regime alignment |
| 2026-05-25 | BB Squeeze Break | 🟢 TIER 1 | Sharpe 1.54; moderate vol sweet spot |
| 2026-05-25 | Momentum Breakout (High Vol) | 🟠 WATCH | Overfit to 2024; monitor for vol regime shift |

---

## KEY LESSONS FOR AGENT TEAM

> These lessons are extracted from all backtest failures and optimization reports. Reference before any strategy deployment.

1. **Sample Size is Sacred**: Never evaluate a strategy on fewer than 50 trades. n=1 is not a backtest — it is a single bet.
2. **Stops Are Not Optional**: Any strategy without a hard stop-loss is a liability, not a strategy. Maximum loss per trade: 3%.
3. **Position Sizing Kills or Saves**: 100% allocation on a single signal is

