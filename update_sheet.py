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
ALL_TICKERS = [INDEX_TICKER] + STOCKS_TICKERS

def get_google_sheet():
    gcp_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    sheet_id = os.environ.get("SHEET_ID")
    if not gcp_json_str or not sheet_id:
        raise ValueError("❌ Missing Environment Variables!")
    creds_dict = json.loads(gcp_json_str)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    return client.open_by_key(sheet_id).sheet1

# ==========================================
# 2. DATA UTILITIES
# ==========================================
def calculate_vcp_count(df):
    """Calculates volatility contraction intensity (1-5)"""
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    
    ranges = []
    periods = [20, 10, 5, 3]
    for p in periods:
        r = (np.max(highs[-p:]) - np.min(lows[-p:])) / closes[-1]
        ranges.append(r)
    
    count = 1
    for i in range(len(ranges)-1):
        if ranges[i] > ranges[i+1]:
            count += 1
    return count

def fetch_nse_oi_data_bulk():
    headers = {'User-Agent': 'Mozilla/5.0'}
    session = requests.Session()
    oi_dict = {}
    
    def fetch_single_oi(symbol):
        url = f"https://www.nseindia.com/api/quote-derivative?symbol={symbol}"
        try:
            resp = session.get(url, timeout=5, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                p_change_oi = float(data['stocks'][0]['marketDeptOrderBook']['tradeInfo'].get('pchangeinOpenInterest', 0.0))
                return symbol, round(p_change_oi, 2)
        except: pass
        return symbol, 0.0

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_single_oi, RAW_FNO_STOCKS)
        for sym, val in results: oi_dict[sym] = val
    return oi_dict

def fetch_single_ticker(ticker):
    try:
        t = yf.Ticker(ticker)
        df_daily = t.history(period="65d", interval="1d")
        df_15m = t.history(period="2d", interval="15m")
        if not df_daily.empty: return ticker, df_daily, df_15m
    except: pass
    return ticker, None, None

# ==========================================
# 3. PROCESSING LOGIC
# ==========================================
def process_symbol_data(data, symbol, live_oi_pct):
    df = data["daily"].dropna()
    df_15m = data["intraday"]
    if len(df) < 30: return None

    ltp = round(df['Close'].iloc[-1], 2)
    high = round(df['High'].iloc[-1], 2)
    low = round(df['Low'].iloc[-1], 2)
    
    # 1. VCP & Volatility
    vcp_count = calculate_vcp_count(df)
    volatility = round(((df['High'] - df['Low']) / df['Close']).tail(10).mean() * 100, 2)
    
    # 2. Volume Spike
    vol_sma = df['Volume'].rolling(20).mean().iloc[-1]
    curr_vol = df['Volume'].iloc[-1]
    vol_spike = round(curr_vol / vol_sma, 2) if vol_sma > 0 else 0

    # 3. Pivot, SL, Target
    pivot = round((df['High'].iloc[-2] + df['Low'].iloc[-2] + df['Close'].iloc[-2]) / 3, 2)
    sl = round(ltp * 0.98, 2)
    target = round(ltp * 1.10, 2)
    
    # 4. Breakout Status
    prev_20_high = df['High'].tail(21).iloc[:-1].max()
    status = "🚀 BREAKOUT" if ltp > prev_20_high else ("😴 TRACKING" if vol_spike < 1.5 else "👀 WATCH VOL")
    
    # 5. Momentum Rank Logic
    m_score = (vcp_count * 2) + (vol_spike * 3) + (1 if ltp > pivot else 0)
    
    return {
        "Ticker": symbol.replace(".NS", ""),
        "HIGH": high,
        "LOW": low,
        "CLOSE": ltp,
        "VCP_Count": vcp_count,
        "Vol_Pct": volatility,
        "Pivot": pivot,
        "LTP": ltp,
        "OI_Chg": f"{live_oi_pct}%",
        "Vol_Spike": f"{vol_spike}x",
        "SL": "2%",
        "Target": "10%",
        "RR": "1:5",
        "Status": status,
        "Score": m_score
    }

def main():
    print("🚀 Starting Super Scanner Engine...")
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).strftime("%H:%M:%S")

    oi_data = fetch_nse_oi_data_bulk()
    
    all_data = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(fetch_single_ticker, ALL_TICKERS)
        for t, d, i in results:
            if d is not None: all_data[t] = {"daily": d, "intraday": i}

    processed_list = []
    for ticker, data in all_data.items():
        if ticker == INDEX_TICKER: continue
        res = process_symbol_data(data, ticker, oi_data.get(ticker.replace(".NS",""), 0))
        if res: processed_list.append(res)

    # Sorting by Score (Rank 1 stocks top par aayenge)
    processed_list.sort(key=lambda x: x['Score'], reverse=True)

    # Final Matrix building
    headers = ["Ticker", "HIGH", "LOW", "CLOSE", "VCP Count", "Volatility %", "Pivot", "LTP", "OI % Chg", "Vol Spike", "SL", "Target", "RR", "Status", "Live Entry Rank"]
    final_rows = [headers]
    
    for i, item in enumerate(processed_list):
        rank = "⭐ RANK 1" if i < 3 and "BREAKOUT" in item['Status'] else "-"
        final_rows.append([
            item["Ticker"], item["HIGH"], item["LOW"], item["CLOSE"], item["VCP_Count"],
            item["Vol_Pct"], item["Pivot"], item["LTP"], item["OI_Chg"], item["Vol_Spike"],
            item["SL"], item["Target"], item["RR"], item["Status"], rank
        ])

    print("📊 Updating Sheet...")
    sheet = get_google_sheet()
    sheet.clear()
    sheet.update(range_name=f"A1:O{len(final_rows)}", values=final_rows, value_input_option='USER_ENTERED')
    print(f"✅ Updated at {current_time}!")

if __name__ == "__main__":
    main()

