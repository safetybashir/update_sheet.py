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
    print("📡 Fetching OI Data...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    session = requests.Session()
    oi_dict = {}
    
    def fetch_single(s):
        try:
            r = session.get(f"https://www.nseindia.com/api/quote-derivative?symbol={s}", timeout=5, headers=headers)
            if r.status_code == 200:
                oi_val = float(r.json()['stocks'][0]['marketDeptOrderBook']['tradeInfo'].get('pchangeinOpenInterest', 0.0))
                return s, round(oi_val, 2)
        except: pass
        return s, 0.0

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_single, RAW_FNO_STOCKS))
        for s, v in results:
            oi_dict[s] = v
    return oi_dict

def calculate_vcp_count(df):
    """Calculate VCP Contraction Count (1-5 scale, NOT percentage)"""
    if len(df) < 20:
        return 1
    
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    
    # Calculate ranges for different periods
    ranges = []
    for period in [20, 10, 5, 3]:
        if len(df) >= period:
            range_val = (np.max(highs[-period:]) - np.min(lows[-period:])) / closes[-1]
            ranges.append(range_val)
    
    # Count contractions
    count = 1
    for i in range(len(ranges) - 1):
        if ranges[i] > ranges[i + 1]:
            count += 1
    
    return min(count, 5)

def process_symbol(ticker, df_daily, oi_val):
    """Process each stock and return all metrics"""
    try:
        ltp = round(float(df_daily['Close'].iloc[-1]), 2)
        high = round(float(df_daily['High'].iloc[-1]), 2)
        low = round(float(df_daily['Low'].iloc[-1]), 2)
        
        # Volume Spike
        vol_sma = df_daily['Volume'].rolling(20).mean().iloc[-1]
        vol_spike = round(float(df_daily['Volume'].iloc[-1]) / vol_sma, 2) if vol_sma > 0 else 0
        
        # Pivot
        pivot = round((df_daily['High'].iloc[-2] + df_daily['Low'].iloc[-2] + df_daily['Close'].iloc[-2]) / 3, 2)
        
        # VCP Count (NOT percentage)
        vcp_count = calculate_vcp_count(df_daily)
        
        # Volatility
        volatility = round(((df_daily['High'] - df_daily['Low']) / df_daily['Close']).tail(10).mean() * 100, 2)
        
        # Breakout Logic
        prev_20_high = float(df_daily['High'].tail(21).iloc[:-1].max())
        is_breakout = ltp > prev_20_high
        status = "🚀 BREAKOUT" if is_breakout else "😴 TRACKING"
        
        # Trend (50 EMA)
        ema_50 = df_daily['Close'].ewm(span=50).mean().iloc[-1]
        trend = "📈 BULLISH" if ltp > ema_50 else "📉 BEARISH"
        
        # Score
        score = (vcp_count * 2) + (vol_spike * 3) + (15 if is_breakout else 0)
        
        return {
            "TICKER": ticker.replace(".NS", ""),
            "LTP": ltp,
            "HIGH": high,
            "LOW": low,
            "CLOSE": ltp,
            "VCP_COUNT": int(vcp_count),  # Integer value (1-5), NOT percentage
            "VOLATILITY": f"{volatility:.2f}%",
            "PIVOT": pivot,
            "OI_CHG": f"{oi_val:.2f}%",
            "VOL_SPIKE": f"{vol_spike:.2f}x",
            "SL": "2%",
            "TARGET": "10%",
            "RR": "1:5",
            "STATUS": status,
            "TREND": trend,
            "IS_BREAKOUT": is_breakout,
            "SCORE": score
        }
    except Exception as e:
        return None

