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

# NSE's bot-protection (Akamai) often fingerprints the TLS handshake itself,
# not just headers/cookies — something the plain `requests` library can't fake.
# `curl_cffi` impersonates a real Chrome TLS fingerprint and is frequently the
# difference between "works in my browser" and "blocked from the server".
# It's optional: the app falls back to plain `requests` if it isn't installed.
try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    curl_requests = None
    HAS_CURL_CFFI = False

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
NSE_HEATMAP_PAGE = "https://www.nseindia.com/market-data/live-market-indices/heatmap"
NSE_API = "https://www.nseindia.com/api/equity-stockIndices"


# Optional: set an HTTP(S) proxy in Streamlit secrets if your host's IP gets
# blocked by NSE (common on cloud/datacenter IPs). In .streamlit/secrets.toml:
#   NSE_PROXY = "http://user:pass@proxy-host:port"
def _get_proxies():
    try:
        proxy = st.secrets.get("NSE_PROXY")
    except Exception:
        proxy = None
    if proxy:
        return {"http": proxy, "https": proxy}
    return None


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": NSE_HEATMAP_PAGE,
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Chromium";v="126", "Not.A/Brand";v="24", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "DNT": "1",
}

PAGE_HEADERS = {
    **BROWSER_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


# --------------------------------------------------------------------------
# DATA FETCHING
# --------------------------------------------------------------------------
def _new_session():
    """Warm up a fresh session the way a real browser would: home page,
    then the heatmap page itself, picking up NSE's anti-bot cookies along the way.
    Uses curl_cffi (real Chrome TLS fingerprint) when available, since NSE's
    bot protection often keys off the TLS handshake, not just HTTP headers."""
    proxies = _get_proxies()
    if HAS_CURL_CFFI:
        s = curl_requests.Session(impersonate="chrome124")
        if proxies:
            s.proxies = proxies
    else:
        s = requests.Session()
        if proxies:
            s.proxies.update(proxies)
    try:
        s.get(NSE_BASE, headers=PAGE_HEADERS, timeout=12)
        time.sleep(0.6)
        s.get(NSE_HEATMAP_PAGE, headers=PAGE_HEADERS, timeout=12)
        time.sleep(0.6)
    except Exception:
        pass
    return s


def get_session() -> requests.Session:
    if "nse_session" not in st.session_state:
        st.session_state.nse_session = _new_session()
    return st.session_state.nse_session


def reset_session():
    st.session_state.nse_session = _new_session()


def fetch_index_constituents(index_name: str, retries: int = 3):
    """Fetch live constituent data for a single NSE sector index.
    Returns (dataframe, diagnostic_message). Diagnostic message is empty on success."""
    last_error = ""
    for attempt in range(retries):
        session = get_session()
        try:
            resp = session.get(
                NSE_API, params={"index": index_name}, headers=BROWSER_HEADERS, timeout=12
            )
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    last_error = (
                        f"HTTP 200 but response wasn't JSON "
                        f"(likely a block/captcha page, {len(resp.text)} bytes)."
                    )
                    reset_session()
                    time.sleep(1 + attempt)
                    continue
                rows = data.get("data", [])
                df = pd.DataFrame(rows)
                if not df.empty and "symbol" in df.columns:
                    df = df[df["symbol"].str.upper() != index_name.upper()]
                if not df.empty:
                    return df, ""
                last_error = "Server returned 200 but no constituent rows."
            elif resp.status_code in (401, 403):
                last_error = f"HTTP {resp.status_code} - blocked/unauthorized (NSE anti-bot or IP block)."
            elif resp.status_code == 429:
                last_error = "HTTP 429 - rate limited by NSE."
            else:
                last_error = f"HTTP {resp.status_code}."
        except requests.exceptions.Timeout:
            last_error = "Request timed out."
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e.__class__.__name__}."
        except Exception as e:
            last_error = f"{e.__class__.__name__}: {e}"
        reset_session()
        time.sleep(1 + attempt)
    return pd.DataFrame(), last_error


@st.cache_data(ttl=REFRESH_SECONDS, show_spinner=False)
def load_all_sectors(sector_map: dict):
    result = {}
    errors = {}
    for display_name, index_name in sector_map.items():
        df, err = fetch_index_constituents(index_name)
        result[display_name] = df
        errors[display_name] = err
        time.sleep(0.4)  # small stagger between sectors, easier on rate limits
    return result, errors, datetime.now()


