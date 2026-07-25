"""
NSE Sector Heatmap Dashboard
-----------------------------
Shows Top 5 gainers and Top 5 losers for each NSE sectoral index
(NIFTY AUTO, NIFTY BANK, NIFTY PHARMA, etc.), styled like the official
NSE heatmap (https://www.nseindia.com/market-data/live-market-indices/heatmap).

Auto-refreshes every 60 seconds.

Data source: NSE India public API (www.nseindia.com/api/equity-stockIndices)
"""

import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
REFRESH_SECONDS = 60
TOP_N = 5

# Display name -> exact NSE index name (as used by the NSE API "index" param)
SECTORS = {
    "NIFTY AUTO": "NIFTY AUTO",
    "NIFTY BANK": "NIFTY BANK",
    "NIFTY FINANCIAL SERVICES": "NIFTY FINANCIAL SERVICES",
    "NIFTY FINANCIAL SERVICES 25/50": "NIFTY FINANCIAL SERVICES 25/50",
    "NIFTY FMCG": "NIFTY FMCG",
    "NIFTY IT": "NIFTY IT",
    "NIFTY MEDIA": "NIFTY MEDIA",
    "NIFTY METAL": "NIFTY METAL",
    "NIFTY PHARMA": "NIFTY PHARMA",
    "NIFTY PSU BANK": "NIFTY PSU BANK",
    "NIFTY REALTY": "NIFTY REALTY",
    "NIFTY PRIVATE BANK": "NIFTY PRIVATE BANK",
    "NIFTY HEALTHCARE INDEX": "NIFTY HEALTHCARE INDEX",
    "NIFTY CONSUMER DURABLES": "NIFTY CONSUMER DURABLES",
    "NIFTY OIL & GAS": "NIFTY OIL & GAS",
    "NIFTY MIDSMALL HEALTHCARE": "NIFTY MIDSMALL HEALTHCARE",
    "NIFTY CHEMICALS": "NIFTY CHEMICALS",
}

NSE_BASE = "https://www.nseindia.com"
NSE_API = "https://www.nseindia.com/api/equity-stockIndices"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/live-market-indices/heatmap",
    "X-Requested-With": "XMLHttpRequest",
}

# --------------------------------------------------------------------------
# DATA FETCHING
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_session() -> requests.Session:
    """NSE requires cookies from a normal page load before the API works."""
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get(NSE_BASE, timeout=10)
        s.get(f"{NSE_BASE}/market-data/live-market-indices", timeout=10)
    except Exception:
        pass
    return s