def main():
    print("🚀 Starting Audit & Scanner...")
    
    oi_data = fetch_nse_oi_data_bulk()
    processed_list = []
    
    def fetch_and_process(ticker):
        try:
            df = yf.Ticker(ticker).history(period="65d")
            if not df.empty and len(df) >= 25:
                clean_sym = ticker.replace(".NS", "")
                oi_val = oi_data.get(clean_sym, 0.0)
                result = process_symbol(ticker, df, oi_val)
                return result
        except Exception:
            pass
        return None

    print("⚡ Processing all stocks...")
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(fetch_and_process, STOCKS_TICKERS)
        for r in results:
            if r:
                processed_list.append(r)

    # Sort by Score (Hierarchy)
    processed_list.sort(key=lambda x: (x['IS_BREAKOUT'], x['SCORE']), reverse=True)

    # Filter BREAKOUT stocks only
    breakout_stocks = [s for s in processed_list if s['IS_BREAKOUT']]
    bullish_stocks = [s for s in processed_list if "BULLISH" in s['TREND']]
    
    # Top 5 Rank 1 stocks (breakout)
    rank_1_stocks = breakout_stocks[:5]
    
    print(f"📊 Total Stocks: {len(processed_list)}")
    print(f"🚀 Breakout Stocks: {len(breakout_stocks)}")
    print(f"📈 Bullish Stocks: {len(bullish_stocks)}")
    print(f"⭐ RANK 1 Stocks: {len(rank_1_stocks)}")

    # ==========================================
    # BUILD FINAL SHEET
    # ==========================================
    headers = [
        "Ticker", "LTP", "HIGH", "LOW", "CLOSE", "VCP Count", "Volatility %", 
        "Pivot", "OI % Chg", "Vol Spike", "SL", "Target", "RR", "Breakout Status", 
        "Current Trend", "B/O STOCKS", "TREND", "⭐ RANK 1 STOCKS"
    ]
    
    final_data = [headers]
    
    for i, stock in enumerate(processed_list):
        # Column N: B/O STOCKS (Breakout stocks ke naam)
        bo_col = stock['TICKER'] if stock['IS_BREAKOUT'] else ""
        
        # Column O: TREND (Bullish/Bearish)
        trend_col = stock['TREND'] if stock['IS_BREAKOUT'] else ""
        
        # Column P: RANK 1 (Top 5 breakout stocks with rank)
        rank_col = ""
        if stock in rank_1_stocks:
            rank_idx = rank_1_stocks.index(stock) + 1
            rank_col = f"RANK {rank_idx}: {stock['TICKER']}"
        
        final_data.append([
            stock["TICKER"],
            stock["LTP"],
            stock["HIGH"],
            stock["LOW"],
            stock["CLOSE"],
            stock["VCP_COUNT"],  # Now showing 1, 2, 3, 4, 5 (not percentage)
            stock["VOLATILITY"],
            stock["PIVOT"],
            stock["OI_CHG"],
            stock["VOL_SPIKE"],
            stock["SL"],
            stock["TARGET"],
            stock["RR"],
            stock["STATUS"],
            stock["TREND"],
            bo_col,  # Column N
            trend_col,  # Column O
            rank_col  # Column P
        ])

    # Update Google Sheet
    print("📤 Updating Google Sheet...")
    sheet = get_google_sheet()
    sheet.clear()
    sheet.update(
        range_name=f"A1:R{len(final_data)}", 
        values=final_data, 
        value_input_option='USER_ENTERED'
    )
    
    print("✅ Audit Complete! Sheet Updated Successfully!")
    print(f"\n📋 Summary:")
    print(f"   • Total Stocks Scanned: {len(processed_list)}")
    print(f"   • Breakout Stocks (B/O): {len(breakout_stocks)}")
    print(f"   • Bullish Trend: {len(bullish_stocks)}")
    print(f"   • RANK 1 Stocks: {len(rank_1_stocks)}")
    if rank_1_stocks:
        print(f"\n⭐ TOP RANK 1 STOCKS:")
        for idx, s in enumerate(rank_1_stocks, 1):
            print(f"   {idx}. {s['TICKER']} - {s['STATUS']} ({s['TREND']})")

if __name__ == "__main__":
    main()
