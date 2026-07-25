NSE Sector Heatmap Dashboard
A Streamlit dashboard that mirrors the NSE sector heatmap
(https://www.nseindia.com/market-data/live-market-indices/heatmap) but drills into
each of the 17 sector indices and shows the Top 5 gainers and Top 5 losers
for that sector, refreshing automatically every 60 seconds.
Sectors covered: NIFTY AUTO, NIFTY BANK, NIFTY FINANCIAL SERVICES,
NIFTY FINANCIAL SERVICES 25/50, NIFTY FMCG, NIFTY IT, NIFTY MEDIA, NIFTY METAL,
NIFTY PHARMA, NIFTY PSU BANK, NIFTY REALTY, NIFTY PRIVATE BANK,
NIFTY HEALTHCARE INDEX, NIFTY CONSUMER DURABLES, NIFTY OIL & GAS,
NIFTY MIDSMALL HEALTHCARE, NIFTY CHEMICALS.
How it works
`app.py` hits NSE's public JSON endpoint
`https://www.nseindia.com/api/equity-stockIndices?index=<SECTOR>` for each sector.
NSE requires a browser-like session (cookies from a normal page load) before the
API responds — the app handles this automatically and retries with a fresh
session if a request fails.
Data is cached for 60 seconds (`st.cache_data(ttl=60)`), and the page auto-reloads
every 60 seconds via a `<meta http-equiv="refresh">` tag, so the dashboard stays live
without any manual action.
For each sector you get: a heatmap-style tile view (green = gainers, red = losers,
shade = magnitude) or a horizontal bar chart view — toggle in the sidebar.
Run locally
```bash
git clone <your-repo-url>
cd nse-sector-dashboard
pip install -r requirements.txt
streamlit run app.py
```
Open the URL Streamlit prints (usually http://localhost:8501).
Push to GitHub
```bash
cd nse-sector-dashboard
git init
git add .
git commit -m "NSE sector heatmap dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```
Deploy on Streamlit Community Cloud (free, auto-refreshing)
Push the repo to GitHub as above.
Go to https://share.streamlit.io and sign in with GitHub.
Click New app, pick your repo/branch, and set the main file path to `app.py`.
Click Deploy. Streamlit Cloud will install `requirements.txt` and host the app
at a public URL, e.g. `https://your-app.streamlit.app`.
The app already auto-refreshes every 60 seconds in the browser — no extra
configuration needed once deployed.
⚠️ Why NSE data may show "could not fetch" on a server, even though it loads fine in your browser
This is expected and it is not a bug in the app — it's how NSE's bot protection
(Akamai) works:
TLS fingerprinting. Every HTTP client (Chrome, Python's `requests`, curl, etc.)
has a distinct "signature" in how it negotiates TLS, independent of headers or
cookies. Your browser's signature looks legitimate; a plain Python `requests`
signature does not, and NSE can reject it before even reading your headers.
→ Fix built into this app: it uses `curl_cffi`
to impersonate a real Chrome TLS fingerprint automatically. This alone resolves
most "could not fetch" cases. Just make sure `requirements.txt` (which includes
`curl_cffi`) is installed — the app falls back to plain `requests` only if
`curl_cffi` fails to install.
IP reputation. NSE also blocks/rate-limits known datacenter IP ranges
(AWS, GCP, Azure, and some Streamlit Community Cloud regions), regardless of TLS
fingerprint. Your home/office browser has a normal residential/corporate IP, which
is why the site "just works" for you directly.
→ Fix: set an HTTP(S) proxy with a non-datacenter exit IP. In your deployed
app's Settings → Secrets, add:
```toml
   NSE_PROXY = "http://user:pass@proxy-host:port"
   ```
The app automatically picks this up (see `_get_proxies()` in `app.py`). Any
residential/rotating proxy provider (e.g. Bright Data, Smartproxy, ScraperAPI, Oxylabs)
works here — a VPN is not usable server-side for this.
How to check what's actually happening
Open the sidebar → 🔧 Connection diagnostics → Run diagnostic check. This
shows, step by step:
Which HTTP engine is active (`curl_cffi` with Chrome impersonation, or plain `requests`)
The HTTP status code for the homepage, the heatmap page, and the API call itself
Whether the response was valid JSON or a block/captcha page
Each sector's "could not fetch" message also now shows the specific reason
(HTTP 403, timeout, rate limit, etc.) instead of a generic error, so you can tell at a
glance whether it's a fingerprint issue, an IP block, or a rate limit.
If it still doesn't work after both fixes
Confirm `curl_cffi` actually installed on your host (some minimal Docker/cloud
images lack build tools it needs — check your deploy logs).
Add a residential/rotating proxy via `NSE_PROXY` as above.
As a fully decoupled alternative, run the scraper on your own machine or a small VPS
(which almost always works out of the box) and have it write results to a JSON file/S3
bucket/Gist every minute; point the Streamlit app at that instead of hitting NSE directly.
This removes NSE availability from the critical path of your dashboard entirely.
Customizing
Change sectors: edit the `SECTORS` dict at the top of `app.py`.
Change Top N: edit `TOP_N` (default 5).
Change refresh interval: edit `REFRESH_SECONDS` (default 60).
Tile color thresholds: edit the `tile_color()` function.
Project structure
```
.
├── app.py              # Streamlit app (all logic + UI)
├── requirements.txt    # Python dependencies
├── README.md
└── .gitignore
```
