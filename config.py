import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_BASE = Path(__file__).parent

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
POLYGON_API_KEY   = os.getenv("POLYGON_API_KEY")   # optional — yfinance is the fallback
ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# Absolute path — works regardless of working directory
VAULT_PATH = str(_BASE / "vault")

# Watchlist — reads watchlist.txt if present, else env var, else default
_wl_file = _BASE / "watchlist.txt"
if _wl_file.exists():
    WATCHLIST = [t.strip().upper() for t in _wl_file.read_text().splitlines() if t.strip()]
else:
    WATCHLIST = os.getenv("WATCHLIST", "AAPL,TSLA,NVDA,AMD,GOOGL,MSFT,AMZN,META").split(",")

# ── Risk / backtesting constants ──────────────────────────────────────────────
# Cash baseline used by the backtester — set to match your actual paper account
# equity so Sharpe/drawdown figures are comparable to live performance.
BACKTEST_CASH = float(os.getenv("BACKTEST_CASH", "100000"))

# Circuit breaker: ExecutionAgent halts new entries if the paper account equity
# drops this fraction below the last saved portfolio snapshot.
# Default = 0.10  → halt if equity falls more than 10% from baseline.
CIRCUIT_BREAKER_DRAWDOWN_PCT = float(os.getenv("CIRCUIT_BREAKER_DRAWDOWN_PCT", "0.10"))

# Round-trip commission applied to every backtest trade.
# Alpaca charges $0 commission, so this models realistic half-spread + slippage
# on a limit order for large-cap stocks.  0.002 = ~0.1% per side (buy + sell).
# Increase for smaller/less liquid tickers.  Env-configurable for sensitivity tests.
BACKTEST_COMMISSION = float(os.getenv("BACKTEST_COMMISSION", "0.002"))

# ── API key validation ────────────────────────────────────────────────────────
# Fail fast with a clear message rather than cryptic SDK errors later.
# POLYGON_API_KEY is intentionally optional (yfinance fallback handles missing Polygon).
_required_keys = {
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    "ALPACA_API_KEY":    ALPACA_API_KEY,
    "ALPACA_SECRET_KEY": ALPACA_SECRET_KEY,
}
_missing = [k for k, v in _required_keys.items() if not v]
if _missing:
    raise EnvironmentError(
        f"\n\nMissing required environment variables: {', '.join(_missing)}\n"
        "Create a .env file in the project root with these keys, or set them "
        "as environment variables before running the daily loop.\n"
        "Example .env:\n"
        "  ANTHROPIC_API_KEY=sk-ant-...\n"
        "  ALPACA_API_KEY=PK...\n"
        "  ALPACA_SECRET_KEY=...\n"
    )
