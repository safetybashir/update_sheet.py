import os
import json
import time
from datetime import datetime
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION (Sheet ID & Tabs) ---
SPREADSHEET_ID = "1Tkd_sn6Fk6i702nTHT3rm3efgZZFcTUPNmnTUJeABm0"
TAB_SWING = "Daily_5EMA_Swing"
TAB_INTRADAY = "Intraday_15Min"

TARGET_UNIVERSE = [
    "TATASTEEL",
    "RELIANCE",
    "INFY",
    "TCS",
    "SUNPHARMA",
    "TATAMOTORS",
    "AXISBANK"
]

RSI_PERIOD = 14
EMA_PERIOD = 5

def get_gspread_client():
    """
    GitHub Secrets (GCP_CREDENTIALS_JSON) ya local file se gspread client authenticate karne ke liye.
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    if "GCP_CREDENTIALS_JSON" in os.environ and os.environ["GCP_CREDENTIALS_JSON"].strip():
        raw_json = os.environ["GCP_CREDENTIALS_JSON"].strip()
        try:
            creds_dict = json.loads(raw_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(f"❌ Error in 'GCP_CREDENTIALS_JSON' secret: {e}")
    elif os.path.exists("credentials.json"):
        try:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(f"❌ Invalid local 'credentials.json': {e}")
    else:
        raise FileNotFoundError("Neither 'GCP_CREDENTIALS_JSON' secret nor 'credentials.json' found.")

def fetch_data(ticker, interval, period):
    try:
        df = yf.download(ticker + ".NS", period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None

def calculate_indicators(df):
    if df is None or len(df) < 20:
        return None
    
    # 5 EMA Calculation
    df['EMA_5'] = df['Close'].ewm(span=EMA_PERIOD, adjust=False).mean()
    
    # RSI Calculation (14 Period)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Alert Candle Logic (Separation Check)
    df['Bullish_Alert'] = (df['Low'] > df['EMA_5']) & (df['Close'] > df['Open'])
    df['Bearish_Alert'] = (df['High'] < df['EMA_5']) & (df['Close'] < df['Open'])
    
    return df

def run_scanner():
    print("--- Starting 5 EMA + RSI Reversal Scanner ---")
    
    swing_results = []
    intraday_results = []
    
    for stock in TARGET_UNIVERSE:
        print(f"Scanning {stock}...")
        
        # 1. Daily Timeframe Scan (Swing)
        df_daily = fetch_data(stock, interval="1d", period="3mo")
        df_daily = calculate_indicators(df_daily)
        if df_daily is not None and not df_daily.empty:
            latest_daily = df_daily.iloc[-1]
            if latest_daily['Bullish_Alert'] or latest_daily['Bearish_Alert']:
                swing_results.append({
                    'Stock': stock,
                    'Timeframe': 'Daily',
                    'Close': round(float(latest_daily['Close']), 2),
                    'RSI': round(float(latest_daily['RSI']), 2),
                    'Signal': 'Bullish Reversal' if latest_daily['Bullish_Alert'] else 'Bearish Reversal',
                    'Alert_High': round(float(latest_daily['High']), 2),
                    'Alert_Low': round(float(latest_daily['Low']), 2)
                })
        
        # 2. 15-Minute Timeframe Scan (Intraday)
        df_15m = fetch_data(stock, interval="15m", period="5d")
        df_15m = calculate_indicators(df_15m)
        if df_15m is not None and not df_15m.empty:
            latest_15m = df_15m.iloc[-1]
            if latest_15m['Bullish_Alert'] or latest_15m['Bearish_Alert']:
                intraday_results.append({
                    'Stock': stock,
                    'Timeframe': '15Min',
                    'Close': round(float(latest_15m['Close']), 2),
                    'RSI': round(float(latest_15m['RSI']), 2),
                    'Signal': 'Bullish Reversal' if latest_15m['Bullish_Alert'] else 'Bearish Reversal',
                    'Alert_High': round(float(latest_15m['High']), 2),
                    'Alert_Low': round(float(latest_15m['Low']), 2)
                })
                
        time.sleep(0.5)
        
    print(f"Scan Complete. Daily Setups: {len(swing_results)}, 15M Setups: {len(intraday_results)}")
    update_google_sheet(swing_results, intraday_results)

def update_google_sheet(swing_data, intraday_data):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # IST Timestamp generate karna
        ist = pytz.timezone("Asia/Kolkata")
        current_time_str = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
        
        # --- Update Daily Swing Tab ---
        tab_swing = sheet.worksheet(TAB_SWING)
        tab_swing.clear()
        
        swing_header_row = [["5 EMA Swing Scanner Report", f"Last Updated: {current_time_str} IST"]]
        if swing_data:
            df_s = pd.DataFrame(swing_data)
            swing_payload = swing_header_row + [[]] + [df_s.columns.values.tolist()] + df_s.values.tolist()
            tab_swing.update('A1', swing_payload)
        else:
            tab_swing.update('A1', swing_header_row + [[]] + [["Status"], ["No Daily Alert Setups Today"]])
            
        # --- Update 15M Intraday Tab ---
        tab_intra = sheet.worksheet(TAB_INTRADAY)
        tab_intra.clear()
        
        intra_header_row = [["15-Min Intraday Scanner Report", f"Last Updated: {current_time_str} IST"]]
        if intraday_data:
            df_i = pd.DataFrame(intraday_data)
            intra_payload = intra_header_row + [[]] + [df_i.columns.values.tolist()] + df_i.values.tolist()
            tab_intra.update('A1', intra_payload)
        else:
            tab_intra.update('A1', intra_header_row + [[]] + [["Status"], ["No 15M Alert Setups Active"]])
            
        print(f"✅ Google Sheet successfully updated with timestamp: {current_time_str}!")
    except Exception as e:
        print(f"❌ Google Sheet Update Error: {e}")
        raise e

if __name__ == "__main__":
    run_scanner()
