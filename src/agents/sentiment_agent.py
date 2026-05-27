# src/agents/sentiment_agent.py
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from src.llm import TradingLLM
from datetime import datetime
from config import WATCHLIST


class SentimentAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            "SentimentAgent",
            "You are SentimentAgent. Output a structured sentiment report with:\n"
            "OVERALL MARKET SENTIMENT: <BULLISH | NEUTRAL-BULLISH | NEUTRAL | NEUTRAL-BEARISH | BEARISH>\n"
            "CONFIDENCE: <N>%\n"
            "Per-ticker: <TICKER>: <N>% bullish — <1-line rationale>\n"
            "BLENDED SCORE: <N>% bullish\n"
            "Base your scores on the actual news headlines and technical data provided.",
            model=TradingLLM.HAIKU,
            max_tokens=1200,
            rag_top_k=3,
        )
        self.fetcher = DataFetcher()

    def analyze_sentiment(self, tickers: list = None):
        """
        Analyze sentiment for all watchlist tickers (or a custom list).
        Fetches up to 4 headlines per ticker; batches large watchlists so the
        prompt stays within a reasonable token budget.
        """
        if tickers is None:
            tickers = WATCHLIST

        news_block = ""
        for ticker in tickers:
            headlines = self.fetcher.get_news(ticker, limit=4)
            news_block += f"\n### {ticker} recent headlines:\n"
            if headlines:
                for h in headlines:
                    news_block += f"- [{h['time']}] {h['title']} ({h['publisher']})\n"
            else:
                news_block += "- No recent news found.\n"

        task = (
            f"Analyze current market sentiment for: {', '.join(tickers)}.\n\n"
            f"REAL NEWS HEADLINES:\n{news_block}\n\n"
            "Also use regime data and recent analysis in the vault. "
            "Score each ticker and produce BLENDED SCORE."
        )
        self.think_and_write(task, "00-Daily", f"sentiment_{datetime.now().strftime('%Y-%m-%d')}.md")
