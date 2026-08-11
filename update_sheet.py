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
    "MOTILALOFS", "BHARATFORG", "TMPVSOLAR", "IND", "TATASTEEL", "LTF", "FORCEMOT",
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

# ==========================================
# 2. GOOGLE SHEET CONNECTION
# ==========================================
def get_google_sheet():
    gcp_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    sheet_id = os.environ.get("SHEET_ID")

    if not gcp_json_str or not sheet_id:
        raise ValueError("Missing environment variables!")

    creds_dict = json.loads(gcp_json_str)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    return client.open_by_key(sheet_id).sheet1

# ==========================================
# 3. NSE OI FETCH
# ==========================================
def fetch_nse_oi_data_bulk():
    print("📡 Fetching OI data from NSE...")
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com'
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        session.get("https://www.nseindia.com", timeout=5)
    except Exception:
        pass

    oi_dict = {}

    def fetch_single_oi(symbol):
        url = f"https://www.nseindia.com/api/quote-derivative?symbol={symbol}"
        try:
            resp = session.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                stocks_data = data.get("stocks", [])
                if stocks_data:
                    trade_info = stocks_data[0]["marketDeptOrderBook"]["tradeInfo"]
                    p_change_oi = float(trade_info.get("pchangeinOpenInterest", 0.0))
                    return symbol, round(p_change_oi, 2)
        except Exception:
            pass
        return symbol, 0.0

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(fetch_single_oi, RAW_FNO_STOCKS)
        for symbol, oi_pct in results:
            oi_dict[symbol] = oi_pct

    return oi_dict

# ==========================================
# 4. YFINANCE FETCH
# ==========================================
def fetch_single_ticker(ticker):
    try:
        t = yf.Ticker(ticker)
        df_daily = t.history(period="65d", interval="1d")
        df_15m = t.history(period="2d", interval="15m")
        if df_daily is not None and not df_daily.empty:
            return ticker, df_daily, df_15m
    except Exception:
        pass
    return ticker, None, None

def fetch_data_parallel(tickers):
    all_data = {}
    print(f"⚡ Fetching {len(tickers)} tickers...")
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(fetch_single_ticker, tickers)
        for ticker, df_daily, df_15m in results:
            if df_daily is not None and not df_daily.empty:
                all_data[ticker] = {
                    "daily": df_daily,
                    "intraday": df_15m
                }
    return all_data

# ==========================================
# 5. CALCULATION HELPERS
# ==========================================
def calculate_vcp_count(df):
    if len(df) < 20:
        return 1

    closes = df["Close"].values
    highs = df["High"].values
    lows = df["Low"].values

    periods = [20, 10, 5, 3]
    ranges = []

    for p in periods:
        if len(df) >= p:
            r = (np.max(highs[-p:]) - np.min(lows[-p:])) / closes[-1] * 100
            ranges.append(r)

    count = 1
    for i in range(len(ranges) - 1):
        if ranges[i] > ranges[i + 1]:
            count += 1

    return min(count, 5)

def calculate_volatility_pct(df):
    if len(df) < 10:
        return 0.0
    intraday_range = ((df["High"] - df["Low"]) / df["Close"]) * 100
    return round(float(intraday_range.tail(10).mean()), 2)

def calculate_pivot(df):
    if len(df) < 2:
        return 0.0
    prev_high = float(df["High"].iloc[-2])
    prev_low = float(df["Low"].iloc[-2])
    prev_close = float(df["Close"].iloc[-2])
    return round((prev_high + prev_low + prev_close) / 3, 2)

def calculate_volume_spike(df):
    if len(df) < 20:
        return 0.0
    vol_sma20 = df["Volume"].rolling(20).mean().iloc[-1]
    curr_vol = float(df["Volume"].iloc[-1])
    if pd.isna(vol_sma20) or vol_sma20 <= 0:
        return 0.0
    return round(curr_vol / vol_sma20, 2)

def calculate_breakout_status(df, ltp, vol_spike):
    if len(df) < 21:
        return "😴 TRACKING"

    prev_20_high = float(df["High"].tail(21).iloc[:-1].max())
    prev_20_low = float(df["Low"].tail(21).iloc[:-1].min())

    if ltp > prev_20_high and vol_spike >= 1.5:
        return "🚀 BREAKOUT"
    elif ltp < prev_20_low and vol_spike >= 1.5:
        return "📉 BREAKDOWN"
    elif vol_spike >= 2.0:
        return "👀 VOL SPIKE"
    return "😴 TRACKING"

