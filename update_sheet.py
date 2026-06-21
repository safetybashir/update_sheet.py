# update_sheet.py – AI Bro Scanner (Super Debugger Mode)
import os
import json
import gspread
import yfinance as yf
import pytz
import pandas as pd
import numpy as np
import logging
import sys
import time
from datetime import datetime as dt
from google.oauth2.service_account import Credentials

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- Load Secrets & Debug ---
try:
    GCP_CREDENTIALS_JSON = os.environ.get('GCP_CREDENTIALS_JSON', '{}')
    SHEET_ID = os.environ.get('SHEET_ID', '')
    
    logging.info(f"🔍 DEBUG: SHEET_ID Length = {len(SHEET_ID) if SHEET_ID else 0}")
    logging.info(f"🔍 DEBUG: GCP_CREDENTIALS_JSON Length = {len(GCP_CREDENTIALS_JSON) if GCP_CREDENTIALS_JSON else 0}")
    
    GCP_CREDENTIALS = json.loads(GCP_CREDENTIALS_JSON)
except Exception as e:
    logging.error(f"❌ Failed to parse secrets: {e}")
    sys.exit(1)

# --- DIVERSIFIED UNIVERSE ---
UNIVERSE = [
    'RELIANCE.NS', 'ONGC.NS', 'TCS.NS', 'INFY.NS', 'HCLTECH.NS', 
    'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'HINDUNILVR.NS', 'ITC.NS'
] # Testing with 10 main stocks first to save time and speed up tracking

def get_stock_data_with_signal(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df_daily = ticker.history(period="1y")
        if df_daily.empty:
            return None
        
        ltp = df_daily['Close'].iloc[-1]
        prev_close = df_daily['Close'].iloc[-2]
        vol = df_daily['Volume'].iloc[-1]
        
        # Fast indicators
        sma50 = df_daily['Close'].rolling(50).mean().iloc[-1] if len(df_daily) >= 50 else ltp
        rsi = 55 # Default safe value for debug
        
        return [symbol, round(ltp, 2), "📈 TRACKING", "OK", 65, f"{vol:,}", "-", "-", round(rsi, 2), round(sma50, 2), "-", round(prev_close, 2), "WATCH", "⏳ WAIT", ""]
    except Exception as e:
        logging.error(f"❌ Error fetching {symbol}: {e}")
        return None

def update_google_sheet():
    logging.info("🚀 Starting Super Debugger Sheet Update...")
    
    if not SHEET_ID or not GCP_CREDENTIALS:
        logging.error("❌ CRITICAL: Environment variables are EMPTY on the server! Check GitHub Secrets.")
        return False
        
    try:
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        
        logging.info(f"🔄 Connecting to Sheet ID: {SHEET_ID}")
        sh = client.open_by_key(SHEET_ID)
        
        # Debug: Print sheet name to confirm connection
        logging.info(f"🎯 Connected to Workbook Name: '{sh.title}'")
        
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"🎯 Target Sheet/Tab Name: '{dash_sheet.title}'")
        
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        final_data = []
        for sym in UNIVERSE:
            data = get_stock_data_with_signal(sym)
            if data:
                data[-1] = timestamp # Insert time
                final_data.append(data)
                logging.info(f"✔ Local Data Ready For: {sym} | Price: {data[1]}")
        
        if not final_data:
            logging.error("❌ No data fetched! Yahoo Finance returned empty rows.")
            return False
            
        logging.info(f"📤 Uploading {len(final_data)} rows to Google Sheet now...")
        
        # Clear & Force Update
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SCANNER - {date_stamp} (Debug Live Update)", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision', '15-Min Signal', 'Time']]
        dash_sheet.update(range_name='A2', values=header2)
        
        dash_sheet.update(range_name='A3', values=final_data)
        
        logging.info("🚀 [BOOM] SCRIPT EXECUTED AND GOOGLE API CONFIRMED UPDATE!")
        return True
        
    except gspread.exceptions.APIError as api_err:
        logging.error(f"❌ GOOGLE API ERROR: {api_err}")
    except Exception as e:
        logging.error(f"❌ SERVER OR CONNECTION ERROR: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
