import os
import json
import time
import pytz
import requests
import pandas as pd
import yfinance as yf
import gspread
import numpy as np
from google.oauth2.service_account import Credentials
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 1. CONFIGURATION
# ==========================================
INDEX_TICKER = "^NSEI"
RAW_FNO_STOCKS = [
    "TORNTPHARM", "ASHOKLEY", "KAYNES", "INOXWIND", "GAIL", "KEI", "PREMIERENE", 
    "CGPOWER", "M&M", "BSE", "DIVISLAB", "MOTHERSON", "POWERINDIA", "GLENMARK", 
    "MAZDOCK", "DELHIVERY", "GVT&D", "TVSMOTOR", "POLYCAB", "TIINDIA", "SIEMENS", 
    "CUMMINSIND", "JSWENERGY", "ANGELONE", "COCHINSHIP", "WAAREEENER", "LAURUSLABS", 
    "MOTILALOFS", "BHARATFORG", "TMPVSOLAR", "TATASTEEL", "LTF", "FORCEMOT", 
    "PRESTIGE", "BPCL", "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", "NBCC", "DMART", 
    "HEROMOTOCO", "KPITTECH", "RVNL", "RELIANCE", "PNB", "ZYDUSLIFE", "BHEL", 
    "NATIONALUM", "NHPC", "SRF", "JINDALSTEL", "BAJAJ-AUTO", "BEL", "TITAN", 
    "SONACOMS", "HINDZINC", "UNOMINDA", "OBEROIRLTY", "BHARTIARTL", "OFSS", "BDL", 
    "SUPREMEIND", "OIL", "SHREECEM", "NTPC", "TATAELXSI", "HINDALCO", "PETRONET", 
    "CIPLA", "MARUTI", "PAYTM", "PERSISTENT", "AMBER", "DLF", "DALBHARAT", 
    "ULTRACEMCO", "ONGC", "PHOENIXLTD", "HINDPETRO", "CAMS", "AUROPHARMA", "BIOCON", 
    "TRENT", "DRREDDY", "JSWSTEEL", "NMDC", "IOC", "UPL", "NYKAA", "LTC", 
    "CROMPTON", "INDUSTOWER", "HAVELLS", "CONCOR", "SAIL", "JUBLFOOD", "GRASIM", 
    "PFC", "ASIANPAINT", "LUPIN", "CDSL", "IREDA", "HINDUNILVR", "GODREJPROP", 
    "KFINTECH", "AMBUJACEM", "APOLLOHOSP", "HCLTECH", "POWERGRID", "RECLTD", 
    "GODREJCP", "FORTIS", "PGELAB", "SUNPHARMA", "MPHASIS", 
    "PIIND", "COLPAL", "BLUESTARCO", "VOLTAS", "TECHM", "EICHERMOT", 
    "INDIGO", "DABUR", "NESTLEIND", "TATACONSUM", "BOSCHLTD", "VEDL", "PIDILITIND", 
    "NAUKRI", "WIPRO", "ALKEM", "ITC", "COFORGE", "MARICO", "PAGEIND", 
    "MAXHEALTH", "BRITANNIA", "INFY", "TCS", "KALYANKJIL", "LODHA", 
    "SWIGGY", "MANKIND", "DIXON", "APLAPOLLO"
]

STOCKS_TICKERS = [f"{stock}.NS" for stock in RAW_FNO_STOCKS]

def get_google_sheet():
    gcp_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    sheet_id = os.environ.get("SHEET_ID")
    creds_dict = json.loads(gcp_json_str)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    return client.open_by_key(sheet_id).sheet1

def fetch_nse_oi_data_bulk():
    headers = {'User-Agent': 'Mozilla/5.0'}
    session = requests.Session()
    oi_dict = {}
    def fetch_single(s):
        try:
            r = session.get(f"https://www.nseindia.com/api/quote-derivative?symbol={s}", timeout=5, headers=headers)
            if r.status_code == 200:
                return s, r.json()['stocks'][0]['marketDeptOrderBook']['tradeInfo'].get('pchangeinOpenInterest', 0.0)
        except: pass
        return s, 0.0
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = ex.map(fetch_single, RAW_FNO_STOCKS)
        for s, v in res: oi_dict[s] = v
    return oi_dict

