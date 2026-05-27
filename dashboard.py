"""
Trading Brain Dashboard
=======================
Run:  streamlit run dashboard.py

Reads vault and data/ files only — never makes network calls.
All sections gracefully degrade if a file is missing or the daily loop
hasn't run yet today.
"""

import json
import re
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import streamlit as st

# ── path constants ────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent
VAULT        = ROOT / "vault"
DATA_HIST    = ROOT / "data" / "historical"
PORTFOLIO    = VAULT / "09-Portfolio"
STRATEGIES   = VAULT / "02-Strategies"
LOGS         = VAULT / "08-Logs"
SIGNALS_DIR  = VAULT / "03-Trade-Journal"
DAILY_DIR    = VAULT / "00-Daily"
PLAYBOOKS    = VAULT / "06-Playbooks"
NEWS_DIR     = VAULT / "05-News"

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trading Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _latest_file(folder: Path, pattern: str) -> Path | None:
    """Return the most recently modified file matching glob pattern, or None."""
    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def _read(path: Path | None) -> str:
    if path and path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def _load_json(path: Path | None) -> dict | list | None:
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


# ── data loaders ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_positions() -> dict:
    data = _load_json(PORTFOLIO / "positions.json")
    if not data:
        return {"account": {}, "positions": [], "timestamp": ""}
    return data


@st.cache_data(ttl=60)
def load_signal_ledger() -> list[dict]:
    data = _load_json(PORTFOLIO / "signal_ledger.json")
    if not data:
        return []
    return data.get("signals", [])


@st.cache_data(ttl=60)
def load_volatility() -> dict:
    data = _load_json(DAILY_DIR / "volatility_latest.json")
    return data or {}


@st.cache_data(ttl=60)
def load_performance_stats() -> dict:
    data = _load_json(DATA_HIST / "performance_stats.json")
    return data or {}


@st.cache_data(ttl=60)
def load_best_params() -> dict:
    data = _load_json(DATA_HIST / "best_params.json")
    return data or {}


# ── signal + risk sweep parsers ───────────────────────────────────────────────

