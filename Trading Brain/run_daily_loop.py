# run_daily_loop.py
from datetime import datetime

from src.agents.data_scout import DataScout
from src.agents.market_analyst import MarketAnalyst
from src.agents.strategist import Strategist
from src.agents.optimizer import Optimizer
from src.agents.risk_guardian import RiskGuardian
from src.agents.critic import Critic
from src.agents.regime_classifier import RegimeClassifier   # ← New

from src.backtester import run_backtest
from src.data_fetcher import DataFetcher
from src.vault_manager import VaultManager


def main():
    print(f"🚀 Starting Trading Second Brain Daily Loop - {datetime.now()}")
    
    # 1. Data Scout
    print("📡 [DataScout] Updating asset data...")
    scout = DataScout()
    for ticker in ["AAPL", "TSLA"]:
        scout.update_asset_data(ticker)
    
    # New: Regime Classification
    print("📈 [RegimeClassifier] Detecting current market regime...")
    regime = RegimeClassifier()
    regime.classify_regime()
    
    # 2. Market Analyst
    print("📊 [MarketAnalyst] Writing daily analysis...")
    analyst = MarketAnalyst()
    analyst.daily_analysis()
    
    # 3. Optimizer + Strategist (now with walk-forward)
    print("🔬 [Optimizer + Strategist] Running walk-forward optimization...")
    strategist = Strategist()
    optimizer = Optimizer()
    optimizer.run_optimization_loop(tickers=["AAPL", "TSLA"])
    optimizer.rank_strategies()
    strategist.refine_strategy("SMA_Crossover")
    
    # Critic review
    critic = Critic()
    critic.review_note("02-Strategies", "SMA_Crossover.md")
    
    # Risk Guardian
    print("🛡️ [RiskGuardian] Daily risk sweep...")
    guardian = RiskGuardian()
    guardian.daily_risk_sweep()
    
    print("✅ Phase 1 upgrades complete! Walk-forward + regime detection now active.")
    print("   Open vault/ in Obsidian — your second brain is now much more intelligent 🚀")

if __name__ == "__main__":
    main()