def fetch_index_constituents(index_name: str, retries: int = 3) -> pd.DataFrame:
    """Fetch live constituent data for a single NSE sector index."""
    for attempt in range(retries):
        session = get_session()
        try:
            resp = session.get(NSE_API, params={"index": index_name}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("data", [])
                df = pd.DataFrame(rows)
                if not df.empty and "symbol" in df.columns:
                    # Drop the summary row for the index itself (symbol == index name)
                    df = df[df["symbol"].str.upper() != index_name.upper()]
                if not df.empty:
                    return df
        except Exception:
            pass
        # Session may be stale / blocked -> refresh cookies and retry
        get_session.clear()
        time.sleep(1)
    return pd.DataFrame()


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def load_all_sectors(sector_map: dict) -> tuple[dict, datetime]:
    result = {}
    for display_name, index_name in sector_map.items():
        result[display_name] = fetch_index_constituents(index_name)
    return result, datetime.now()


def top_bottom(df: pd.DataFrame, n: int = TOP_N):
    if df.empty or "pChange" not in df.columns:
        return pd.DataFrame(), pd.DataFrame()
    df = df.copy()
    df["pChange"] = pd.to_numeric(df["pChange"], errors="coerce")
    df["lastPrice"] = pd.to_numeric(df.get("lastPrice"), errors="coerce")
    df = df.dropna(subset=["pChange"])
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    df = df.sort_values("pChange", ascending=False)
    top = df.head(n)
    bottom = df.tail(n).sort_values("pChange")
    return top, bottom


# --------------------------------------------------------------------------
# STYLING HELPERS
# --------------------------------------------------------------------------
def tile_color(pchange: float) -> str:
    if pd.isna(pchange):
        return "#8a8a8a"
    if pchange >= 4:
        return "#0b6e2f"
    if pchange >= 2:
        return "#1e8449"
    if pchange >= 1:
        return "#52be80"
    if pchange >= 0:
        return "#a9dfbf"
    if pchange >= -1:
        return "#f5b7b1"
    if pchange >= -2:
        return "#ec7063"
    if pchange >= -4:
        return "#cb4335"
    return "#7b241c"


def render_tiles(df: pd.DataFrame) -> str:
    if df.empty:
        return "<div style='color:#888;padding:8px;'>No data</div>"
    tiles = []
    for _, row in df.iterrows():
        symbol = row.get("symbol", "-")
        price = row.get("lastPrice", float("nan"))
        pchange = row.get("pChange", float("nan"))
        color = tile_color(pchange)
        text_color = "#ffffff"
        price_str = f"{price:,.2f}" if pd.notna(price) else "-"
        pchange_str = f"{pchange:+.2f}%" if pd.notna(pchange) else "-"
        tiles.append(
            f"""
            <div style="background:{color};color:{text_color};border-radius:6px;
                        padding:10px 12px;margin:4px;flex:1 1 140px;min-width:130px;
                        font-family:Arial, sans-serif;">
                <div style="font-weight:700;font-size:13px;">{symbol}</div>
                <div style="font-size:13px;">{price_str}</div>
                <div style="font-size:13px;font-weight:600;">{pchange_str}</div>
            </div>
            """
        )
    return f"<div style='display:flex;flex-wrap:wrap;'>{''.join(tiles)}</div>"


def render_sector_chart(top: pd.DataFrame, bottom: pd.DataFrame, sector_name: str) -> go.Figure:
    combo = pd.concat([top, bottom]).drop_duplicates(subset="symbol")
    combo = combo.sort_values("pChange")
    colors = [tile_color(v) for v in combo["pChange"]]
    fig = go.Figure(
        go.Bar(
            x=combo["pChange"],
            y=combo["symbol"],
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.2f}%" for v in combo["pChange"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title=f"{sector_name} — Top {TOP_N} Gainers & Losers",
        height=max(280, 40 * len(combo)),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title="% Change",
        yaxis_title="",
        showlegend=False,
        template="plotly_white",
    )
    return fig


# --------------------------------------------------------------------------
# APP LAYOUT
# --------------------------------------------------------------------------
st.set_page_config(page_title="NSE Sector Heatmap Dashboard", layout="wide", page_icon="📊")

# Browser-side auto refresh (full page reload triggers a Streamlit rerun)
st.markdown(f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">', unsafe_allow_html=True)

st.title("📊 NSE Sector Heatmap — Top 5 Gainers & Losers per Sector")
st.caption(
    "Live data from NSE India · Auto-refreshes every "
    f"{REFRESH_SECONDS} seconds · Source: nseindia.com/market-data/live-market-indices/heatmap"
)

with st.sidebar:
    st.header("Settings")
    selected_sectors = st.multiselect(
        "Sectors to display",
        options=list(SECTORS.keys()),
        default=list(SECTORS.keys()),
    )
    view_mode = st.radio("View", ["Tiles (heatmap style)", "Bar chart"], index=0)
    if st.button("🔄 Refresh now"):
        load_all_sectors.clear()
        st.rerun()

if not selected_sectors:
    st.warning("Select at least one sector from the sidebar.")
    st.stop()

with st.spinner("Fetching live NSE data..."):
    sector_map = {k: SECTORS[k] for k in selected_sectors}
    all_data, fetched_at = load_all_sectors(sector_map)

st.caption(f"Last updated: {fetched_at.strftime('%Y-%m-%d %H:%M:%S')} (next refresh in ~{REFRESH_SECONDS}s)")

any_data = False
for sector_name in selected_sectors:
    df = all_data.get(sector_name, pd.DataFrame())
    top, bottom = top_bottom(df, TOP_N)

    st.subheader(sector_name)

    if top.empty and bottom.empty:
        st.info(
            "Could not fetch live data for this sector right now "
            "(NSE may be rate-limiting or temporarily unavailable). Will retry on next refresh."
        )
        continue

    any_data = True

    if view_mode == "Tiles (heatmap style)":
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🟢 Top 5 Gainers**", help="Best performing stocks in this sector")
            st.markdown(render_tiles(top), unsafe_allow_html=True)
        with col2:
            st.markdown("**🔴 Top 5 Losers**", help="Worst performing stocks in this sector")
            st.markdown(render_tiles(bottom), unsafe_allow_html=True)
    else:
        fig = render_sector_chart(top, bottom, sector_name)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

if not any_data:
    st.error(
        "No live data could be retrieved for any sector. NSE frequently blocks requests "
        "coming from cloud/datacenter IPs (including some Streamlit Cloud regions). "
        "See the README for workarounds."
    )
