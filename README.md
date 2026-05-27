# 🧠 Trading Brain

A multi-agent AI trading system powered by Anthropic Claude, running against Alpaca paper trading.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env (copy from template)
#    Fill in your API keys
cp .env.example .env

# 3. (First time) Download 10-year historical data
python download_history.py

# 4. (Weekly) Optimise strategy parameters
python train_strategies.py

# 5. Run the daily trading loop
python run_daily_loop.py

# 6. Launch the dashboard
streamlit run dashboard.py
```

---

## Dashboard

```bash
streamlit run dashboard.py
```

Opens at **http://localhost:8501** — reads the vault in real time, no network calls.

| Tab | Contents |
|-----|----------|
| 💼 Portfolio | Equity, cash, open positions, signal ledger |
| 🎯 Signals | Today's signals with RiskGuardian verdicts |
| 🌡️ Market | Regime, VIX, volatility, sector rotation |
| 📈 Strategy | Profit-factor heatmap, best params, ranking |
| 🔍 Reviews | Critic reviews, OutcomeTracker, run logs |

Click **🔄 Refresh** to reload all vault data (or wait ~60s for automatic cache expiry).

---

## Architecture

15 agents orchestrated by `run_daily_loop.py`:

```
Phase 1a — DataScout       (prefetch CSVs + indicators)
Phase 1b — NewsScout + SectorScout  (parallel)
Phase 2  — RegimeClassifier + VolatilityAgent  (parallel)
Phase 3  — SentimentAgent → MarketAnalyst
Phase 3.5— HistoricalTrainer.run_regime_check()
Phase 4  — Optimizer → Strategist → MetaEvaluator + Critic
Phase 5  — Critic reviews strategy
Phase 6  — SignalGenerator
Phase 7  — RiskGuardian (7-gate sweep)
Phase 8  — Critic reviews signals + risk sweep
Phase 9  — ExecutionAgent (bracket orders)
Phase 10 — PnLTracker + OutcomeTracker
```

---

## Key Files

| File | Purpose |
|------|---------|
| `run_daily_loop.py` | Master orchestrator |
| `dashboard.py` | Streamlit dashboard |
| `train_strategies.py` | Weekly strategy optimisation (~10–25 min) |
| `download_history.py` | Download / refresh 10-year CSVs |
| `config.py` | API keys, constants (reads `.env`) |
| `src/agents/` | All 15 agent implementations |
| `src/llm.py` | TradingLLM with prompt caching + retries |
| `src/alpaca_broker.py` | Alpaca paper trading wrapper |
| `src/backtester.py` | 8-strategy walk-forward backtester |
| `src/historical_loader.py` | 10-year CSV hub |
| `src/earnings_cache.py` | Shared earnings calendar cache |
| `vault/` | Agent outputs (Obsidian-compatible markdown) |
| `data/historical/` | 10-year CSVs + best_params.json |
| `logs/` | Daily run logs |

---

## Environment Variables (`.env`)

```
ANTHROPIC_API_KEY=sk-ant-...
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Optional
POLYGON_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
WATCHLIST=AAPL,TSLA,NVDA,AMD,GOOGL,MSFT,AMZN,META

# Tunable constants (defaults shown)
BACKTEST_CASH=100000
BACKTEST_COMMISSION=0.002
CIRCUIT_BREAKER_DRAWDOWN_PCT=0.10
```

---

## Strategies

8 strategies backtested over 10 years × 8 tickers (64 sessions):

| Strategy | Status |
|----------|--------|
| RSI_MeanReversion | ✅ Development candidate (lowest drawdown) |
| BB_Reversion | ⚠️ MSFT + META only |
| MACD_Momentum | 🔴 Retired |
| SMA_Crossover | 🔴 Retired |
| EMA_Momentum | 🔴 Retired |
| Volume_Breakout | 🔬 Bull regime candidate |
| Trend_Pullback | 🔬 Researching |
| ROC_Momentum | 🔬 Researching |

Re-run `train_strategies.py` weekly to refresh `data/historical/best_params.json`.
