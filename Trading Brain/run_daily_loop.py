# run_daily_loop.py
from datetime import datetime

from src.agents.data_scout import DataScout
from src.agents.market_analyst import MarketAnalyst
from src.agents.strategist import Strategist
from src.agents.optimizer import Optimizer
from src.agents.risk_guardian import RiskGuardian
from src.agents.critic import Critic
from src.agents.regime_classifier import RegimeClassifier
from src.agents.sentiment_agent import SentimentAgent     # ← New
from src.agents.meta_evaluator import MetaEvaluator       # ← New

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
    
    # 2. Regime + Sentiment
    print("📈 [RegimeClassifier] Detecting current market regime...")
    regime = RegimeClassifier()
    regime.classify_regime()
    
    print("📰 [SentimentAgent] Analyzing news & sentiment...")
    sentiment = SentimentAgent()
    sentiment.analyze_sentiment()
    
    # 3. Market Analyst
    print("📊 [MarketAnalyst] Writing daily analysis...")
    analyst = MarketAnalyst()
    analyst.daily_analysis()
    
    # 4. Optimizer + Strategist
    print("🔬 [Optimizer + Strategist] Running walk-forward optimization...")
    strategist = Strategist()
    optimizer = Optimizer()
    optimizer.run_optimization_loop(tickers=["AAPL", "TSLA"])
    optimizer.rank_strategies()
    strategist.refine_strategy("SMA_Crossover")
    
    # 5. Meta-Evaluator + Critic
    print("📊 [MetaEvaluator] Evaluating long-term performance...")
    meta = MetaEvaluator()
    meta.evaluate_performance()
    
    critic = Critic()
    critic.review_note("02-Strategies", "SMA_Crossover.md")
    
    # 6. Risk Guardian (with Telegram alerts)
    print("🛡️ [RiskGuardian] Daily risk sweep + alerts...")
    guardian = RiskGuardian()
    guardian.daily_risk_sweep()
    
    print("✅ PHASE 2 COMPLETE! Full upgraded second brain is now running.")
    print("   Open vault/ in Obsidian to see the new sentiment, meta-eval, and ensemble notes 🚀")

if __name__ == "__main__":
    main()