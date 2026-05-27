# streamlit_app.py — Trading Second Brain  (v6)
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import json, re
from pathlib import Path
from datetime import datetime
import sys, subprocess, os

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
VAULT    = BASE_DIR / "vault"
WL_FILE  = BASE_DIR / "watchlist.txt"
sys.path.insert(0, str(BASE_DIR))

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trading Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
  #MainMenu, footer { visibility: hidden; }

  /* ── KPI cards ───────────────────────────────────────────── */
  .kpi-card {
    background: #161b22; border: 1px solid #30363d;
    border-radius: 10px; padding: 18px 14px; text-align: center;
  }
  .kpi-label { font-size:.68em; color:#8892b0; text-transform:uppercase;
               letter-spacing:1.2px; margin-bottom:6px; }
  .kpi-value { font-size:1.55em; font-weight:700; line-height:1.1; }
  .kpi-sub   { font-size:.75em; color:#8892b0; margin-top:4px; }

  /* ── Confidence bar ──────────────────────────────────────── */
  .conf-track { background:#21262d; border-radius:4px; height:6px; margin:6px 0; }
  .conf-fill  { height:6px; border-radius:4px; }

  /* ── Generic card ────────────────────────────────────────── */
  .tb-card { background:#0d1117; border:1px solid #30363d;
             border-radius:10px; padding:16px 20px; margin:6px 0; }

  /* ── Agent cards + animations ────────────────────────────── */
  @keyframes pulse-run {
    0%   { box-shadow:0 0  4px 1px rgba(240,176,48,.35); border-color:#d29922; }
    50%  { box-shadow:0 0 18px 5px rgba(240,176,48,.80); border-color:#f0c040; }
    100% { box-shadow:0 0  4px 1px rgba(240,176,48,.35); border-color:#d29922; }
  }
  .agent-card {
    background:#0d1117; border:1px solid #21262d; border-radius:8px;
    padding:10px 12px; font-size:.85em;
    transition: border-color .3s, box-shadow .3s; margin: 4px 0;
  }
  .agent-idle    { border-color:#21262d !important; }
  .agent-running { animation:pulse-run 1.3s ease-in-out infinite !important; }
  .agent-done    { border-color:#3fb950 !important;
                   box-shadow:0 0 8px rgba(63,185,80,.45) !important; }
  .agent-failed  { border-color:#f85149 !important;
                   box-shadow:0 0 8px rgba(248,81,73,.45) !important; }

  /* ── Trade feed cards ────────────────────────────────────── */
  @keyframes slide-in {
    from { opacity:0; transform:translateY(-8px); }
    to   { opacity:1; transform:translateY(0); }
  }
  .trade-card { border-radius:10px; padding:14px 16px; margin:8px 0;
                border-left:4px solid #30363d; background:#0d1117;
                animation:slide-in .35s ease-out; }
  .trade-buy  { border-left-color:#3fb950; background:#0a1f0f; }
  .trade-sell { border-left-color:#f85149; background:#1f0a0a; }
  .trade-nosig{ border-left-color:#484f58; background:#0d1117; }
  .trade-ticker{ font-size:1.25em; font-weight:700; }
  .trade-meta  { color:#8892b0; font-size:.8em; margin-top:6px; }
  .trade-badge { display:inline-block; padding:2px 8px; border-radius:10px;
                 font-size:.72em; font-weight:700; margin-left:6px; }
  .badge-buy      { background:#0d4429; color:#3fb950; border:1px solid #3fb950; }
  .badge-sell     { background:#4d0f10; color:#f85149; border:1px solid #f85149; }
  .badge-approved { background:#0d4429; color:#3fb950; border:1px solid #3fb950; }
  .badge-rejected { background:#4d0f10; color:#f85149; border:1px solid #f85149; }
  .badge-pending  { background:#3d2800; color:#d29922; border:1px solid #d29922; }

  /* ── Portfolio cards ─────────────────────────────────────── */
  .pos-card { background:#0d1117; border:1px solid #30363d;
              border-radius:10px; padding:14px 16px; margin:6px 0; }
  .pos-gain { border-left:4px solid #3fb950; }
  .pos-loss { border-left:4px solid #f85149; }

  /* ── News cards ──────────────────────────────────────────── */
  .news-card { background:#0d1117; border:1px solid #21262d;
               border-radius:8px; padding:10px 14px; margin:5px 0;
               font-size:.85em; }
  .news-bull { border-left:3px solid #3fb950; }
  .news-bear { border-left:3px solid #f85149; }
  .news-neut { border-left:3px solid #484f58; }

  /* ── Earnings badge ──────────────────────────────────────── */
  .earn-soon { background:#3d2800; color:#d29922; border:1px solid #d29922;
               border-radius:6px; padding:3px 8px; font-size:.75em; margin-left:6px; }
  .earn-far  { background:#161b22; color:#484f58; border:1px solid #30363d;
               border-radius:6px; padding:3px 8px; font-size:.75em; margin-left:6px; }

  /* ── Section headers ─────────────────────────────────────── */
  .section-header {
    font-size:.7em; font-weight:700; color:#8892b0;
    text-transform:uppercase; letter-spacing:1.5px;
    border-bottom:1px solid #21262d; padding-bottom:6px; margin-bottom:10px;
  }

  /* ── Trading / execution tab ──────────────────────────────── */
  .order-card { background:#0d1117; border:1px solid #30363d;
                border-radius:10px; padding:14px 16px; margin:6px 0; }
  .order-open     { border-left:4px solid #d29922; }
  .order-filled   { border-left:4px solid #3fb950; }
  .order-cancelled{ border-left:4px solid #484f58; }
  .exec-log-card  { background:#0d1117; border:1px solid #21262d; border-radius:8px;
                    padding:10px 14px; margin:5px 0; font-size:.85em; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  WATCHLIST
# ══════════════════════════════════════════════════════════════════════════════
def load_watchlist() -> list[str]:
    if WL_FILE.exists():
        return [t.strip().upper() for t in WL_FILE.read_text().splitlines() if t.strip()]
    return ["AAPL","TSLA","NVDA","AMD","GOOGL","MSFT","AMZN","META"]

def save_watchlist(tickers: list[str]):
    WL_FILE.write_text("\n".join(t.upper() for t in tickers) + "\n")

WATCHLIST = load_watchlist()

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
AGENTS = [
    ("DataScout",        "📡", "OHLCV + RSI/MACD/BB",         "haiku"),
    ("NewsScout",        "📰", "Real news headlines",          "haiku"),
    ("SectorScout",      "🏭", "11-sector rotation",           "haiku"),
    ("RegimeClassifier", "📈", "Bull/Bear/Range/HiVol",        "haiku"),
    ("VolatilityAgent",  "🌡️", "VIX + HV20/60 regime",         "haiku"),
    ("SentimentAgent",   "💬", "News & options sentiment",     "haiku"),
    ("MarketAnalyst",    "📊", "SPY/QQQ/IWM daily note",       "haiku"),
    ("Optimizer",        "🔬", "5-strategy walk-forward",      "haiku"),
    ("Strategist",       "📐", "Strategy refinement",          "sonnet"),
    ("MetaEvaluator",    "🎯", "Scores & ranks strategies",    "sonnet"),
    ("Critic",           "🔍", "Finds flaws & risks",          "sonnet"),
    ("SignalGenerator",  "⚡", "High-conviction signals",      "sonnet"),
    ("RiskGuardian",     "🛡️", "Strict risk gating",           "sonnet"),
    ("ExecutionAgent",   "🚀", "Alpaca paper order router",    "haiku"),
    ("PnLTracker",       "💰", "P&L + portfolio snapshot",     "haiku"),
]

MODEL_BADGE = {
    "haiku":  ("<span style='font-size:.65em;background:#1a2a1a;color:#3fb950;"
               "border:1px solid #3fb950;border-radius:4px;padding:1px 5px'>HAIKU</span>"),
    "sonnet": ("<span style='font-size:.65em;background:#1a1a2a;color:#58a6ff;"
               "border:1px solid #58a6ff;border-radius:4px;padding:1px 5px'>SONNET</span>"),
}

DARK = "#0d1117"
PLOT_LAYOUT = dict(
    paper_bgcolor=DARK, plot_bgcolor=DARK,
    font=dict(color="#cdd9e5"),
    margin=dict(l=10, r=20, t=50, b=20),
    xaxis=dict(gridcolor="#21262d", zerolinecolor="#30363d"),
    yaxis=dict(gridcolor="#21262d"),
)

def _pl(**overrides) -> dict:
    """Merge PLOT_LAYOUT with per-chart overrides — no duplicate-key errors."""
    return {k: v for k, v in PLOT_LAYOUT.items() if k not in overrides} | overrides

SECTOR_COLORS = {  # Risk-On → bright, Defensive → muted
    "Technology":              "#58a6ff",
    "Financials":              "#3fb950",
    "Energy":                  "#d29922",
    "Healthcare":              "#bc8cff",
    "Consumer Staples":        "#8892b0",
    "Consumer Discretionary":  "#f0883e",
    "Industrials":             "#56d364",
    "Materials":               "#e3b341",
    "Utilities":               "#484f58",
    "Real Estate":             "#6e7681",
    "Communication":           "#388bfd",
}

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS — vault
# ══════════════════════════════════════════════════════════════════════════════
def safe_read(path: Path) -> str:
    try:    return path.read_text(encoding="utf-8", errors="replace")
    except: return ""

def latest(pattern: str) -> Path | None:
    fs = sorted(VAULT.glob(pattern), reverse=True)
    return fs[0] if fs else None

def latest_text(pattern: str) -> str:
    f = latest(pattern); return safe_read(f) if f else ""

def show_md(pattern: str, empty="No data yet — run the daily loop"):
    f = latest(pattern)
    if f: st.caption(f"📄 `{f.name}`"); st.markdown(safe_read(f))
    else: st.info(empty)

def vault_stats():
    if not VAULT.exists(): return 0, "—"
    files = list(VAULT.rglob("*.md"))
    if not files: return 0, "—"
    newest = max(files, key=lambda f: f.stat().st_mtime)
    age    = datetime.now() - datetime.fromtimestamp(newest.stat().st_mtime)
    m      = int(age.total_seconds() // 60)
    return len(files), (f"{m}m ago" if m < 60 else f"{m//60}h ago")

def load_sector_json() -> list[dict]:
    p = VAULT / "00-Daily" / "sectors_latest.json"
    if p.exists():
        try: return json.loads(p.read_text())
        except: return []
    return []

def load_portfolio_json() -> dict:
    p = VAULT / "09-Portfolio" / "positions.json"
    if p.exists():
        try: return json.loads(p.read_text())
        except: return {}
    return {}

def load_volatility_json() -> dict:
    p = VAULT / "00-Daily" / "volatility_latest.json"
    if p.exists():
        try: return json.loads(p.read_text())
        except: return {}
    return {}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_earnings_calendar(tickers: tuple) -> list[dict]:
    """Fetch next earnings date for each ticker (cached 1h)."""
    try:
        sys.path.insert(0, str(BASE_DIR))
        from src.data_fetcher import DataFetcher  # noqa: PLC0415
        fetcher = DataFetcher()
        rows = []
        for ticker in tickers:
            try:
                date_str = fetcher.get_earnings_date(ticker)
                if date_str:
                    try:
                        dt        = datetime.strptime(date_str[:10], "%Y-%m-%d")
                        days_away = (dt - datetime.now()).days
                    except Exception:
                        days_away = 9999
                    rows.append({"Ticker": ticker, "Earnings Date": date_str[:10],
                                 "Days Away": days_away})
            except Exception:
                pass
        return sorted(rows, key=lambda x: x["Days Away"])
    except Exception:
        return []

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS — parsers
# ══════════════════════════════════════════════════════════════════════════════
def _num(s: str) -> float | None:
    m = re.search(r'[+-]?\d+\.?\d*', s.strip())
    return float(m.group()) if m else None

def parse_regime(text: str) -> dict:
    d = {"label":"Unknown","confidence":0,"volatility":"—","bias":"—"}
    if not text: return d
    flat = text.replace("\n","│")
    for pat, key in [(r'REGIME:\s*(.+?)(?:│|\|)',"label"),
                     (r'VOLATILITY:\s*(.+?)(?:│|\|)',"volatility"),
                     (r'BIAS:\s*(.+?)(?:│|\|)',"bias")]:
        m = re.search(pat, flat)
        if m: d[key] = m.group(1).strip().rstrip("│|")
    m = re.search(r'CONFIDENCE:\s*(\d+)%', text)
    if m: d["confidence"] = int(m.group(1))
    return d

def parse_sentiment(text: str) -> dict:
    d = {"label":"Unknown","confidence":0,"blended":0,"tickers":{}}
    if not text: return d
    flat = text.replace("\n","│")
    m = re.search(r'OVERALL MARKET SENTIMENT:\s*([\w\s-]+?)(?:│|\|)', flat)
    if m: d["label"] = m.group(1).strip()
    m = re.search(r'CONFIDENCE:\s*(\d+)%', text)
    if m: d["confidence"] = int(m.group(1))
    m = re.search(r'BLENDED.*?[+]?(\d+\.?\d*)%', text, re.IGNORECASE)
    if m: d["blended"] = float(m.group(1))
    for ticker in WATCHLIST:
        m = re.search(rf'{ticker}.*?[+]?(\d+\.?\d*)%\s*bullish', text, re.IGNORECASE)
        if m: d["tickers"][ticker] = float(m.group(1))
    return d

def parse_rankings(text: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line: continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 6: continue
        rank_raw = re.sub(r'[^\d]','',parts[0])
        if not rank_raw: continue
        try:
            sharpe = _num(parts[2])
            if sharpe is None: continue
            rows.append({
                "Rank":     int(rank_raw),
                "Strategy": re.sub(r'[*_`🥇🥈🥉]','',parts[1]).strip(),
                "Sharpe":   sharpe,
                "Return":   _num(parts[3]) or 0,
                "Max DD":   _num(parts[4]) or 0,
                "Win Rate": _num(parts[5]) or 0,
                "Calmar":   _num(parts[6]) if len(parts) > 6 else 0,
                "Tier":     parts[7].strip() if len(parts) > 7 else "—",
            })
        except: continue
    return pd.DataFrame(rows) if rows else pd.DataFrame()

ALL_STRATEGIES = ["SMA_Crossover","RSI_MeanReversion","MACD_Momentum","BB_Reversion","EMA_Momentum"]

def parse_backtest_files() -> pd.DataFrame:
    rows = []
    for strat in ALL_STRATEGIES:
        for t in WATCHLIST:
            files = sorted(VAULT.glob(f"04-Backtests/{t}_{strat}_WF*.md"), reverse=True)
            if not files: continue
            txt = safe_read(files[0])
            ret = re.search(r'\*\*Return\*\*[:\s]+([+-]?\d+\.?\d*)%', txt)
            dd  = re.search(r'\*\*Max.?Drawdown\*\*[:\s]+([+-]?\d+\.?\d*)%', txt)
            sh  = re.search(r'\*\*Sharpe\*\*[:\s]+([+-]?\d+\.?\d*)(?!\/A)', txt)
            wr  = re.search(r'\*\*Win.?Rate\*\*[:\s]+(\d+\.?\d*)%', txt)
            cal = re.search(r'\*\*Calmar\*\*[:\s]+([+-]?\d+\.?\d*)', txt)
            if ret or dd:
                rows.append({
                    "Ticker":   t,  "Strategy": strat,
                    "Return":   float(ret.group(1)) if ret else 0,
                    "Max DD":   float(dd.group(1))  if dd  else 0,
                    "Sharpe":   float(sh.group(1))  if sh  else 0,
                    "Win Rate": float(wr.group(1))  if wr  else 0,
                    "Calmar":   float(cal.group(1)) if cal else 0,
                })
    return pd.DataFrame(rows)

def parse_trade_signals(text: str) -> list[dict]:
    if not text: return []
    signals, seen = [], set()
    for ticker in WATCHLIST:
        pat = re.search(rf'(?:###?\s*)?{ticker}[\s\S]{{0,700}}?(?=###|##|\Z)',
                        text, re.IGNORECASE)
        if not pat or ticker in seen: continue
        seen.add(ticker)
        chunk = pat.group(0)
        direction = "NO SIGNAL"
        if re.search(r'\bBUY\b', chunk):    direction = "BUY"
        elif re.search(r'\bSELL\b', chunk): direction = "SELL"
        if re.search(r'NO\s*SIGNAL', chunk, re.IGNORECASE): direction = "NO SIGNAL"
        cm   = re.search(r'(\d{2,3})\s*%\s*(?:confidence)?', chunk, re.IGNORECASE)
        conf = int(cm.group(1)) if cm else None
        def _price(label):
            # Wrap label in (?:...) so alternation like 'entry|enter' doesn't
            # short-circuit before the capture group, leaving m.group(1) as None
            m = re.search(rf'(?:{label})[:\s|]+\$?([\d,]+\.?\d*)', chunk, re.IGNORECASE)
            if not m or not m.group(1):
                return None
            try:
                return f"${float(m.group(1).replace(',', '')):.2f}"
            except (ValueError, TypeError):
                return None
        entry, stop, target = _price(r'entry|enter'), _price(r'stop'), _price(r'target')
        rm = re.search(r'[Rr][\s:]*[Rr][\s:]*([\d.]+)\s*[:/]\s*([\d.]+)', chunk)
        rr = f"{rm.group(1)}:{rm.group(2)}" if rm else None
        signals.append(dict(ticker=ticker, direction=direction,
                            confidence=conf, entry=entry, stop=stop, target=target, rr=rr))
    return signals

def parse_risk_verdicts(text: str) -> dict[str, str]:
    if not text: return {}
    verdicts = {}
    for ticker in WATCHLIST:
        pat = re.search(rf'(?:###?\s*)?{ticker}[\s\S]{{0,400}}?(?=###|##|\Z)',
                        text, re.IGNORECASE)
        if not pat: continue
        chunk = pat.group(0)
        if re.search(r'\bAPPROVE[D]?\b', chunk, re.IGNORECASE):    verdicts[ticker] = "APPROVED"
        elif re.search(r'\bREJECT(?:ED)?\b', chunk, re.IGNORECASE): verdicts[ticker] = "REJECTED"
        else:                                                          verdicts[ticker] = "PENDING"
    return verdicts

# ══════════════════════════════════════════════════════════════════════════════
#  CHART FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
def technical_chart(ticker: str, chart_type: str = "candlestick"):
    csv_path = VAULT / "01-Assets" / "Stocks" / f"{ticker}.csv"
    if not csv_path.exists():
        st.info(f"No CSV data for {ticker} yet — run the daily loop")
        return
    try:
        df = pd.read_csv(str(csv_path))
    except Exception as e:
        st.warning(f"Could not read {ticker}.csv: {e}")
        return

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])
    df = df.tail(120)
    if df.empty: st.info("Insufficient price history"); return

    has_rsi   = "rsi"  in df.columns and df["rsi"].notna().any()
    has_macd  = "macd" in df.columns and df["macd"].notna().any()
    has_ohlcv = all(c in df.columns for c in ["open","high","low","close","volume"])

    rows    = 2 + int(has_rsi) + int(has_macd)
    heights = ([0.50, 0.10, 0.22, 0.18] if rows == 4 else
               [0.55, 0.12, 0.33]       if rows == 3 else
               [0.65, 0.15, 0.20])[:rows]
    titles  = [f"{ticker} — {chart_type.title()}", "Volume"]
    if has_rsi:  titles.append("RSI(14)")
    if has_macd: titles.append("MACD(12/26/9)")

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        row_heights=heights, vertical_spacing=0.03,
                        subplot_titles=titles)
    x = df["timestamp"] if "timestamp" in df.columns else df.index

    # ── Row 1: Price (candlestick or line) ────────────────────────────────────
    if chart_type == "candlestick" and has_ohlcv:
        fig.add_trace(go.Candlestick(
            x=x, open=df["open"], high=df["high"], low=df["low"], close=df["close"],
            name="OHLC",
            increasing=dict(line_color="#3fb950", fillcolor="#0a1f0f"),
            decreasing=dict(line_color="#f85149", fillcolor="#1f0a0a"),
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=x, y=df["close"], name="Close",
                                 line=dict(color="#58a6ff", width=2)), row=1, col=1)

    if "sma50"  in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df["sma50"],  name="SMA50",
                                 line=dict(color="#d29922", width=1, dash="dot")), row=1, col=1)
    if "sma200" in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df["sma200"], name="SMA200",
                                 line=dict(color="#f85149", width=1, dash="dot")), row=1, col=1)
    if "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(x=x, y=df["bb_upper"], name="BB Upper",
                                 line=dict(color="#30363d", width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["bb_lower"], name="BB Lower",
                                 line=dict(color="#30363d", width=1),
                                 fill="tonexty", fillcolor="rgba(88,166,255,0.05)"), row=1, col=1)

    # ── Row 2: Volume ─────────────────────────────────────────────────────────
    if "volume" in df.columns:
        vol_colors = []
        for i in range(len(df)):
            c  = float(df["close"].iloc[i])
            p  = float(df["close"].iloc[i-1]) if i > 0 else c
            vol_colors.append("#3fb950" if c >= p else "#f85149")
        fig.add_trace(go.Bar(x=x, y=df["volume"], name="Volume",
                             marker_color=vol_colors, opacity=0.6), row=2, col=1)

    # ── Row 3: RSI ────────────────────────────────────────────────────────────
    if has_rsi:
        rr = 2 + 1
        fig.add_trace(go.Scatter(x=x, y=df["rsi"], name="RSI",
                                 line=dict(color="#bc8cff", width=1.5)), row=rr, col=1)
        fig.add_hline(y=70, line_color="#f85149", line_dash="dash", line_width=1, row=rr, col=1)
        fig.add_hline(y=30, line_color="#3fb950", line_dash="dash", line_width=1, row=rr, col=1)
        fig.add_hline(y=50, line_color="#484f58", line_dash="dot",  line_width=1, row=rr, col=1)

    # ── Row 4: MACD ───────────────────────────────────────────────────────────
    if has_macd:
        mr = 2 + int(has_rsi) + 1
        hc = ["#3fb950" if v >= 0 else "#f85149" for v in df["macd_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=x, y=df["macd_hist"], name="Histogram",
                             marker_color=hc), row=mr, col=1)
        fig.add_trace(go.Scatter(x=x, y=df["macd"], name="MACD",
                                 line=dict(color="#58a6ff", width=1.2)), row=mr, col=1)
        if "macd_signal" in df.columns:
            fig.add_trace(go.Scatter(x=x, y=df["macd_signal"], name="Signal",
                                     line=dict(color="#d29922", width=1.2)), row=mr, col=1)

    fig.update_layout(
        height=560, showlegend=True,
        legend=dict(bgcolor=DARK, bordercolor="#30363d", font=dict(size=10),
                    orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        paper_bgcolor=DARK, plot_bgcolor=DARK, font=dict(color="#cdd9e5"),
        margin=dict(l=10, r=20, t=50, b=20),
        xaxis_rangeslider_visible=False,
    )
    for i in range(1, rows+1):
        fig.update_layout(**{f"xaxis{i if i>1 else ''}": dict(gridcolor="#21262d")})
        fig.update_layout(**{f"yaxis{i if i>1 else ''}": dict(gridcolor="#21262d")})
    if has_rsi:
        rsi_ax = f"yaxis{2+1}"
        fig.update_layout(**{rsi_ax: dict(gridcolor="#21262d", range=[0,100])})

    st.plotly_chart(fig, width='stretch')


def correlation_heatmap():
    """Load all ticker CSVs → compute 60d close correlation → Plotly heatmap."""
    closes = {}
    for ticker in WATCHLIST:
        csv_path = VAULT / "01-Assets" / "Stocks" / f"{ticker}.csv"
        if not csv_path.exists(): continue
        try:
            df = pd.read_csv(str(csv_path))
            if "close" in df.columns and len(df) >= 20:
                closes[ticker] = df["close"].tail(60).values
        except: continue

    if len(closes) < 2:
        st.info("Need at least 2 tickers with data — run the daily loop")
        return

    # Align lengths
    min_len = min(len(v) for v in closes.values())
    mat     = pd.DataFrame({k: v[-min_len:] for k, v in closes.items()})
    corr    = mat.corr()
    tickers = list(corr.columns)

    # Color scale: red (negative) → grey (zero) → green (positive)
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=tickers, y=tickers,
        colorscale=[[0,"#f85149"],[0.5,"#21262d"],[1,"#3fb950"]],
        zmin=-1, zmax=1, zmid=0,
        text=[[f"{v:.2f}" for v in row] for row in corr.values],
        texttemplate="%{text}",
        textfont=dict(size=11, color="#cdd9e5"),
        hoverongaps=False,
        hovertemplate="<b>%{x} vs %{y}</b><br>Correlation: %{z:.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="60-Day Close Price Correlation Matrix",
        height=420 + max(0, (len(tickers)-6)*25),
        **{k:v for k,v in PLOT_LAYOUT.items() if k not in ("xaxis","yaxis")},
        xaxis=dict(side="bottom", gridcolor="#21262d"),
        yaxis=dict(autorange="reversed", gridcolor="#21262d"),
    )
    st.plotly_chart(fig, width='stretch')


def sector_heatmap(sector_data: list[dict]):
    if not sector_data: return
    df = pd.DataFrame(sector_data)

    # Sort by 5D% performance
    df = df.sort_values("5D%", ascending=False)

    # Heatmap: rows=sectors, cols=timeframes
    periods = ["1D%","5D%","21D%","63D%"]
    z_vals  = df[periods].values.tolist()
    y_labs  = [f"{r['ETF']} ({r['Sector'][:12]})" for _, r in df.iterrows()]

    max_abs = max(abs(v) for row in z_vals for v in row) or 5
    text_vals = [[f"{v:+.1f}%" for v in row] for row in z_vals]

    fig = go.Figure(go.Heatmap(
        z=z_vals, x=["1 Day","5 Day","21 Day","63 Day"], y=y_labs,
        colorscale=[[0,"#4d0f10"],[0.5,"#21262d"],[1,"#0d4429"]],
        zmin=-max_abs, zmax=max_abs, zmid=0,
        text=text_vals, texttemplate="%{text}", textfont=dict(size=11),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z:+.2f}%<extra></extra>",
    ))
    fig.update_layout(
        title="Sector Performance Heatmap",
        height=400,
        **{k:v for k,v in PLOT_LAYOUT.items() if k not in ("xaxis","yaxis")},
        xaxis=dict(side="top", gridcolor="#21262d"),
        yaxis=dict(autorange="reversed", gridcolor="#21262d"),
    )
    st.plotly_chart(fig, width='stretch')


def sector_bar(sector_data: list[dict], period: str = "5D%"):
    if not sector_data: return
    df = pd.DataFrame(sector_data).sort_values(period, ascending=True)
    colors = ["#3fb950" if v >= 0 else "#f85149" for v in df[period]]
    fig = go.Figure(go.Bar(
        x=df[period], y=[f"{r['ETF']} {r['Sector'][:10]}" for _, r in df.iterrows()],
        orientation="h", marker_color=colors,
        text=[f"{v:+.2f}%" for v in df[period]], textposition="outside",
        hovertemplate="<b>%{y}</b><br>" + period + ": %{x:+.2f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#484f58", line_width=1)
    fig.update_layout(title=f"Sector Returns — {period}", height=380,
                      **_pl(yaxis=dict(gridcolor="#21262d")))
    st.plotly_chart(fig, width='stretch')


# ── Trade helpers ─────────────────────────────────────────────────────────────
def trade_card_html(sig: dict, verdict: str | None = None) -> str:
    d        = sig["direction"]
    card_cls = {"BUY":"trade-buy","SELL":"trade-sell"}.get(d,"trade-nosig")
    dir_badge = (f"<span class='trade-badge badge-buy'>BUY</span>"   if d == "BUY"  else
                 f"<span class='trade-badge badge-sell'>SELL</span>" if d == "SELL" else "")
    v_cls    = ("badge-approved" if verdict=="APPROVED" else
                "badge-rejected" if verdict=="REJECTED" else "badge-pending")
    vhtml    = f"<span class='trade-badge {v_cls}'>{verdict}</span>" if verdict else ""
    conf     = f"<b>{sig['confidence']}%</b> conf" if sig.get("confidence") else ""
    rr       = f" &nbsp;·&nbsp; R:R <b>{sig['rr']}</b>" if sig.get("rr") else ""
    levels   = " &nbsp;·&nbsp; ".join(filter(None, [
        f"Entry <b>{sig['entry']}</b>"   if sig.get("entry")  else None,
        f"Stop <b>{sig['stop']}</b>"     if sig.get("stop")   else None,
        f"Target <b>{sig['target']}</b>" if sig.get("target") else None,
    ]))
    return f"""
    <div class='trade-card {card_cls}'>
      <div><span class='trade-ticker'>{sig['ticker']}</span>{dir_badge}{vhtml}</div>
      <div class='trade-meta'>{conf}{rr}{"<br>"+levels if levels else ""}</div>
    </div>"""

def render_trade_feed(signals, verdicts, placeholder=None):
    active = [s for s in signals if s["direction"] != "NO SIGNAL"]
    if not active:
        html = "<div style='color:#484f58;padding:12px'>No active signals yet</div>"
    else:
        html = "".join(trade_card_html(s, verdicts.get(s["ticker"])) for s in active)
        no_sig = [s["ticker"] for s in signals if s["direction"] == "NO SIGNAL"]
        if no_sig:
            html += (f"<div style='color:#484f58;font-size:.8em;padding:6px 4px'>"
                     f"No signal: {', '.join(no_sig)}</div>")
    if placeholder: placeholder.markdown(html, unsafe_allow_html=True)
    else:           st.markdown(html, unsafe_allow_html=True)


def signals_to_csv(signals: list[dict], verdicts: dict) -> str:
    rows = []
    for s in signals:
        rows.append({
            "Date":      datetime.now().strftime("%Y-%m-%d"),
            "Ticker":    s["ticker"],
            "Direction": s["direction"],
            "Confidence":s.get("confidence",""),
            "Entry":     s.get("entry",""),
            "Stop":      s.get("stop",""),
            "Target":    s.get("target",""),
            "RR":        s.get("rr",""),
            "Verdict":   verdicts.get(s["ticker"],""),
        })
    return pd.DataFrame(rows).to_csv(index=False)


# ── Agent grid ────────────────────────────────────────────────────────────────
def _build_agent_grid_html():
    st_ = st.session_state.agent_status
    left_html = right_html = ""
    for i, (name, icon, desc, tier) in enumerate(AGENTS):
        info   = st_.get(name, {})
        lbl    = info.get("label", "idle")
        a_icon = info.get("icon",  "⚪")
        if "running" in lbl:  css, tc = "agent-running", "#d29922"
        elif lbl == "done":   css, tc = "agent-done",    "#3fb950"
        elif lbl == "FAILED": css, tc = "agent-failed",  "#f85149"
        else:                 css, tc = "agent-idle",    "#484f58"
        stag = ("" if lbl == "idle" else
                f"<span style='float:right;font-size:.7em;color:{tc};margin-top:2px'>{lbl}</span>")
        card = (f"<div class='agent-card {css}'>"
                f"  <span style='font-size:1.05em'>{icon}</span>"
                f"  <strong style='color:#cdd9e5'> {name}</strong>"
                f"  <span style='float:right;font-size:1.1em'>{a_icon}</span>"
                f"  {stag}"
                f"  <br><span style='color:#8892b0;font-size:.8em'>{desc}</span>"
                f"  &nbsp;{MODEL_BADGE[tier]}"
                f"</div>")
        if i % 2 == 0: left_html += card
        else:          right_html += card
    return left_html, right_html


def accent(label: str) -> str:
    l = label.lower()
    if "bull" in l:                   return "#3fb950"
    if "bear" in l:                   return "#f85149"
    if "high" in l and "vol" in l:    return "#bc8cff"
    if "rang" in l or "neutral" in l: return "#d29922"
    return "#58a6ff"

def kpi(col, label, value, sub, color="#cdd9e5", border=None):
    col.markdown(
        f"<div class='kpi-card' style='{'border-color:'+border if border else ''}'>"
        f"<div class='kpi-label'>{label}</div>"
        f"<div class='kpi-value' style='color:{color}'>{value}</div>"
        f"<div class='kpi-sub'>{sub}</div></div>",
        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for k, v in [("agent_log",[]),("agent_status",{}),("loop_running",False),
             ("live_signals",[]),("live_verdicts",{})]:
    if k not in st.session_state: st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🧠 Trading Brain")
    n_notes, last_w = vault_stats()
    c1, c2 = st.columns(2)
    c1.metric("📁 Notes", n_notes)
    c2.metric("🕐 Updated", last_w)
    st.divider()

    if st.button("🔄 Refresh Dashboard", width='stretch'):
        WATCHLIST[:] = load_watchlist()
        st.rerun()

    run_btn = st.button(
        "🚀 Run Daily Loop", type="primary", width='stretch',
        disabled=st.session_state.loop_running,
        help="13 agents: parallel data fetch → news → sectors → regime → signals → risk → P&L",
    )
    if run_btn:
        st.session_state.update(
            loop_running=True, agent_log=[],
            agent_status={}, live_signals=[], live_verdicts={},
        )
        st.rerun()

    # ── Watchlist editor ──────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📋 Watchlist")
    wl_text = st.text_area("One ticker per line", value="\n".join(WATCHLIST),
                            height=160, label_visibility="collapsed")
    if st.button("💾 Save Watchlist", width='stretch'):
        new_wl = [t.strip().upper() for t in wl_text.splitlines() if t.strip()]
        if new_wl:
            save_watchlist(new_wl); WATCHLIST[:] = new_wl
            st.success(f"Saved {len(new_wl)} tickers"); st.rerun()
        else:
            st.error("Watchlist can't be empty")

    # ── Agent status compact ──────────────────────────────────────────────────
    if st.session_state.agent_status:
        st.divider(); st.markdown("### 🤖 Status")
        for name, info in st.session_state.agent_status.items():
            c = ("#3fb950" if info["label"]=="done" else
                 "#f85149" if info["label"]=="FAILED" else "#d29922")
            st.markdown(
                f"{info['icon']} <span style='color:{c}'><b>{name[:18]}</b></span>"
                f" <span style='color:#484f58;font-size:.8em'>{info['label']}</span>",
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  LIVE RUNNER
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.loop_running:
    st.markdown("## 🔴 Live Run")
    hc1, hc2 = st.columns([1,1])
    hc1.markdown("<div class='section-header'>🤖 AGENT NETWORK</div>", unsafe_allow_html=True)
    hc2.markdown("<div class='section-header'>📊 TRADE FEED</div>",    unsafe_allow_html=True)

    agent_col, feed_col = st.columns([1,1])
    with agent_col:
        ag_c1, ag_c2   = st.columns(2)
        agent_left_ph  = ag_c1.empty()
        agent_right_ph = ag_c2.empty()
    with feed_col:
        feed_ph = st.empty()

    st.markdown("<div class='section-header'>📋 RAW LOG</div>", unsafe_allow_html=True)
    log_ph = st.empty()

    def _render_agents():
        lh, rh = _build_agent_grid_html()
        agent_left_ph.markdown(lh,  unsafe_allow_html=True)
        agent_right_ph.markdown(rh, unsafe_allow_html=True)

    def _render_feed():
        render_trade_feed(st.session_state.live_signals,
                          st.session_state.live_verdicts, feed_ph)

    _render_agents(); _render_feed()

    env  = {**os.environ, "PYTHONUNBUFFERED":"1"}
    proc = subprocess.Popen(
        [sys.executable, "-u", str(BASE_DIR / "run_daily_loop.py")],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        cwd=str(BASE_DIR), env=env,
    )
    for raw in proc.stdout:
        line = raw.rstrip()
        st.session_state.agent_log.append(line)
        status_changed, completed_agent = False, None

        if line.startswith("▶  "):
            n = line[3:]
            st.session_state.agent_status[n] = {"icon":"🟡","label":"running…"}
            status_changed = True
        elif line.startswith("✅ "):
            n = line[3:].split(" — done")[0]
            if n in st.session_state.agent_status:
                st.session_state.agent_status[n] = {"icon":"✅","label":"done"}
                status_changed = True; completed_agent = n
        elif line.startswith("❌ "):
            n = line[3:].split(" — FAILED")[0]
            if n in st.session_state.agent_status:
                st.session_state.agent_status[n] = {"icon":"❌","label":"FAILED"}
                status_changed = True

        if status_changed: _render_agents()
        if completed_agent and "SignalGenerator" in completed_agent:
            st.session_state.live_signals = parse_trade_signals(
                latest_text("03-Trade-Journal/signals_*.md"))
            _render_feed()
        if completed_agent and "RiskGuardian" in completed_agent:
            st.session_state.live_verdicts = parse_risk_verdicts(
                latest_text("06-Playbooks/RISK_SWEEP_*.md"))
            _render_feed()

        log_ph.code("\n".join(st.session_state.agent_log[-60:]), language=None)

    proc.wait()
    st.session_state.loop_running = False
    if proc.returncode == 0: st.success("✅ All agents finished — refreshing…")
    else:                    st.warning(f"⚠️  Finished with errors (exit {proc.returncode})")
    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  LOAD VAULT DATA
# ══════════════════════════════════════════════════════════════════════════════
regime_txt    = latest_text("00-Daily/regime_*.md")
sentiment_txt = latest_text("00-Daily/sentiment_*.md")
rankings_txt  = latest_text("06-Playbooks/STRATEGY_RANKING_*.md")
signal_txt    = latest_text("03-Trade-Journal/signals_*.md")
risk_txt      = latest_text("06-Playbooks/RISK_SWEEP_*.md")

regime    = parse_regime(regime_txt)
sentiment = parse_sentiment(sentiment_txt)
rankings  = parse_rankings(rankings_txt)
bt_df     = parse_backtest_files()
signals   = parse_trade_signals(signal_txt)
verdicts  = parse_risk_verdicts(risk_txt)
sectors    = load_sector_json()
portfolio  = load_portfolio_json()
volatility = load_volatility_json()
rc = accent(regime["label"])
sc = accent(sentiment["label"])

# ══════════════════════════════════════════════════════════════════════════════
#  HERO KPI BAR
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 🧠 Trading Second Brain")
k1, k2, k3, k4, k5, k6, k7 = st.columns(7)

kpi(k1, "Market Regime",  regime["label"] or "—",
    f"{regime['confidence']}% confidence", rc, rc)
kpi(k2, "Sentiment",      sentiment["label"] or "—",
    f"{sentiment['blended']:.0f}% bullish", sc, sc)

top_strat  = rankings.iloc[0]["Strategy"][:18] if not rankings.empty else "—"
top_sharpe = rankings.iloc[0]["Sharpe"]        if not rankings.empty else 0
sc2 = "#3fb950" if top_sharpe>=1 else "#d29922" if top_sharpe>=0 else "#f85149"
kpi(k3, "Top Strategy", top_strat, f"Sharpe {top_sharpe:.2f}", sc2)

active_sigs = [s for s in signals if s["direction"] != "NO SIGNAL"]
approved    = sum(1 for v in verdicts.values() if v == "APPROVED")
kpi(k4, "Active Signals", str(len(active_sigs)),
    f"{approved} approved", "#3fb950" if approved else "#8892b0")

# Sector rotation KPI
if sectors:
    df_s = pd.DataFrame(sectors).sort_values("5D%", ascending=False)
    top_s = df_s.iloc[0]; bot_s = df_s.iloc[-1]
    kpi(k5, "Sector Rotation",
        top_s["ETF"], f"Leading ↑ {top_s['5D%']:+.1f}% | Lag: {bot_s['ETF']} {bot_s['5D%']:+.1f}%",
        "#3fb950")
else:
    kpi(k5, "Sectors", "—", "Run loop for data", "#8892b0")

# VIX / Volatility KPI
if volatility and volatility.get("vix"):
    vix_val    = volatility["vix"]
    vix_reg    = volatility.get("vix_regime", "—")
    vix_pct    = volatility.get("vix_percentile_1yr")
    vix_col    = ("#3fb950" if vix_val < 15 else
                  "#d29922" if vix_val < 25 else "#f85149")
    vix_sub    = f"{vix_pct}th pct · {vix_reg.split(' ')[0]}" if vix_pct else vix_reg.split(" ")[0]
    kpi(k6, "VIX", f"{vix_val:.1f}", vix_sub, vix_col, vix_col)
else:
    kpi(k6, "VIX", "—", "Run loop for data", "#8892b0")

n_notes, last_w = vault_stats()
kpi(k7, "Vault Notes", str(n_notes), f"updated {last_w}")

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
T1, T2, T3, T4, T5, T6, T7, T8, T9 = st.tabs([
    "🏠 Command Center",
    "📊 Trade Feed",
    "🏭 Sectors",
    "💼 Portfolio",
    "📡 Signals & Risk",
    "📊 Market Intelligence",
    "📋 Strategy Lab",
    "🔬 Research",
    "🚀 Trading",
])

# ── T1: COMMAND CENTER ────────────────────────────────────────────────────────
with T1:
    left, right = st.columns([3, 2])
    with left:
        st.markdown(f"### 🤖 Agent Network  *({len(AGENTS)} agents)*")
        lh, rh = _build_agent_grid_html()
        t1c1, t1c2 = st.columns(2)
        t1c1.markdown(lh, unsafe_allow_html=True)
        t1c2.markdown(rh, unsafe_allow_html=True)
        if st.session_state.agent_log:
            st.markdown("### 📋 Last Run Log")
            st.code("\n".join(st.session_state.agent_log[-50:]), language=None)

    with right:
        st.markdown("### 📈 Regime Snapshot")
        if regime_txt:
            conf = regime["confidence"]
            st.markdown(f"""
            <div class="tb-card" style="border-color:{rc}">
              <div style="font-size:1.3em;font-weight:700;color:{rc}">{regime['label']}</div>
              <div class="conf-track" style="margin:10px 0 4px">
                <div class="conf-fill" style="width:{conf}%;background:{rc}"></div></div>
              <div style="color:{rc};font-size:.9em;margin-bottom:10px">{conf}% confidence</div>
              <div style="color:#8892b0;font-size:.78em">VOLATILITY</div>
              <div style="color:#cdd9e5;margin-bottom:8px">{regime['volatility']}</div>
              <div style="color:#8892b0;font-size:.78em">BIAS</div>
              <div style="color:#cdd9e5">{regime['bias']}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.info("No regime data — run the daily loop")

        st.markdown("### 💬 Sentiment")
        if sentiment_txt:
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=sentiment["blended"],
                number={"suffix":"%","font":{"color":sc,"size":28}},
                gauge={"axis":{"range":[0,100],"tickcolor":"#8892b0"},
                       "bar":{"color":sc,"thickness":.25},
                       "bgcolor":DARK,"bordercolor":"#30363d",
                       "steps":[{"range":[0,40],"color":"#2a0d0d"},
                                 {"range":[40,60],"color":"#21262d"},
                                 {"range":[60,100],"color":"#0d2a1a"}],
                       "threshold":{"line":{"color":"#cdd9e5","width":2},
                                    "thickness":.75,"value":50}},
                title={"text":f"{sentiment['label']}  •  {sentiment['confidence']}% conf",
                       "font":{"color":"#8892b0","size":11}},
            ))
            fig_g.update_layout(**{**PLOT_LAYOUT,"height":200,"margin":dict(t=40,b=0,l=10,r=10)})
            st.plotly_chart(fig_g, width='stretch')

            tkr_scores = sentiment.get("tickers", {})
            if tkr_scores:
                cols = st.columns(min(4, len(tkr_scores)))
                for ci, (tkr, score) in enumerate(list(tkr_scores.items())[:4]):
                    tc = "#3fb950" if score>=60 else "#d29922" if score>=40 else "#f85149"
                    cols[ci].markdown(f"""
                    <div class='tb-card' style='border-color:{tc};text-align:center;padding:10px'>
                      <div style='color:#8892b0;font-size:.72em'>{tkr}</div>
                      <div style='color:{tc};font-size:1.4em;font-weight:700'>{score:.0f}%</div>
                      <div class='conf-track'>
                        <div class='conf-fill' style='width:{score}%;background:{tc}'></div></div>
                    </div>""", unsafe_allow_html=True)
        else:
            st.info("No sentiment data — run the daily loop")

# ── T2: TRADE FEED ────────────────────────────────────────────────────────────
with T2:
    st.subheader("📊 Trading Live Feed")

    n_active   = len(active_sigs)
    n_approved = sum(1 for v in verdicts.values() if v == "APPROVED")
    n_rejected = sum(1 for v in verdicts.values() if v == "REJECTED")

    sb1, sb2, sb3, sb4 = st.columns(4)
    sb1.metric("Total Signals",     len(signals))
    sb2.metric("Active (BUY/SELL)", n_active)
    sb3.metric("✅ Approved",        n_approved)
    sb4.metric("❌ Rejected",        n_rejected)

    # CSV download
    if signals:
        csv_bytes = signals_to_csv(signals, verdicts).encode()
        st.download_button(
            "📥 Download Signals CSV", data=csv_bytes,
            file_name=f"signals_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    st.divider()
    if not signals:
        st.info("No signals yet — run the daily loop")
    else:
        col_a, col_r = st.columns(2)
        with col_a:
            st.markdown("<div class='section-header'>✅ APPROVED & PENDING</div>",
                        unsafe_allow_html=True)
            showed = False
            for s in signals:
                if s["direction"] == "NO SIGNAL": continue
                v = verdicts.get(s["ticker"])
                if v == "REJECTED": continue
                st.markdown(trade_card_html(s, v), unsafe_allow_html=True); showed = True
            if not showed:
                st.markdown("<div style='color:#484f58;padding:12px'>None yet</div>",
                            unsafe_allow_html=True)
        with col_r:
            st.markdown("<div class='section-header'>❌ REJECTED & NO SIGNAL</div>",
                        unsafe_allow_html=True)
            showed = False
            for s in signals:
                v = verdicts.get(s["ticker"])
                if s["direction"] != "NO SIGNAL" and v != "REJECTED": continue
                st.markdown(trade_card_html(s, v), unsafe_allow_html=True); showed = True
            if not showed:
                st.markdown("<div style='color:#484f58;padding:12px'>None yet</div>",
                            unsafe_allow_html=True)

    if signal_txt or risk_txt:
        st.divider()
        rc1, rc2 = st.columns(2)
        with rc1:
            f = latest("03-Trade-Journal/signals_*.md")
            if f:
                with st.expander(f"📄 Full Signal Report — {f.name}"):
                    st.markdown(signal_txt)
        with rc2:
            f = latest("06-Playbooks/RISK_SWEEP_*.md")
            if f:
                with st.expander(f"🛡️ Full Risk Sweep — {f.name}"):
                    st.markdown(risk_txt)

# ── T3: SECTORS ───────────────────────────────────────────────────────────────
with T3:
    st.subheader("🏭 Sector Rotation")
    if not sectors:
        st.info("No sector data — run the daily loop (SectorScout)")
    else:
        df_sec = pd.DataFrame(sectors)

        # Rotation summary card
        rotation_txt = latest_text("00-Daily/sectors_*.md")
        if rotation_txt:
            signal_line = ""
            m = re.search(r'ROTATION SIGNAL:\s*(.+)', rotation_txt)
            if m:
                sig_label = m.group(1).strip()
                sig_col   = ("#3fb950" if "risk-on" in sig_label.lower() else
                             "#f85149" if "risk-off" in sig_label.lower() else "#d29922")
                signal_line = (f"<div style='font-size:1.2em;font-weight:700;color:{sig_col};"
                               f"margin-bottom:8px'>⚡ {sig_label}</div>")
            st.markdown(f"<div class='tb-card'>{signal_line}</div>", unsafe_allow_html=True)

        # Period selector
        period = st.radio("Timeframe", ["1D%","5D%","21D%","63D%"],
                          horizontal=True, index=1, key="sector_period")

        col_bar, col_heat = st.columns([1,1])
        with col_bar:
            sector_bar(sectors, period)
        with col_heat:
            sector_heatmap(sectors)

        # RSI heatmap (sector health)
        df_rsi = df_sec[df_sec["RSI"].notna()].sort_values("RSI", ascending=False)
        if not df_rsi.empty:
            rsi_colors = ["#f85149" if r>=70 else "#3fb950" if r<=30 else "#58a6ff"
                          for r in df_rsi["RSI"]]
            fig_rsi = go.Figure(go.Bar(
                x=df_rsi["RSI"], y=[f"{r['ETF']}" for _, r in df_rsi.iterrows()],
                orientation="h", marker_color=rsi_colors,
                text=[f"RSI {r:.0f}" for r in df_rsi["RSI"]], textposition="outside",
            ))
            fig_rsi.add_vline(x=70, line_color="#f85149", line_dash="dash", line_width=1)
            fig_rsi.add_vline(x=30, line_color="#3fb950", line_dash="dash", line_width=1)
            fig_rsi.add_vline(x=50, line_color="#484f58", line_dash="dot",  line_width=1)
            fig_rsi.update_layout(title="Sector RSI(14) — Overbought/Oversold", height=320,
                                  **_pl(yaxis=dict(gridcolor="#21262d")))
            st.plotly_chart(fig_rsi, width='stretch')

        # Full sector table
        with st.expander("📊 Full sector table"):
            st.dataframe(df_sec.set_index("ETF"), width='stretch')

        st.divider()
        st.subheader("📄 SectorScout Analysis")
        show_md("00-Daily/sectors_*.md")

# ── T4: PORTFOLIO ─────────────────────────────────────────────────────────────
with T4:
    st.subheader("💼 Alpaca Paper Portfolio")
    if not portfolio:
        st.info("No portfolio snapshot — run the daily loop to fetch positions")
    else:
        try:
            acc  = portfolio.get("account", {})
            ts   = portfolio.get("timestamp", "")[:19].replace("T"," ")
            st.caption(f"Snapshot: {ts}")

            a1, a2, a3, a4 = st.columns(4)
            pv = acc.get("portfolio_value", 0)
            eq = acc.get("equity",          0)
            cs = acc.get("cash",            0)
            bp = acc.get("buying_power",    0)
            kpi(a1, "Portfolio Value", f"${pv:,.2f}", "Paper account",   "#3fb950")
            kpi(a2, "Equity",          f"${eq:,.2f}", "Total equity",    "#58a6ff")
            kpi(a3, "Cash",            f"${cs:,.2f}", "Available cash",  "#cdd9e5")
            kpi(a4, "Buying Power",    f"${bp:,.2f}", "Margin power",    "#d29922")

            positions = portfolio.get("positions", [])
            if not positions:
                st.info("No open positions in paper account")
            else:
                df_pos = pd.DataFrame(positions)
                pl_colors = ["#3fb950" if v>=0 else "#f85149" for v in df_pos["unrealized_pl"]]
                fig_pl = go.Figure()
                fig_pl.add_trace(go.Bar(
                    x=df_pos["symbol"], y=df_pos["unrealized_pl"],
                    marker_color=pl_colors,
                    text=[f"${v:+.2f}" for v in df_pos["unrealized_pl"]],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>P&L: $%{y:+.2f}<extra></extra>",
                ))
                fig_pl.add_hline(y=0, line_color="#30363d", line_width=1)
                fig_pl.update_layout(title="Unrealized P&L by Position",
                                     height=280, **PLOT_LAYOUT)
                st.plotly_chart(fig_pl, width='stretch')

                # Position cards
                cols_per = 3
                for row in range((len(positions)+cols_per-1)//cols_per):
                    rcols = st.columns(cols_per)
                    for ci in range(cols_per):
                        idx = row*cols_per+ci
                        if idx >= len(positions): break
                        p   = positions[idx]
                        cls = "pos-gain" if p["unrealized_pl"]>=0 else "pos-loss"
                        pc  = "#3fb950" if p["unrealized_pl"]>=0 else "#f85149"
                        rcols[ci].markdown(f"""
                        <div class='pos-card {cls}'>
                          <div style='font-size:1.1em;font-weight:700'>{p['symbol']}</div>
                          <div style='color:{pc};font-size:.95em'>
                            ${p['unrealized_pl']:+.2f} ({p['unrealized_plpc']:+.2f}%)
                          </div>
                          <div style='color:#8892b0;font-size:.8em;margin-top:4px'>
                            {p['qty']} shares · Avg ${p['avg_entry']:.2f} · Now ${p['current_price']:.2f}
                          </div>
                          <div style='color:#8892b0;font-size:.8em'>
                            Value: ${p['market_value']:,.2f}
                          </div>
                        </div>""", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Could not load portfolio: {e}")

# ── T5: SIGNALS & RISK ────────────────────────────────────────────────────────
with T5:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📡 Signal Report"); show_md("03-Trade-Journal/signals_*.md")
    with c2:
        st.subheader("🛡️ Risk Sweep");    show_md("06-Playbooks/RISK_SWEEP_*.md")
    st.divider()
    st.subheader("💰 P&L Report");        show_md("06-Playbooks/PNL_REPORT_*.md")

# ── T6: MARKET INTELLIGENCE ───────────────────────────────────────────────────
with T6:
    mi1, mi2 = st.columns(2)
    with mi1:
        st.subheader("📈 Market Regime"); show_md("00-Daily/regime_*.md")
    with mi2:
        st.subheader("💬 Sentiment");     show_md("00-Daily/sentiment_*.md")

    st.divider()

    # ── Volatility section ────────────────────────────────────────────────────
    st.subheader("🌡️ Volatility Dashboard")
    if volatility and volatility.get("vix"):
        vix_val  = volatility["vix"]
        vix_reg  = volatility.get("vix_regime", "Normal")
        vix_pct  = volatility.get("vix_percentile_1yr")
        vix_col  = ("#3fb950" if vix_val < 15 else "#d29922" if vix_val < 25 else "#f85149")

        vc1, vc2, vc3 = st.columns([1, 2, 2])
        with vc1:
            st.markdown(
                f"<div class='tb-card' style='border-color:{vix_col};text-align:center'>"
                f"<div class='kpi-label'>VIX</div>"
                f"<div style='font-size:2.8em;font-weight:700;color:{vix_col}'>{vix_val:.1f}</div>"
                f"<div style='color:{vix_col};font-size:.85em;margin-top:4px'>{vix_reg}</div>"
                + (f"<div class='kpi-sub'>{vix_pct}th pct (1yr)</div>" if vix_pct else "")
                + "</div>", unsafe_allow_html=True)

        tkr_vol = volatility.get("tickers", {})
        if tkr_vol:
            with vc2:
                # HV20 bar chart
                tv_df = pd.DataFrame([
                    {"Ticker": t, "HV20": v["hv20"], "HV60": v["hv60"],
                     "Expanding": v.get("expanding", False)}
                    for t, v in tkr_vol.items()
                ]).sort_values("HV20", ascending=True)
                hv_colors = ["#f0883e" if r["Expanding"] else "#58a6ff"
                             for _, r in tv_df.iterrows()]
                fig_hv = go.Figure()
                fig_hv.add_trace(go.Bar(
                    x=tv_df["HV20"], y=tv_df["Ticker"], orientation="h",
                    name="HV20", marker_color=hv_colors,
                    text=[f"{v:.1f}%" for v in tv_df["HV20"]], textposition="outside",
                    hovertemplate="<b>%{y}</b><br>HV20: %{x:.1f}%<extra></extra>",
                ))
                fig_hv.add_trace(go.Scatter(
                    x=tv_df["HV60"], y=tv_df["Ticker"], mode="markers",
                    name="HV60", marker=dict(color="#8892b0", size=8, symbol="diamond"),
                    hovertemplate="<b>%{y}</b><br>HV60: %{x:.1f}%<extra></extra>",
                ))
                fig_hv.update_layout(
                    title="HV20 (bar) vs HV60 ◆ — 🟠 Expanding  🔵 Contracting",
                    height=max(280, len(tv_df)*35+60), barmode="overlay",
                    legend=dict(bgcolor=DARK, bordercolor="#30363d", font=dict(size=9)),
                    **_pl(yaxis=dict(gridcolor="#21262d")),
                )
                st.plotly_chart(fig_hv, width='stretch')

            with vc3:
                # HV20/HV60 ratio scatter
                tv_df["Ratio"] = tv_df["HV20"] / tv_df["HV60"].replace(0, 1)
                r_colors = ["#f0883e" if r >= 1.05 else "#58a6ff" if r <= 0.95 else "#484f58"
                            for r in tv_df["Ratio"]]
                fig_rt = go.Figure(go.Bar(
                    x=tv_df["Ratio"], y=tv_df["Ticker"], orientation="h",
                    marker_color=r_colors, name="HV20/HV60",
                    text=[f"×{r:.2f}" for r in tv_df["Ratio"]], textposition="outside",
                    hovertemplate="<b>%{y}</b><br>HV20/HV60: %{x:.2f}<extra></extra>",
                ))
                fig_rt.add_vline(x=1, line_color="#484f58", line_dash="dash", line_width=1)
                fig_rt.add_vline(x=1.1, line_color="#f0883e", line_dash="dot", line_width=1)
                fig_rt.update_layout(
                    title="Vol Ratio (>1 = expanding)",
                    height=max(280, len(tv_df)*35+60),
                    **_pl(yaxis=dict(gridcolor="#21262d")),
                )
                st.plotly_chart(fig_rt, width='stretch')

        with st.expander("📄 VolatilityAgent report"):
            show_md("00-Daily/volatility_*.md")
    else:
        st.info("No volatility data — run the daily loop (VolatilityAgent)")

    st.divider()

    # ── Correlation heatmap ───────────────────────────────────────────────────
    st.subheader("🔗 Correlation Matrix  *(60-day)*")
    correlation_heatmap()

    st.divider()

    # ── Earnings calendar ─────────────────────────────────────────────────────
    st.subheader("📅 Earnings Calendar")
    earn_col1, earn_col2 = st.columns([3, 1])
    with earn_col2:
        fetch_earn_btn = st.button("🔄 Fetch Earnings Dates", width='stretch',
                                   help="Pulls next earnings dates from yfinance (cached 1h)")
    if fetch_earn_btn or "earnings_rows" not in st.session_state:
        with st.spinner("Fetching earnings dates…"):
            st.session_state["earnings_rows"] = fetch_earnings_calendar(tuple(WATCHLIST))

    earn_rows = st.session_state.get("earnings_rows", [])
    if earn_rows:
        with earn_col1:
            for r in earn_rows:
                days   = r["Days Away"]
                urgency = (f"<span class='earn-soon'>⚡ {days}d</span>" if 0 <= days <= 14 else
                           f"<span class='earn-far'>{days}d</span>"    if days >= 0 else
                           f"<span class='earn-far'>past</span>")
                st.markdown(
                    f"<div class='news-card news-neut'>"
                    f"<b>{r['Ticker']}</b> &nbsp; {r['Earnings Date']} &nbsp; {urgency}"
                    f"</div>",
                    unsafe_allow_html=True)
    else:
        with earn_col1:
            st.info("Click 'Fetch Earnings Dates' to load next earnings for watchlist")

    st.divider()
    n1, n2 = st.columns(2)
    with n1:
        st.subheader("📓 Daily Analysis"); show_md("00-Daily/daily_*.md")
    with n2:
        st.subheader("📰 News Summary");   show_md("05-News/NEWS_*.md")

# ── T7: STRATEGY LAB ──────────────────────────────────────────────────────────
with T7:
    st.subheader("📋 Strategy Lab")

    # ── Interactive backtest runner ───────────────────────────────────────────
    st.markdown("### ▶ Run Interactive Backtest")
    ibc1, ibc2, ibc3 = st.columns([2, 2, 1])
    ib_ticker   = ibc1.selectbox("Ticker",   WATCHLIST,         key="ib_ticker")
    ib_strategy = ibc2.selectbox("Strategy", ALL_STRATEGIES,    key="ib_strategy")
    run_bt_btn  = ibc3.button("▶ Run", type="primary", width='stretch',
                               help="Walk-forward backtest — 70% in-sample → 30% out-of-sample")

    if run_bt_btn:
        with st.spinner(f"Running {ib_strategy} on {ib_ticker}…"):
            try:
                from src.data_fetcher import DataFetcher as _DF     # noqa: PLC0415
                from src.backtester  import run_backtest_full as _RBF  # noqa: PLC0415
                _df = _DF().fetch_historical(ib_ticker)
                if not _df.empty:
                    _report, _eq = _RBF(_df, ib_strategy, ib_ticker)
                    st.session_state["bt_report"] = _report
                    st.session_state["bt_equity"] = _eq
                    st.session_state["bt_label"]  = f"{ib_strategy} on {ib_ticker}"
                else:
                    st.warning(f"No data available for {ib_ticker}")
            except Exception as _e:
                st.error(f"Backtest failed: {_e}")

    if "bt_report" in st.session_state:
        st.markdown(st.session_state["bt_report"])
        eq = st.session_state.get("bt_equity")
        if eq is not None and not eq.empty:
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=eq.index, y=eq["Equity"], name="Equity",
                line=dict(color="#58a6ff", width=2),
                fill="tozeroy", fillcolor="rgba(88,166,255,0.06)",
                hovertemplate="<b>%{x|%Y-%m-%d}</b><br>$%{y:,.0f}<extra></extra>",
            ))
            if "DrawdownPct" in eq.columns:
                # Drawdown on secondary y-axis (shown as positive %)
                fig_eq.add_trace(go.Scatter(
                    x=eq.index, y=eq["DrawdownPct"].abs() * 100,
                    name="Drawdown %", line=dict(color="#f85149", width=1.2, dash="dot"),
                    yaxis="y2", opacity=0.7,
                    hovertemplate="<b>%{x|%Y-%m-%d}</b><br>DD: %{y:.1f}%<extra></extra>",
                ))
            fig_eq.update_layout(
                title=f"Equity Curve — {st.session_state.get('bt_label','')}",
                height=340,
                **{k: v for k, v in PLOT_LAYOUT.items() if k not in ("yaxis",)},
                yaxis=dict(title="Equity ($)", gridcolor="#21262d"),
                yaxis2=dict(title="Drawdown %", overlaying="y", side="right",
                            gridcolor="#21262d", ticksuffix="%",
                            showgrid=False, zeroline=False),
                legend=dict(bgcolor=DARK, bordercolor="#30363d", font=dict(size=10)),
            )
            st.plotly_chart(fig_eq, width='stretch')

    st.divider()

    if not rankings.empty:
        def _sc(v): return "#3fb950" if v>=1 else "#d29922" if v>=.5 else "#8892b0" if v>=0 else "#f85149"
        colors = [_sc(s) for s in rankings["Sharpe"]]
        fig_sh = go.Figure()
        fig_sh.add_trace(go.Bar(
            y=rankings["Strategy"], x=rankings["Sharpe"], orientation="h",
            marker_color=colors, text=[f"{s:+.2f}" for s in rankings["Sharpe"]],
            textposition="outside", textfont=dict(color=colors),
            hovertemplate="<b>%{y}</b><br>Sharpe: %{x:.2f}<extra></extra>",
        ))
        fig_sh.add_vline(x=0, line_color="#f85149", line_width=1.5, line_dash="dash")
        fig_sh.add_vline(x=1, line_color="#3fb950", line_width=1, line_dash="dot",
                         annotation_text="Target 1.0", annotation_font_color="#3fb950",
                         annotation_position="top right")
        fig_sh.update_layout(title="Strategy Sharpe Ratios",
                             height=max(300, len(rankings)*32+70),
                             yaxis=dict(autorange="reversed",gridcolor="#21262d"),
                             **{k:v for k,v in PLOT_LAYOUT.items() if k!="yaxis"})
        st.plotly_chart(fig_sh, width='stretch')

        if len(rankings)>2:
            fig_b = go.Figure()
            fig_b.add_trace(go.Scatter(
                x=rankings["Win Rate"], y=rankings["Max DD"],
                mode="markers+text", text=rankings["Strategy"].str[:14],
                textposition="top center", textfont=dict(size=9,color="#8892b0"),
                marker=dict(size=rankings["Sharpe"].abs().clip(lower=.1)*20,
                            color=colors, opacity=.85, line=dict(color="#21262d",width=1)),
                hovertemplate="<b>%{text}</b><br>Win Rate: %{x:.1f}%<br>Max DD: %{y:.1f}%<extra></extra>",
            ))
            fig_b.update_layout(title="Win Rate vs Max DD  (bubble=|Sharpe|)",
                                xaxis_title="Win Rate %", yaxis_title="Max Drawdown %",
                                height=360, **PLOT_LAYOUT)
            st.plotly_chart(fig_b, width='stretch')

        with st.expander("📊 Full rankings table"):
            st.dataframe(rankings.set_index("Rank"), width='stretch')
    else:
        st.info("No rankings — run the daily loop")

    if not bt_df.empty:
        st.divider()
        st.subheader("📊 Multi-Strategy Backtest Results")
        st1, st2, st3 = st.tabs(["Return & DD","Sharpe by Ticker","Full Table"])
        strat_colors = {
            "SMA_Crossover":     "#58a6ff",
            "RSI_MeanReversion": "#3fb950",
            "MACD_Momentum":     "#d29922",
            "BB_Reversion":      "#bc8cff",
            "EMA_Momentum":      "#f0883e",
        }
        strats = bt_df["Strategy"].unique()

        with st1:
            fig_r = go.Figure()
            for strat in strats:
                sub = bt_df[bt_df["Strategy"]==strat]
                fig_r.add_trace(go.Bar(name=strat, x=sub["Ticker"], y=sub["Return"],
                                       marker_color=strat_colors.get(strat,"#58a6ff")))
            fig_r.update_layout(title="Walk-Forward Return % — All Strategies × Tickers",
                                barmode="group", height=340,
                                legend=dict(bgcolor=DARK,bordercolor="#30363d"), **PLOT_LAYOUT)
            st.plotly_chart(fig_r, width='stretch')

        with st2:
            fig_s = go.Figure()
            for strat in strats:
                sub = bt_df[bt_df["Strategy"]==strat]
                fig_s.add_trace(go.Bar(name=strat, x=sub["Ticker"], y=sub["Sharpe"],
                                       marker_color=strat_colors.get(strat,"#58a6ff")))
            fig_s.add_hline(y=1, line_color="#3fb950", line_dash="dot", line_width=1)
            fig_s.update_layout(title="Sharpe Ratio — All Strategies × Tickers",
                                barmode="group", height=320,
                                legend=dict(bgcolor=DARK,bordercolor="#30363d"), **PLOT_LAYOUT)
            st.plotly_chart(fig_s, width='stretch')

        with st3:
            st.dataframe(bt_df.sort_values("Sharpe",ascending=False), width='stretch')

    st.divider()
    mc1, mc2 = st.columns(2)
    with mc1:
        st.subheader("🎯 Meta Evaluation"); show_md("06-Playbooks/META_EVAL_*.md")
    with mc2:
        st.subheader("🔍 Critic Review");   show_md("08-Logs/CRITIC_REVIEW_*.md")

# ── T8: RESEARCH ──────────────────────────────────────────────────────────────
with T8:
    st.subheader("🔬 Ticker Research")
    tickers_avail = sorted(
        f.stem.replace("_analysis","")
        for f in VAULT.glob("07-Research/*_analysis.md")
    )
    if not tickers_avail:
        st.info("No research data — run the daily loop")
    else:
        rr1, rr2 = st.columns([2,1])
        with rr1:
            selected = st.selectbox("Select ticker", tickers_avail)
        with rr2:
            chart_type = st.radio("Chart style", ["candlestick","line"],
                                  horizontal=True, key="chart_style")

        # Technical chart
        st.markdown("### 📈 Technical Chart  *(Price · Volume · RSI · MACD)*")
        technical_chart(selected, chart_type)

        # Analysis + backtest
        d1, d2 = st.columns(2)
        with d1:
            st.markdown(f"**📊 {selected} Data Analysis**")
            af = VAULT/"07-Research"/f"{selected}_analysis.md"
            st.markdown(safe_read(af) if af.exists() else "_No analysis yet_")
        with d2:
            st.markdown("**⚙️ Latest Backtests**")
            bts = sorted(VAULT.glob(f"04-Backtests/{selected}_*.md"), reverse=True)
            if bts:
                for bf in bts[:3]:
                    with st.expander(f"📄 {bf.stem}"): st.markdown(safe_read(bf))
            else:
                st.info("No backtest yet")

        # News feed
        st.divider()
        st.markdown("### 📰 Latest News  *(from NewsScout)*")
        news_txt = latest_text("05-News/NEWS_*.md")
        if news_txt:
            pat = re.search(rf'###\s*{selected}[\s\S]{{0,800}}?(?=###|\Z)',
                            news_txt, re.IGNORECASE)
            section = pat.group(0) if pat else ""
            if not section:
                st.markdown("_No news section found for this ticker_")
            else:
                html = ""
                for line in section.splitlines():
                    if line.startswith("###") or not line.strip(): continue
                    ll  = line.lower()
                    cls = ("news-bull" if any(w in ll for w in
                               ["bullish","upgrade","beat","surge","positive","buy","strong","record"]) else
                           "news-bear" if any(w in ll for w in
                               ["bearish","downgrade","miss","fall","negative","sell","weak","loss"]) else
                           "news-neut")
                    html += f"<div class='news-card {cls}'>{line.lstrip('- ')}</div>"
                st.markdown(html or "_No headlines_", unsafe_allow_html=True)
        else:
            st.info("No news data — run the daily loop")

# ── T9: TRADING ───────────────────────────────────────────────────────────────
with T9:
    st.subheader("🚀 Alpaca Paper Trading")
    st.caption("Live data from Alpaca paper account — refreshes on page load or manual refresh")

    # ── Live data loader (cached 30s) ──────────────────────────────────────
    @st.cache_data(ttl=30, show_spinner=False)
    def _load_live_trading_data() -> dict:
        """Fetch live account, positions, and orders from Alpaca."""
        try:
            from src.alpaca_broker import AlpacaBroker  # noqa: PLC0415
            broker  = AlpacaBroker()
            return {
                "account":       broker.get_account(),
                "hours":         broker.market_hours(),
                "positions":     broker.get_positions(),
                "open_orders":   broker.get_open_orders(),
                "recent_orders": broker.get_recent_orders(limit=20),
                "error":         None,
            }
        except Exception as e:
            return {"error": str(e)}

    # Refresh button
    col_ref, col_kill = st.columns([1, 5])
    with col_ref:
        if st.button("🔄 Refresh", key="trading_refresh"):
            st.cache_data.clear()
            st.rerun()

    live = _load_live_trading_data()

    if live.get("error"):
        st.error(f"❌ Could not connect to Alpaca: {live['error']}")
        st.info("Check that ALPACA_API_KEY and ALPACA_SECRET_KEY are set in your .env file")
    else:
        acc   = live.get("account", {})
        hours = live.get("hours", {})
        is_open = hours.get("is_open", False)

        # ── Market status banner ──────────────────────────────────────────
        mkt_color = "#3fb950" if is_open else "#f85149"
        mkt_label = "🟢 MARKET OPEN" if is_open else "🔴 MARKET CLOSED"
        next_evt  = (f"Closes at {hours.get('next_close','—')}" if is_open
                     else f"Opens at {hours.get('next_open','—')}")
        st.markdown(
            f"<div style='background:#0d1117;border:1px solid {mkt_color};"
            f"border-radius:8px;padding:8px 16px;margin-bottom:12px;"
            f"color:{mkt_color};font-weight:700'>"
            f"{mkt_label} &nbsp;·&nbsp; "
            f"<span style='color:#8892b0;font-weight:400;font-size:.9em'>{next_evt}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ── Account KPIs ──────────────────────────────────────────────────
        a1, a2, a3, a4 = st.columns(4)
        pv = acc.get("portfolio_value", 0)
        eq = acc.get("equity", 0)
        cs = acc.get("cash", 0)
        bp = acc.get("buying_power", 0)
        kpi(a1, "Portfolio Value", f"${pv:,.2f}", "Paper account",  "#3fb950")
        kpi(a2, "Equity",          f"${eq:,.2f}", "Net liquidating", "#58a6ff")
        kpi(a3, "Cash",            f"${cs:,.2f}", "Settled cash",    "#cdd9e5")
        kpi(a4, "Buying Power",    f"${bp:,.2f}", "Available margin","#d29922")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Left / Right layout ───────────────────────────────────────────
        left9, right9 = st.columns([3, 2])

        # ── Open positions ────────────────────────────────────────────────
        with left9:
            st.markdown("#### 📌 Open Positions")
            positions = live.get("positions", [])
            if not positions:
                st.info("No open positions — signals must be APPROVED and executed first")
            else:
                total_pl = sum(p["unrealized_pl"] for p in positions)
                total_mv = sum(p["market_value"] for p in positions)
                st.caption(
                    f"{len(positions)} position(s) | "
                    f"Market value: ${total_mv:,.2f} | "
                    f"Total P&L: {'🟢' if total_pl>=0 else '🔴'} ${total_pl:+,.2f}"
                )
                for p in positions:
                    pc  = "#3fb950" if p["unrealized_pl"] >= 0 else "#f85149"
                    cls = "pos-gain" if p["unrealized_pl"] >= 0 else "pos-loss"
                    st.markdown(
                        f"<div class='pos-card {cls}'>"
                        f"<div style='display:flex;justify-content:space-between'>"
                        f"<span style='font-size:1.1em;font-weight:700'>{p['symbol']}</span>"
                        f"<span style='color:{pc};font-size:1em;font-weight:700'>"
                        f"${p['unrealized_pl']:+,.2f} ({p['unrealized_plpc']:+.2f}%)</span>"
                        f"</div>"
                        f"<div style='color:#8892b0;font-size:.82em;margin-top:5px'>"
                        f"Qty: {p['qty']} · Avg: ${p['avg_entry']:.2f} · "
                        f"Now: ${p['current_price']:.2f} · "
                        f"Value: ${p['market_value']:,.2f}"
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

            # ── Open orders ───────────────────────────────────────────────
            st.markdown("#### ⏳ Open Orders")
            open_orders = live.get("open_orders", [])
            if not open_orders:
                st.info("No pending orders")
            else:
                for o in open_orders:
                    side_color = "#3fb950" if "buy" in str(o["side"]).lower() else "#f85149"
                    lp = f"Limit ${o['limit_price']:.2f}" if o["limit_price"] else "Market"
                    cls_suffix = "bracket" if "bracket" in o.get("order_class","") else ""
                    st.markdown(
                        f"<div class='order-card order-open'>"
                        f"<div style='display:flex;justify-content:space-between'>"
                        f"<span style='font-weight:700'>{o['symbol']}</span>"
                        f"<span style='color:{side_color};font-weight:700'>"
                        f"{str(o['side']).upper()}</span>"
                        f"</div>"
                        f"<div style='color:#8892b0;font-size:.82em;margin-top:4px'>"
                        f"Qty: {int(o['qty'])} · {lp} · "
                        f"{'🔗 Bracket' if cls_suffix else 'Simple'} · "
                        f"ID: <code>{o['id'][:8]}…</code>"
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

        # ── Right: Manual order + kill switch ─────────────────────────────
        with right9:
            # Kill switch
            st.markdown("#### ☠️ Emergency Controls")
            st.warning("⚠️ Kill switch closes ALL positions and cancels ALL orders immediately.")
            kill_col1, kill_col2 = st.columns(2)
            with kill_col1:
                if st.button("🛑 Cancel All Orders", type="secondary", key="cancel_all"):
                    try:
                        from src.alpaca_broker import AlpacaBroker  # noqa
                        n = AlpacaBroker().cancel_all_orders()
                        st.cache_data.clear()
                        st.success(f"Cancelled {n} order(s)")
                    except Exception as e:
                        st.error(f"Failed: {e}")
            with kill_col2:
                if st.button("💀 FLATTEN ALL", type="primary", key="kill_all"):
                    try:
                        from src.alpaca_broker import AlpacaBroker  # noqa
                        n = AlpacaBroker().close_all_positions()
                        st.cache_data.clear()
                        st.success(f"Closed {n} position(s)")
                    except Exception as e:
                        st.error(f"Failed: {e}")

            st.divider()

            # Manual order form
            st.markdown("#### 📝 Manual Order")
            with st.form("manual_order_form"):
                mo_ticker = st.text_input("Ticker", value="AAPL",
                                           placeholder="e.g. AAPL").upper().strip()
                mo_side   = st.selectbox("Side", ["BUY", "SELL"])
                mo_type   = st.selectbox("Order Type", ["Market", "Limit"])
                mo_qty    = st.number_input("Shares", min_value=1, max_value=1000,
                                             value=1, step=1)
                mo_price  = st.number_input("Limit Price ($)", min_value=0.01,
                                             value=100.00, step=0.01,
                                             disabled=(mo_type == "Market"))
                submitted = st.form_submit_button("🚀 Place Order", type="primary")

            if submitted and mo_ticker:
                try:
                    from src.alpaca_broker import AlpacaBroker  # noqa
                    broker = AlpacaBroker()
                    if mo_type == "Market":
                        o = broker.place_market_order(mo_ticker, mo_side, mo_qty)
                    else:
                        o = broker.place_limit_order(mo_ticker, mo_side, mo_qty, mo_price)
                    st.cache_data.clear()
                    st.success(
                        f"✅ {mo_side} {mo_qty}× {mo_ticker} submitted\n"
                        f"Order ID: `{o['id'][:16]}…` | Status: **{o['status']}**"
                    )
                except Exception as e:
                    st.error(f"Order failed: {e}")

        st.divider()

        # ── Recent orders table ───────────────────────────────────────────
        st.markdown("#### 📋 Recent Orders (last 20)")
        recent = live.get("recent_orders", [])
        if not recent:
            st.info("No order history yet")
        else:
            rows = []
            for o in recent:
                status_str = str(o["status"])
                side_str   = str(o["side"]).upper()
                fp         = f"${o['filled_price']:.2f}" if o["filled_price"] else "—"
                lp         = f"${o['limit_price']:.2f}"  if o["limit_price"]  else "MKT"
                rows.append({
                    "Symbol":    o["symbol"],
                    "Side":      side_str,
                    "Qty":       int(o["qty"]),
                    "Filled":    int(o["filled_qty"]),
                    "Type":      str(o["type"]).replace("OrderType.", ""),
                    "Limit":     lp,
                    "Fill Price":fp,
                    "Class":     str(o["order_class"]).replace("OrderClass.", "") or "simple",
                    "Status":    status_str.replace("OrderStatus.", ""),
                    "Submitted": o["created_at"][:16],
                })
            df_orders = pd.DataFrame(rows)
            st.dataframe(
                df_orders,
                width='stretch',
                hide_index=True,
                column_config={
                    "Side": st.column_config.TextColumn(width="small"),
                    "Status": st.column_config.TextColumn(width="medium"),
                },
            )

        st.divider()

        # ── Execution log from vault ──────────────────────────────────────
        st.markdown("#### 📝 Execution Logs (vault)")
        exec_files = sorted(
            (VAULT / "03-Trade-Journal").glob("EXECUTED_*.md"), reverse=True
        )[:5]
        if not exec_files:
            st.info("No execution logs yet — run the daily loop to generate signals and trades")
        else:
            for ef in exec_files:
                with st.expander(f"📄 {ef.name}", expanded=(ef == exec_files[0])):
                    st.markdown(safe_read(ef))

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
    f"📁 `{VAULT}`  |  "
    f"🐍 `{Path(sys.executable).name}`  |  "
    f"📋 {len(WATCHLIST)} tickers  |  "
    f"🤖 {len(AGENTS)} agents  |  "
    f"📊 {len(ALL_STRATEGIES)} strategies"
)
