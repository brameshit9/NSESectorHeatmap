# NSE Sector Heatmap Dashboard

A Streamlit dashboard that mirrors the NSE sector heatmap
(https://www.nseindia.com/market-data/live-market-indices/heatmap) but drills into
**each of the 17 sector indices** and shows the **Top 5 gainers** and **Top 5 losers**
for that sector, refreshing automatically every 60 seconds.

Sectors covered: NIFTY AUTO, NIFTY BANK, NIFTY FINANCIAL SERVICES,
NIFTY FINANCIAL SERVICES 25/50, NIFTY FMCG, NIFTY IT, NIFTY MEDIA, NIFTY METAL,
NIFTY PHARMA, NIFTY PSU BANK, NIFTY REALTY, NIFTY PRIVATE BANK,
NIFTY HEALTHCARE INDEX, NIFTY CONSUMER DURABLES, NIFTY OIL & GAS,
NIFTY MIDSMALL HEALTHCARE, NIFTY CHEMICALS.

## How it works

- `app.py` hits NSE's public JSON endpoint
  `https://www.nseindia.com/api/equity-stockIndices?index=<SECTOR>` for each sector.
- NSE requires a browser-like session (cookies from a normal page load) before the
  API responds — the app handles this automatically and retries with a fresh
  session if a request fails.
- Data is cached for 60 seconds (`st.cache_data(ttl=60)`), and the page auto-reloads
  every 60 seconds via a `<meta http-equiv="refresh">` tag, so the dashboard stays live
  without any manual action.
- For each sector you get: a heatmap-style tile view (green = gainers, red = losers,
  shade = magnitude) or a horizontal bar chart view — toggle in the sidebar.

## Run locally

```bash
git clone <your-repo-url>
cd nse-sector-dashboard
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

## Push to GitHub

```bash
cd nse-sector-dashboard
git init
git add .
git commit -m "NSE sector heatmap dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## Deploy on Streamlit Community Cloud (free, auto-refreshing)

1. Push the repo to GitHub as above.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **New app**, pick your repo/branch, and set the main file path to `app.py`.
4. Click **Deploy**. Streamlit Cloud will install `requirements.txt` and host the app
   at a public URL, e.g. `https://your-app.streamlit.app`.
5. The app already auto-refreshes every 60 seconds in the browser — no extra
   configuration needed once deployed.

## ⚠️ Important note about NSE and cloud hosting

NSE's website actively rate-limits and sometimes blocks requests coming from
datacenter/cloud IP ranges (this can include some Streamlit Cloud regions, AWS, GCP,
etc.), even though the same code works fine from a home/office internet connection.
If sectors show "Could not fetch live data" after deploying:

- It usually still works intermittently — the 60s auto-refresh will keep retrying.
- Running the app on your own machine, a VPS with a residential-style IP, or behind
  a proxy/VPN typically resolves it.
- As a more robust alternative, you can swap the fetch logic to use the
  [`nsepython`](https://pypi.org/project/nsepython/) library, which is actively
  maintained to work around NSE's anti-bot measures, or add a small caching proxy
  (e.g. a scheduled GitHub Action that fetches data every minute and writes it to a
  JSON file/S3 bucket that the Streamlit app reads from, decoupling the app from
  NSE's rate limits entirely).

## Customizing

- **Change sectors**: edit the `SECTORS` dict at the top of `app.py`.
- **Change Top N**: edit `TOP_N` (default 5).
- **Change refresh interval**: edit `REFRESH_SECONDS` (default 60).
- **Tile color thresholds**: edit the `tile_color()` function.

## Project structure

```
.
├── app.py              # Streamlit app (all logic + UI)
├── requirements.txt    # Python dependencies
├── README.md
└── .gitignore
```
