import os
import json
import pandas as pd
import yfinance as yf
import gspread
import numpy as np
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 1. CONFIGURATION
# ==========================================
RAW_FNO_STOCKS = [
    "TORNTPHARM", "ASHOKLEY", "KAYNES", "INOXWIND", "GAIL", "KEI", "PREMIERENE", 
    "CGPOWER", "M&M", "BSE", "DIVISLAB", "MOTHERSON", "POWERINDIA", "GLENMARK", 
    "MAZDOCK", "DELHIVERY", "GVT&D", "TVSMOTOR", "POLYCAB", "TIINDIA", "SIEMENS", 
    "CUMMINSIND", "JSWENERGY", "ANGELONE", "COCHINSHIP", "WAAREEENER", "LAURUSLABS", 
    "MOTILALOFS", "BHARATFORG", "TATASTEEL", "LTF", "FORCEMOT", "PRESTIGE", "BPCL", 
    "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", "NBCC", "DMART", "HEROMOTOCO", 
    "KPITTECH", "RVNL", "RELIANCE", "PNB", "ZYDUSLIFE", "BHEL", "NATIONALUM", 
    "NHPC", "SRF", "JINDALSTEL", "BAJAJ-AUTO", "BEL", "TITAN", "SONACOMS", 
    "HINDZINC", "UNOMINDA", "OBEROIRLTY", "BHARTIARTL", "OFSS", "BDL", "SUPREMEIND", 
    "OIL", "SHREECEM", "NTPC", "TATAELXSI", "HINDALCO", "PETRONET", "CIPLA", 
    "MARUTI", "PAYTM", "PERSISTENT", "AMBER", "DLF", "DALBHARAT", "ULTRACEMCO", 
    "ONGC", "PHOENIXLTD", "HINDPETRO", "CAMS", "AUROPHARMA", "BIOCON", "TRENT", 
    "DRREDDY", "JSWSTEEL", "NMDC", "IOC", "UPL", "NYKAA", "LTC", "CROMPTON", 
    "INDUSTOWER", "HAVELLS", "CONCOR", "SAIL", "JUBLFOOD", "GRASIM", "PFC", 
    "ASIANPAINT", "LUPIN", "CDSL", "IREDA", "HINDUNILVR", "GODREJPROP", "KFINTECH", 
    "AMBUJACEM", "APOLLOHOSP", "HCLTECH", "POWERGRID", "RECLTD", "GODREJCP", 
    "FORTIS", "PGELAB", "SUNPHARMA", "MPHASIS", "PIIND", "COLPAL", "BLUESTARCO", 
    "VOLTAS", "TECHM", "EICHERMOT", "INDIGO", "DABUR", "NESTLEIND", "TATACONSUM", 
    "BOSCHLTD", "VEDL", "PIDILITIND", "NAUKRI", "WIPRO", "ALKEM", "ITC", "COFORGE", 
    "MARICO", "PAGEIND", "MAXHEALTH", "BRITANNIA", "INFY", "TCS", "KALYANKJIL", 
    "LODHA", "SWIGGY", "MANKIND", "DIXON", "APLAPOLLO"
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

def calculate_vwap(df):
    v = df['Volume'].values
    h = df['High'].values
    l = df['Low'].values
    c = df['Close'].values
    typical_price = (h + l + c) / 3
    return np.sum(typical_price * v) / np.sum(v)

def process_symbol(ticker):
    try:
        # Fetching 1-day interval data for EMA and Trend
        df = yf.Ticker(ticker).history(period="60d", interval="1d")
        if df.empty or len(df) < 21: return None
        
        ltp = df['Close'].iloc[-1]
        
        # 1. Breakout Status (Col M)
        prev_20_high = df['High'].tail(21).iloc[:-1].max()
        is_bo = ltp > prev_20_high
        bo_name = ticker.replace(".NS","") if is_bo else ""
        
        # 2. Trend (Col N)
        ema_50 = df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
        if ltp > ema_50 * 1.02: trend = "📈 BULLISH"
        elif ltp < ema_50 * 0.98: trend = "📉 BEARISH"
        else: trend = "↔️ SIDEWAYS"
        
        # 3. Momentum (Col O: EMA 21 + VWAP)
        ema_21 = df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
        vwap = calculate_vwap(df.tail(1)) # Approx daily VWAP
        
        momentum_name = ""
        if ltp > ema_21 and ltp > vwap and trend == "📈 BULLISH":
            momentum_name = ticker.replace(".NS","")

        return [bo_name, trend, momentum_name]
    except:
        return ["", "", ""]

def main():
    print("🚀 Scanning for M, N, O Columns...")
    results = []
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        output = list(executor.map(process_symbol, STOCKS_TICKERS))
        for res in output:
            if res: results.append(res)

    # Header and Data
    headers = ["B/O STOCKS", "TREND (STOCKS)", "MOMENTUM (EMA21+VWAP)"]
    final_data = [headers] + results

    # Updating Sheet at Col M (13th column)
    sheet = get_google_sheet()
    
    # Range M1:O... (M=13, N=14, O=15)
    end_row = len(final_data)
    sheet.update(range_name=f"M1:O{end_row}", values=final_data, value_input_option='USER_ENTERED')
    
    print(f"✅ Columns M, N, O Updated for {len(results)} stocks!")

if __name__ == "__main__":
    main()

