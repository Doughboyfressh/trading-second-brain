# src/agents/news_scout.py
from src.agents.base import BaseAgent
from src.data_fetcher import DataFetcher
from src.llm import TradingLLM
from datetime import datetime
from config import WATCHLIST


class NewsScout(BaseAgent):
    def __init__(self):
        super().__init__(
            "NewsScout",
            "You are NewsScout. Summarize recent financial news for the given tickers. "
            "For each ticker: list 2-3 key headlines, rate sentiment "
            "(BULLISH / NEUTRAL / BEARISH), and flag major catalysts "
            "(earnings, guidance, M&A, FDA, macro, analyst upgrades/downgrades). "
            "Be concise and factual — never fabricate headlines.",
            model=TradingLLM.HAIKU,
            max_tokens=1400,
            rag_top_k=2,
        )
        self.fetcher = DataFetcher()

    def scan_news(self, tickers: list = None):
        if tickers is None:
            tickers = WATCHLIST

        all_news = ""
        for ticker in tickers:
            headlines = self.fetcher.get_news(ticker, limit=5)
            all_news += f"\n### {ticker}\n"
            if headlines:
                for h in headlines:
                    all_news += f"- [{h['time']}] **{h['title']}** — {h['publisher']}\n"
            else:
                all_news += "- No recent news found.\n"

        self.think_and_write(
            f"Summarize and rate the sentiment for these recent news headlines:\n{all_news}",
            "05-News",
            f"NEWS_{datetime.now().strftime('%Y-%m-%d')}.md",
        )
        print("News scan complete")
