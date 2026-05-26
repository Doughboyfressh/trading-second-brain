# src/data_fetcher.py
from polygon import RESTClient
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, OrderType
import pandas as pd
from datetime import datetime
from config import POLYGON_API_KEY, ALPACA_API_KEY, ALPACA_SECRET_KEY

class DataFetcher:
    def __init__(self):
        self.polygon = RESTClient(api_key=POLYGON_API_KEY)
        self.alpaca = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
    
    def fetch_historical(self, ticker: str, multiplier=1, timespan="day", days_back=730):
        """Simple & stable fetch for stocks only"""
        print(f"📥 Fetching data for {ticker}...")
        try:
            to_date = datetime.now().strftime("%Y-%m-%d")
            from_date = (datetime.now().replace(year=datetime.now().year - 2)).strftime("%Y-%m-%d")
            
            aggs = self.polygon.get_aggs(ticker, multiplier, timespan, from_date, to_date, limit=50000)
            
            if aggs:
                df = pd.DataFrame([a.__dict__ for a in aggs])
                print(f"   → Polygon returned {len(df)} rows")
                
                # Fix Polygon short column names
                column_map = {'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}
                for old, new in column_map.items():
                    if old in df.columns:
                        df[new] = df[old]
                        if old != new:
                            df.drop(columns=[old], inplace=True, errors='ignore')
                
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    print(f"✅ Fetched {len(df)} bars for {ticker}")
                    return df
        except Exception as e:
            print(f"   ⚠️ Polygon error: {e}")
        
        # Very safe fallback
        print(f"   🔄 yfinance fallback for {ticker}")
        try:
            df = yf.download(ticker, period="2y", interval="1d", progress=False)
            if not df.empty:
                df = df.reset_index()
                df = df.rename(columns={'Date': 'timestamp'})
                print(f"✅ Fetched {len(df)} bars for {ticker} (yfinance)")
                return df
        except Exception as e:
            print(f"   ❌ yfinance failed: {e}")
        
        print(f"❌ No data for {ticker}")
        return pd.DataFrame()
    
    def get_alpaca_account(self):
        return self.alpaca.get_account()
    
    def place_paper_order(self, symbol: str, qty: int, side: str):
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
            type=OrderType.MARKET
        )
        return self.alpaca.submit_order(order_data)