def calculate_trend(df, ltp):
    if len(df) < 50:
        return "NEUTRAL"
    
    ema_50 = df["Close"].ewm(span=50, adjust=False).mean().iloc[-1]
    
    if ltp > ema_50:
        return "📈 BULLISH"
    elif ltp < ema_50:
        return "📉 BEARISH"
    return "↔️ NEUTRAL"

def calculate_score(vcp_count, vol_spike, breakout_status, ltp, pivot):
    score = 0
    score += vcp_count * 2
    score += vol_spike * 3

    if "BREAKOUT" in breakout_status:
        score += 10
    elif "BREAKDOWN" in breakout_status:
        score += 5
    
    if ltp > pivot:
        score += 2

    return round(score, 2)

# ==========================================
# 6. PROCESS SYMBOL DATA
# ==========================================
def process_symbol_data(data, symbol, live_oi_pct):
    df = data["daily"].dropna().copy()

    if len(df) < 25:
        return None

    ticker_name = symbol.replace(".NS", "")

    # ❌ FIX: Make sure HIGH, LOW, CLOSE are numeric values, not percentages
    high = round(float(df["High"].iloc[-1]), 2)
    low = round(float(df["Low"].iloc[-1]), 2)
    close = round(float(df["Close"].iloc[-1]), 2)
    ltp = close

    vcp_count = calculate_vcp_count(df)
    volatility_pct = calculate_volatility_pct(df)
    pivot = calculate_pivot(df)
    vol_spike = calculate_volume_spike(df)
    breakout_status = calculate_breakout_status(df, ltp, vol_spike)
    trend = calculate_trend(df, ltp)

    oi_pct = live_oi_pct if live_oi_pct is not None else 0.0
    oi_str = f"{oi_pct:.2f}%"

    score = calculate_score(vcp_count, vol_spike, breakout_status, ltp, pivot)

    # Rank logic: Only BREAKOUT status gets RANK 1
    rank = 1 if "BREAKOUT" in breakout_status else 0

    return {
        "Ticker": ticker_name,
        "LTP": ltp,
        "HIGH": high,
        "LOW": low,
        "CLOSE": close,
        "VCP_Count": int(vcp_count),
        "Volatility_Pct": f"{volatility_pct:.2f}%",
        "Pivot": round(pivot, 2),
        "OI_Chg": oi_str,
        "Vol_Spike": f"{vol_spike:.2f}x",
        "SL": "2%",
        "Target": "10%",
        "RR": "1:5",
        "Breakout_Status": breakout_status,
        "Trend": trend,
        "Score": score,
        "Rank": rank
    }

# ==========================================
# 7. MAIN
# ==========================================
def main():
    start_time = time.time()
    print("🚀 Starting FnO Scanner Engine...")

    ist = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(ist).strftime("%H:%M:%S")

    # Fetch OI Data
    oi_data = fetch_nse_oi_data_bulk()

    # Fetch Price Data
    all_data = fetch_data_parallel(ALL_TICKERS)

    processed_list = []

    for symbol, data in all_data.items():
        if symbol == INDEX_TICKER:
            continue

        clean_symbol = symbol.replace(".NS", "")
        live_oi_pct = oi_data.get(clean_symbol, 0.0)
        result = process_symbol_data(data, symbol, live_oi_pct)
        if result:
            processed_list.append(result)

    # ❌ CRITICAL FIX: Filter ONLY RANK 1 stocks
    rank_1_stocks = [s for s in processed_list if s["Rank"] == 1]
    
    # Sort by score (descending)
    rank_1_stocks.sort(key=lambda x: x["Score"], reverse=True)

    # ==========================================
    # PART A: LEFT SIDE - ALL STOCKS (A to N)
    # ==========================================
    headers_left = [
        "Ticker", "LTP", "HIGH", "LOW", "CLOSE", "VCP Count",
        "Volatility %", "Pivot", "OI % Chg", "Vol Spike", "SL", "Target", "RR", "Breakout Status"
    ]

    # Sort all stocks by score for general reference
    processed_list.sort(key=lambda x: x["Score"], reverse=True)
    
    rows_left = [headers_left]
    for item in processed_list:
        rows_left.append([
            item["Ticker"],
            item["LTP"],
            item["HIGH