def _parse_signals(text: str) -> list[dict]:
    """
    Parse a SignalGenerator markdown file into a list of dicts.
    Handles the format:
        ### TICKER
        DIRECTION: ...
        CONFIDENCE: N%
        ENTRY: $X.XX  (or N/A)
        STOP:  $X.XX
        TARGET:$X.XX
        R:R:   X:X
        RATIONALE: ...
    """
    results = []
    # split on level-3 headings that look like ticker names (all-caps, 2-5 chars)
    blocks = re.split(r"^###\s+([A-Z]{1,5})\s*$", text, flags=re.MULTILINE)
    # blocks = [preamble, TICKER1, body1, TICKER2, body2, ...]
    it = iter(blocks)
    next(it)  # skip preamble
    for ticker in it:
        body = next(it, "")
        def _val(key: str) -> str:
            m = re.search(rf"^{key}[:\s]+(.+)$", body, re.MULTILINE | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        direction  = _val("DIRECTION").upper().replace("NO_SIGNAL", "NO SIGNAL")
        confidence = _val("CONFIDENCE").replace("%", "").strip()
        entry      = _val("ENTRY").replace("$", "").replace(",", "").strip()
        stop_      = _val("STOP").replace("$", "").replace(",", "").strip()
        target     = _val("TARGET").replace("$", "").replace(",", "").strip()
        rr         = _val(r"R:R")
        rationale  = _val("RATIONALE")

        def _float(s: str) -> float | None:
            try:
                return float(s)
            except Exception:
                return None

        conf_f = _float(confidence)
        results.append({
            "ticker":     ticker.strip(),
            "direction":  direction or "NO SIGNAL",
            "confidence": conf_f,
            "entry":      _float(entry),
            "stop":       _float(stop_),
            "target":     _float(target),
            "rr":         rr or "N/A",
            "rationale":  rationale[:120] + "…" if len(rationale) > 120 else rationale,
        })
    return results


def _parse_risk_sweep(text: str) -> dict[str, str]:
    """
    Return {TICKER: "APPROVE" | "REJECT"} from a RiskGuardian sweep file.
    Looks for: **VERDICT: APPROVE** or **VERDICT: REJECT**
    """
    verdicts: dict[str, str] = {}
    current_ticker = None
    for line in text.splitlines():
        m_ticker = re.match(r"^###\s+([A-Z]{1,5})\s*$", line.strip())
        if m_ticker:
            current_ticker = m_ticker.group(1)
        if current_ticker:
            if re.search(r"VERDICT.*APPROVE", line, re.IGNORECASE):
                verdicts[current_ticker] = "APPROVE"
            elif re.search(r"VERDICT.*REJECT", line, re.IGNORECASE):
                verdicts[current_ticker] = "REJECT"
    return verdicts


def _parse_regime(text: str) -> dict:
    """Extract regime, confidence, bias, volatility from a regime markdown file."""
    def _field(key: str) -> str:
        m = re.search(rf"^{key}[:\s]+(.+)$", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    return {
        "regime":     _field("REGIME"),
        "confidence": _field("CONFIDENCE"),
        "volatility": _field("VOLATILITY"),
        "bias":       _field("BIAS"),
    }


# ── cached vault reads ────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_signals_and_sweep():
    sig_file   = _latest_file(SIGNALS_DIR, "signals_*.md")
    sweep_file = _latest_file(PLAYBOOKS,  "RISK_SWEEP_*.md")

    signals = _parse_signals(_read(sig_file))
    sweep   = _parse_risk_sweep(_read(sweep_file))

    # merge sweep verdict into each signal row
    for s in signals:
        s["verdict"] = sweep.get(s["ticker"], "—")

    sig_date   = sig_file.stem.replace("signals_", "")   if sig_file   else "—"
    sweep_date = sweep_file.stem.replace("RISK_SWEEP_", "") if sweep_file else "—"
    return signals, sig_date, sweep_date


@st.cache_data(ttl=60)
def load_regime():
    f = _latest_file(DAILY_DIR, "regime_*.md")
    return _parse_regime(_read(f)), f.stem if f else "—"


@st.cache_data(ttl=60)
def load_strategy_ranking() -> tuple[str, str]:
    f = _latest_file(PLAYBOOKS, "STRATEGY_RANKING_*.md")
    return _read(f), f.stem if f else "—"


@st.cache_data(ttl=60)
def load_critic_reviews() -> list[tuple[str, str]]:
    files = sorted(LOGS.glob("CRITIC_REVIEW_*.md"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:4]
    return [(f.stem.replace("CRITIC_REVIEW_", ""), _read(f)) for f in files]


@st.cache_data(ttl=60)
def load_news() -> str:
    f = _latest_file(NEWS_DIR, "NEWS_*.md")
    return _read(f)


@st.cache_data(ttl=60)
def load_pnl_report() -> tuple[str, str]:
    f = _latest_file(PLAYBOOKS, "PNL_REPORT_*.md")
    return _read(f), f.stem if f else "—"


# ── colour helpers ────────────────────────────────────────────────────────────

def _direction_badge(direction: str) -> str:
    d = (direction or "").upper()
    if "BUY" in d:
        return "🟢 BUY"
    if "SELL" in d:
        return "🔴 SELL"
    return "⚪ NO SIGNAL"


def _verdict_badge(verdict: str) -> str:
    if verdict == "APPROVE":
        return "✅ APPROVE"
    if verdict == "REJECT":
        return "❌ REJECT"
    return "—"


def _conf_colour(conf: float | None) -> str:
    if conf is None:
        return ""
    if conf >= 75:
        return "🟢"
    if conf >= 65:
        return "🟡"
    return "🔴"


def _pf_colour(pf: float) -> str:
    if pf >= 0.85:
        return "background-color: #1a472a; color: white"
    if pf >= 0.60:
        return "background-color: #2d4a1e; color: white"
    if pf >= 0.40:
        return "background-color: #4a3000; color: white"
    return "background-color: #4a1e1e; color: white"


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

# ── title bar ─────────────────────────────────────────────────────────────────
col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.title("🧠 Trading Brain Dashboard")
    st.caption(f"Live read from vault  ·  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
with col_refresh:
    st.write("")
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ── load all data ─────────────────────────────────────────────────────────────
positions_data  = load_positions()
account         = positions_data.get("account", {})
positions       = positions_data.get("positions", [])
signals, sig_date, sweep_date = load_signals_and_sweep()
regime_data, regime_file      = load_regime()
vol_data        = load_volatility()
perf_stats      = load_performance_stats()
best_params     = load_best_params()
ledger          = load_signal_ledger()

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PORTFOLIO
# ═══════════════════════════════════════════════════════════════════════════════
tab_portfolio, tab_signals, tab_market, tab_strategy, tab_reviews = st.tabs([
    "💼 Portfolio", "🎯 Signals", "🌡️ Market", "📈 Strategy", "🔍 Reviews"
])

with tab_portfolio:
    # ── account metrics ───────────────────────────────────────────────────────
    equity    = float(account.get("equity",          0) or 0)
    cash      = float(account.get("cash",            0) or 0)
    bpower    = float(account.get("buying_power",    0) or 0)
    port_val  = float(account.get("portfolio_value", 0) or 0)
    invested  = port_val - cash if port_val and cash else 0.0

    snap_ts   = positions_data.get("timestamp", "")
    snap_str  = (snap_ts[:19].replace("T", " ") if snap_ts else "no snapshot")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Equity",        f"${equity:,.2f}")
    m2.metric("Cash",          f"${cash:,.2f}")
    m3.metric("Invested",      f"${invested:,.2f}")
    m4.metric("Buying Power",  f"${bpower:,.2f}")
    m5.metric("Snapshot",      snap_str[:10], delta=snap_str[11:] if len(snap_str) > 10 else None,
              delta_color="off")

    st.divider()

    # ── open positions ────────────────────────────────────────────────────────
    st.subheader("Open Positions")
    if positions:
        rows = []
        total_unpl = 0.0
        for p in positions:
            qty      = float(p.get("qty",            0) or 0)
            avg_e    = float(p.get("avg_entry",      0) or 0)
            cur_px   = float(p.get("current_price",  0) or 0)
            mkt_val  = float(p.get("market_value",   0) or 0)
            unpl     = float(p.get("unrealized_pl",  0) or 0)
            unpl_pct = float(p.get("unrealized_plpc",0) or 0)
            side     = str(p.get("side", "")).replace("PositionSide.", "")
            total_unpl += unpl

            rows.append({
                "Ticker":       p.get("symbol", "?"),
                "Side":         side,
                "Qty":          qty,
                "Avg Entry":    f"${avg_e:.2f}",
                "Current":      f"${cur_px:.2f}",
                "Mkt Value":    f"${mkt_val:,.2f}",
                "Unreal P&L":   f"${unpl:+,.2f}",
                "Unreal P&L %": f"{unpl_pct:+.2f}%",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        colour = "green" if total_unpl >= 0 else "red"
        st.markdown(f"**Total Unrealized P&L: :{colour}[${total_unpl:+,.2f}]**")
    else:
        st.info("No open positions in latest snapshot.")

    st.divider()

    # ── signal ledger (trade history) ─────────────────────────────────────────
    st.subheader("Signal Ledger")
    if ledger:
        rows = []
        for s in reversed(ledger[-30:]):   # last 30, newest first
            outcome = s.get("outcome", "OPEN")
            pct     = s.get("outcome_pct")
            rows.append({
                "Date":       s.get("date", ""),
                "Ticker":     s.get("ticker", ""),
                "Direction":  s.get("direction", ""),
                "Confidence": f"{s.get('confidence', 0)}%",
                "Entry":      f"${float(s.get('entry', 0) or 0):.2f}",
                "Stop":       f"${float(s.get('stop',  0) or 0):.2f}",
                "Target":     f"${float(s.get('target',0) or 0):.2f}",
                "Outcome":    outcome,
                "P&L %":      f"{pct:+.2f}%" if pct is not None else "—",
                "Note":       (s.get("outcome_note", "") or "")[:60],
            })
        df_ledger = pd.DataFrame(rows)

        def _style_outcome(val):
            if val == "WIN":   return "background-color: #1a472a; color: white"
            if val == "LOSS":  return "background-color: #4a1e1e; color: white"
            if val == "OPEN":  return "background-color: #2a3a4a; color: white"
            return ""

        styled = df_ledger.style.applymap(_style_outcome, subset=["Outcome"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        wins   = sum(1 for s in ledger if s.get("outcome") == "WIN")
        losses = sum(1 for s in ledger if s.get("outcome") == "LOSS")
        if wins + losses > 0:
            wr = wins / (wins + losses) * 100
            st.caption(f"Resolved: {wins}W / {losses}L → Win rate **{wr:.0f}%**")
    else:
        st.info("Signal ledger is empty — no signals have been logged yet.")

    # ── PnL report ────────────────────────────────────────────────────────────
    pnl_text, pnl_fname = load_pnl_report()
    if pnl_text:
        with st.expander(f"📋 PnL Report ({pnl_fname})", expanded=False):
            st.markdown(pnl_text)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_signals:
    if not signals:
        st.warning("No signals file found in vault/03-Trade-Journal/")
    else:
        approved = [s for s in signals if s["verdict"] == "APPROVE"]
        rejected = [s for s in signals if s["verdict"] == "REJECT"]
        no_sig   = [s for s in signals if s["direction"] == "NO SIGNAL"]

        # ── summary bar ───────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Signals File",   sig_date)
        c2.metric("✅ Approved",    len(approved))
        c3.metric("❌ Rejected",    len(rejected))
        c4.metric("⚪ No Signal",   len(no_sig))

        st.divider()

        # ── approved signals (prominent) ─────────────────────────────────────
        if approved:
            st.subheader("✅ Approved Signals")
            for s in approved:
                conf_e = s["confidence"]
                rr_str = s.get("rr", "N/A")
                with st.container(border=True):
                    cols = st.columns([1, 1, 1, 1, 1, 1, 3])
                    cols[0].metric("Ticker",     s["ticker"])
                    cols[1].metric("Direction",  _direction_badge(s["direction"]))
                    cols[2].metric("Confidence", f"{conf_e:.0f}%" if conf_e else "—")
                    cols[3].metric("Entry",      f"${s['entry']:.2f}"  if s["entry"]  else "—")
                    cols[4].metric("Stop",       f"${s['stop']:.2f}"   if s["stop"]   else "—")
                    cols[5].metric("Target",     f"${s['target']:.2f}" if s["target"] else "—")
                    cols[6].markdown(f"**R:R** {rr_str}  \n{s.get('rationale', '')}")
        else:
            st.info("No signals approved by RiskGuardian today.")

        st.divider()

        # ── full signal table (all tickers) ──────────────────────────────────
        st.subheader("All Signals")
        rows = []
        for s in signals:
            rows.append({
                "Ticker":     s["ticker"],
                "Direction":  _direction_badge(s["direction"]),
                "Conf":       f"{_conf_colour(s['confidence'])} {s['confidence']:.0f}%" if s["confidence"] else "—",
                "Entry":      f"${s['entry']:.2f}"  if s["entry"]  else "—",
                "Stop":       f"${s['stop']:.2f}"   if s["stop"]   else "—",
                "Target":     f"${s['target']:.2f}" if s["target"] else "—",
                "R:R":        s.get("rr", "—"),
                "Verdict":    _verdict_badge(s["verdict"]),
                "Rationale":  s.get("rationale", ""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # ── raw sweep notes ───────────────────────────────────────────────────
        sweep_file = _latest_file(PLAYBOOKS, "RISK_SWEEP_*.md")
        if sweep_file:
            with st.expander(f"📄 Full Risk Sweep ({sweep_file.stem})", expanded=False):
                st.markdown(_read(sweep_file))


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — MARKET
# ═══════════════════════════════════════════════════════════════════════════════
with tab_market:
    c_left, c_right = st.columns([1, 1])

    # ── regime card ───────────────────────────────────────────────────────────
    with c_left:
        st.subheader("📍 Market Regime")
        regime  = regime_data.get("regime",     "—")
        r_conf  = regime_data.get("confidence", "—")
        r_vol   = regime_data.get("volatility", "—")
        r_bias  = regime_data.get("bias",       "—")

        colour = "green" if "bull" in regime.lower() else ("red" if "bear" in regime.lower() else "orange")
        st.markdown(f"### :{colour}[{regime}]")
        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("Confidence",  r_conf)
        col_r2.metric("Volatility",  r_vol)
        col_r3.metric("Bias",        r_bias.upper() if r_bias else "—")

        regime_file_full = _latest_file(DAILY_DIR, "regime_*.md")
        with st.expander("Full Regime Note", expanded=False):
            st.markdown(_read(regime_file_full))

    # ── volatility card ───────────────────────────────────────────────────────
    with c_right:
        st.subheader("📊 Volatility")
        vix     = vol_data.get("vix", None)
        vix_reg = vol_data.get("vix_regime", "—")
        vix_pct = vol_data.get("vix_percentile_1yr", None)
        tickers_vol = vol_data.get("tickers", {})

        if vix:
            cv1, cv2 = st.columns(2)
            cv1.metric("VIX",        f"{vix:.2f}",  delta=vix_reg)
            cv2.metric("Percentile", f"{vix_pct}%" if vix_pct else "—")

        if tickers_vol:
            rows_v = []
            for t, v in tickers_vol.items():
                expanding = v.get("expanding", False)
                rows_v.append({
                    "Ticker":    t,
                    "HV20":      f"{v.get('hv20', 0):.1f}%",
                    "HV60":      f"{v.get('hv60', 0):.1f}%",
                    "Ratio":     f"{v.get('ratio', 0):.2f}",
                    "Vol State": "🔴 Expanding" if expanding else "🟢 Contracting",
                })
            st.dataframe(pd.DataFrame(rows_v), use_container_width=True, hide_index=True)

    st.divider()

    # ── news headline ─────────────────────────────────────────────────────────
    news_text = load_news()
    if news_text:
        with st.expander("📰 Latest News Summary", expanded=False):
            st.markdown(news_text[:3000] + ("…" if len(news_text) > 3000 else ""))

    # ── sector data ───────────────────────────────────────────────────────────
    sectors_file = DAILY_DIR / "sectors_latest.json"
    sectors_data = _load_json(sectors_file)
    if sectors_data:
        st.subheader("🏭 Sector Rotation")
        # sectors_latest.json is a dict of sector → data; render as table
        if isinstance(sectors_data, dict):
            rows_s = []
            for sector, vals in sectors_data.items():
                if isinstance(vals, dict):
                    rows_s.append({"Sector": sector, **{k: v for k, v in vals.items()}})
                else:
                    rows_s.append({"Sector": sector, "Value": vals})
            if rows_s:
                st.dataframe(pd.DataFrame(rows_s), use_container_width=True, hide_index=True)
        elif isinstance(sectors_data, list):
            st.dataframe(pd.DataFrame(sectors_data), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — STRATEGY
# ═══════════════════════════════════════════════════════════════════════════════
with tab_strategy:
    # ── best strategy per ticker ──────────────────────────────────────────────
    st.subheader("🏆 Best Strategy per Ticker")
    by_ticker = perf_stats.get("by_ticker", {})
    regime_best = best_params.get("regime_best_strategy", {})

    if by_ticker:
        rows_bt = []
        for ticker, bt in by_ticker.items():
            pf = bt.get("best_profit_factor", 0)
            rows_bt.append({
                "Ticker":        ticker,
                "Best Strategy": bt.get("best_strategy", "—"),
                "Win Rate":      f"{bt.get('best_win_rate', 0):.1f}%",
                "Wins":          bt.get("best_wins", 0),
                "Losses":        bt.get("best_losses", 0),
                "Profit Factor": f"{pf:.3f}",
                "Return %":      f"{bt.get('best_return_pct', 0):+.1f}%",
                "P&L ($100k)":   f"${bt.get('best_pnl_usd', 0):+,.0f}",
            })
        st.dataframe(pd.DataFrame(rows_bt), use_container_width=True, hide_index=True)
    else:
        st.info("Run train_strategies.py to populate performance data.")

    # ── regime → strategy map ─────────────────────────────────────────────────
    if regime_best:
        st.subheader("🗺️ Regime → Strategy Map")
        by_strat = perf_stats.get("by_strategy", {})
        rows_rm = []
        for reg, strat in regime_best.items():
            agg = by_strat.get(strat, {})
            rows_rm.append({
                "Regime":        reg,
                "Best Strategy": strat,
                "Avg Win Rate":  f"{agg.get('avg_win_rate', 0):.1f}%",
                "Avg PF":        f"{agg.get('avg_profit_factor', 0):.3f}",
                "Avg Return":    f"{agg.get('avg_return_pct', 0):+.1f}%",
                "Avg Calmar":    f"{agg.get('avg_calmar', 0):.2f}",
            })
        st.dataframe(pd.DataFrame(rows_rm), use_container_width=True, hide_index=True)

    st.divider()

    # ── profit factor heatmap ─────────────────────────────────────────────────
    st.subheader("🔥 Profit Factor Heatmap (Strategy × Ticker)")
    by_session = perf_stats.get("by_session", [])
    if by_session:
        try:
            import plotly.graph_objects as go

            df_pf = pd.DataFrame(by_session)[["ticker", "strategy", "profit_factor"]]
            pf_pivot = df_pf.pivot_table(
                index="strategy", columns="ticker", values="profit_factor", aggfunc="max"
            )

            # order strategies by mean PF descending
            pf_pivot = pf_pivot.loc[pf_pivot.mean(axis=1).sort_values(ascending=False).index]

            # colour scale: red (<0.40) → orange (0.40–0.60) → yellow (0.60–0.85) → green (≥0.85)
            fig = go.Figure(data=go.Heatmap(
                z=pf_pivot.values,
                x=list(pf_pivot.columns),
                y=list(pf_pivot.index),
                colorscale=[
                    [0.0,  "#4a1e1e"],   # deep red   — PF=0
                    [0.4,  "#8b3a00"],   # dark orange — PF=0.4
                    [0.6,  "#8b7200"],   # dark yellow — PF=0.6
                    [0.85, "#1a5c1a"],   # mid green   — PF=0.85
                    [1.0,  "#00c800"],   # bright green — PF=max
                ],
                zmin=0.0,
                zmax=max(1.0, pf_pivot.values.max()),
                text=pf_pivot.round(3).values,
                texttemplate="%{text}",
                hovertemplate="<b>%{y}</b> × <b>%{x}</b><br>Profit Factor: %{z:.3f}<extra></extra>",
            ))
            fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"),
                xaxis=dict(tickfont=dict(size=11)),
                yaxis=dict(tickfont=dict(size=11)),
                title="Profit Factor (0 = ruins account, 1.0 = breakeven, >1 = profitable)",
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.warning("Install plotly for heatmap: `pip install plotly`")
            # fallback table
            st.dataframe(pf_pivot.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=1.5),
                         use_container_width=True)

    # ── strategy ranking note ─────────────────────────────────────────────────
    ranking_text, ranking_fname = load_strategy_ranking()
    if ranking_text:
        with st.expander(f"📄 Strategy Ranking ({ranking_fname})", expanded=False):
            st.markdown(ranking_text)

    # ── best params table ─────────────────────────────────────────────────────
    st.subheader("⚙️ Optimised Parameters")
    strategies_params = best_params.get("strategies", {})
    if strategies_params:
        rows_p = []
        for strat, tickers_p in strategies_params.items():
            for ticker, params in tickers_p.items():
                clean = {k: v for k, v in params.items() if not k.startswith("_")}
                oos_r = params.get("_oos_return", None)
                rows_p.append({
                    "Strategy": strat,
                    "Ticker":   ticker,
                    **{k: v for k, v in clean.items()},
                    "OOS Return": f"{oos_r:+.1f}%" if oos_r is not None else "—",
                    "OOS Calmar": f"{params.get('_oos_calmar', 0):+.3f}",
                })
        # only show non-trivial params (exclude all-NaN columns)
        df_p = pd.DataFrame(rows_p).dropna(axis=1, how="all")
        with st.expander("Show all optimised params", expanded=False):
            st.dataframe(df_p, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — REVIEWS
# ═══════════════════════════════════════════════════════════════════════════════
with tab_reviews:
    st.subheader("🔍 Latest Critic Reviews")
    reviews = load_critic_reviews()
    if reviews:
        for name, text in reviews:
            with st.expander(f"📝 {name}", expanded=False):
                st.markdown(text)
    else:
        st.info("No critic reviews found in vault/08-Logs/")

    st.divider()

    # ── outcomes ──────────────────────────────────────────────────────────────
    st.subheader("📊 OutcomeTracker")
    outcomes_file = _latest_file(LOGS, "OUTCOMES_*.md")
    if outcomes_file:
        with st.expander(f"📄 {outcomes_file.stem}", expanded=True):
            st.markdown(_read(outcomes_file)[:4000])
    else:
        st.info("No outcomes file found.")

    st.divider()

    # ── daily agent log ───────────────────────────────────────────────────────
    st.subheader("📋 Daily Agent Log")
    daily_file = _latest_file(DAILY_DIR, "daily_*.md")
    if daily_file:
        with st.expander(f"📄 {daily_file.stem}", expanded=False):
            st.markdown(_read(daily_file))

    # ── run logs ──────────────────────────────────────────────────────────────
    logs_dir = ROOT / "logs"
    if logs_dir.exists():
        log_files = sorted(logs_dir.glob("daily_*.log"),
                           key=lambda p: p.stat().st_mtime, reverse=True)[:3]
        if log_files:
            st.subheader("📟 Recent Run Logs")
            for lf in log_files:
                with st.expander(f"🗒️ {lf.name}", expanded=False):
                    content = lf.read_text(encoding="utf-8", errors="replace")
                    # show tail (most important = end of run)
                    lines = content.splitlines()
                    tail  = "\n".join(lines[-120:])
                    st.code(tail, language="text")

# ── footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Trading Brain dashboard · reads vault/ in real time · "
    "data never sent to network · "
    f"vault at `{VAULT}`"
)