def calculate_vcp(df):
    h, l, c = df['High'].values, df['Low'].values, df['Close'].values
    ranges = [(np.max(h[-p:]) - np.min(l[-p:]))/c[-1] for p in [20, 10, 5] if len(df) >= p]
    count = 1
    for i in range(len(ranges)-1):
        if ranges[i] > ranges[i+1]: count += 1
    return count

def process_symbol(ticker, df_daily, oi_val):
    ltp = round(df_daily['Close'].iloc[-1], 2)
    vol_sma = df_daily['Volume'].rolling(20).mean().iloc[-1]
    vol_spk = round(df_daily['Volume'].iloc[-1] / vol_sma, 2) if vol_sma > 0 else 0
    
    pivot = round((df_daily['High'].iloc[-2] + df_daily['Low'].iloc[-2] + df_daily['Close'].iloc[-2]) / 3, 2)
    vcp = calculate_vcp(df_daily)
    volatility = round(((df_daily['High'] - df_daily['Low']) / df_daily['Close']).tail(10).mean() * 100, 2)
    
    # Breakout & Trend
    is_bo = ltp > df_daily['High'].tail(21).iloc[:-1].max()
    status = "🚀 BREAKOUT" if is_bo else "😴 TRACKING"
    trend = "📈 BULLISH" if ltp > df_daily['Close'].ewm(span=50).mean().iloc[-1] else "📉 BEARISH"
    
    score = (vcp * 2) + (vol_spk * 3) + (10 if is_bo else 0)
    
    return {
        "TICKER": ticker.replace(".NS",""), "LTP": ltp, "HIGH": round(df_daily['High'].iloc[-1], 2),
        "LOW": round(df_daily['Low'].iloc[-1], 2), "CLOSE": ltp, "VCP": vcp, "VOLA": f"{volatility}%",
        "PIVOT": pivot, "OI": f"{oi_val}%", "SPK": f"{vol_spk}x", "SL": "2%", "TGT": "10%",
        "RR": "1:5", "STATUS": status, "TREND": trend, "SCORE": score
    }

def main():
    oi_data = fetch_nse_oi_data_bulk()
    processed = []
    
    def fetch_and_proc(t):
        try:
            df = yf.Ticker(t).history(period="65d")
            if not df.empty: return process_symbol(t, df, oi_data.get(t.replace(".NS",""), 0))
        except: return None

    with ThreadPoolExecutor(max_workers=15) as ex:
        results = ex.map(fetch_and_proc, STOCKS_TICKERS)
        for r in results: 
            if r: processed.append(r)

    # Hierarchy Sorting
    processed.sort(key=lambda x: x['SCORE'], reverse=True)

    headers = ["Ticker", "LTP", "HIGH", "LOW", "CLOSE", "VCP Count", "Volatility %", "Pivot", "OI % Chg", "Vol Spike", "SL", "Target", "RR", "Breakout Status", "Current Trend", "⭐ LIVE ENTRIES"]
    final_data = [headers]
    
    for i, s in enumerate(processed):
        # Last column only for Rank 1-3 if they are breakouts
        rank_val = f"RANK {i+1}" if i < 3 and "BREAKOUT" in s['STATUS'] else "-"
        final_data.append([
            s["TICKER"], s["LTP"], s["HIGH"], s["LOW"], s["CLOSE"], s["VCP"],
            s["VOLA"], s["PIVOT"], s["OI"], s["SPK"], s["SL"], s["TGT"], 
            s["RR"], s["STATUS"], s["TREND"], rank_val
        ])

    sheet = get_google_sheet()
    sheet.clear()
    sheet.update(range_name=f"A1:P{len(final_data)}", values=final_data, value_input_option='USER_ENTERED')
    print("✅ Sheet Updated Successfully!")

if __name__ == "__main__":
    main()