def run_diagnostics():
    """Quick step-by-step connectivity check the user can trigger from the sidebar."""
    lines = []
    lines.append(
        f"HTTP engine: {'curl_cffi (Chrome TLS impersonation)' if HAS_CURL_CFFI else 'requests (no TLS impersonation - install curl_cffi for better results)'}"
    )
    proxies = _get_proxies()
    s = curl_requests.Session(impersonate="chrome124") if HAS_CURL_CFFI else requests.Session()
    if proxies:
        if HAS_CURL_CFFI:
            s.proxies = proxies
        else:
            s.proxies.update(proxies)
        lines.append("Using proxy from secrets: yes")
    else:
        lines.append("Using proxy from secrets: no (set NSE_PROXY in secrets.toml if needed)")
    try:
        r1 = s.get(NSE_BASE, headers=PAGE_HEADERS, timeout=12)
        lines.append(f"1) GET {NSE_BASE} -> HTTP {r1.status_code}, {len(r1.content)} bytes")
    except Exception as e:
        lines.append(f"1) GET {NSE_BASE} -> FAILED: {e}")
        return lines
    time.sleep(0.5)
    try:
        r2 = s.get(NSE_HEATMAP_PAGE, headers=PAGE_HEADERS, timeout=12)
        lines.append(f"2) GET heatmap page -> HTTP {r2.status_code}, {len(r2.content)} bytes")
    except Exception as e:
        lines.append(f"2) GET heatmap page -> FAILED: {e}")
    time.sleep(0.5)
    try:
        r3 = s.get(NSE_API, params={"index": "NIFTY AUTO"}, headers=BROWSER_HEADERS, timeout=12)
        lines.append(f"3) GET api/equity-stockIndices?index=NIFTY AUTO -> HTTP {r3.status_code}")
        ct = r3.headers.get("Content-Type", "")
        lines.append(f"   Content-Type: {ct}")
        if r3.status_code == 200:
            try:
                d = r3.json()
                lines.append(f"   JSON OK, rows returned: {len(d.get('data', []))}")
            except Exception:
                lines.append(f"   Response is NOT valid JSON (first 200 chars): {r3.text[:200]!r}")
        else:
            lines.append(f"   Response first 200 chars: {r3.text[:200]!r}")
    except Exception as e:
        lines.append(f"3) GET api -> FAILED: {e}")
    return lines


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
        reset_session()
        st.rerun()

    with st.expander("🔧 Connection diagnostics"):
        st.caption(
            "If sectors show 'could not fetch data', run this to see exactly "
            "where the request is failing (this is almost always NSE blocking "
            "the server's IP address, not a bug in the app)."
        )
        if st.button("Run diagnostic check"):
            with st.spinner("Testing connection to NSE..."):
                diag_lines = run_diagnostics()
            st.code("\n".join(diag_lines))

if not selected_sectors:
    st.warning("Select at least one sector from the sidebar.")
    st.stop()

with st.spinner("Fetching live NSE data..."):
    sector_map = {k: SECTORS[k] for k in selected_sectors}
    all_data, all_errors, fetched_at = load_all_sectors(sector_map)

st.caption(f"Last updated: {fetched_at.strftime('%Y-%m-%d %H:%M:%S')} (next refresh in ~{REFRESH_SECONDS}s)")

any_data = False
for sector_name in selected_sectors:
    df = all_data.get(sector_name, pd.DataFrame())
    top, bottom = top_bottom(df, TOP_N)

    st.subheader(sector_name)

    if top.empty and bottom.empty:
        err = all_errors.get(sector_name, "Unknown error")
        st.info(
            f"Could not fetch live data for this sector right now. Reason: **{err}** "
            "Will retry on next refresh — open '🔧 Connection diagnostics' in the sidebar "
            "for a full connectivity trace."
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
        "coming from cloud/datacenter IPs (including Streamlit Community Cloud), even "
        "though the same site loads fine in your own browser. Run the diagnostic check "
        "in the sidebar to confirm, and see the README for fixes (proxy, local hosting, "
        "or a decoupled data-fetch job)."
    )
