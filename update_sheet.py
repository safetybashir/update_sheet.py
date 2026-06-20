# update_sheet.py – AI Bro Scanner with 15-Minute Candle Strategy (10-Min Update)
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.oauth2.service_account import Credentials

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- Load Secrets ---
try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1T0r-MG2oxImCyhJv0q98bdCEnjNschePHBhOtMmW9Bg')
except Exception as e:
    logging.error(f"❌ Failed to load credentials: {e}")
    sys.exit(1)

# --- Custom Universe (Your Selected Stocks) ---
UNIVERSE = [
    'BHARTIARTL', 'INFY', 'RELIANCE', 'MCX', 'NATIONALUM',
    'COALINDIA', 'HYUNDAI', 'HINDUNILVR', 'TCS', 'M&M',
    'ULTRACEMCO', 'LT', 'HAL', 'BSE', 'KALYANKJIL',
    'NESTLEIND', 'SUNPHARMA', 'JUBLFOOD', 'WIPRO', 'RVNL',
    'MAXHEALTH', 'HCLTECH', 'POWERINDIA', 'TATASTEEL', 'ASHOKLEY',
    'HINDALCO', 'ASIANPAINT', 'CIPLA', 'TORNTPHARM', 'ETERNAL',
    'MARUTI', 'TMPV', 'WAAREEENER', 'MOTHERSON', 'GVT&D',
    'CUMMINSIND', 'TATACONSUM', 'BEL', 'EICHERMOT', 'DLF',
    'ENRIN', 'ITC', 'BDL', 'SOLARINDS', 'BRITANNIA',
    'DMART', 'THERMAX', 'CGPOWER', 'LODHA', 'APOLLOHOSP',
    'NAUKRI', 'TVSMOTOR', 'TMCV', 'TITAN', 'HEROMOTOCO',
    'ABB', 'BPCL', 'ALKEM', 'SIEMENS', 'PERSISTENT',
    'DRREDDY', 'OFSS', 'SWIGGY', 'LUPIN', 'JSWENERGY',
    'PIDILITIND', 'INDUSTOWER', 'BOSCHLTD', 'BHARATFORG', 'INDIGO',
    'MARICO', 'TECHM', 'DABUR', 'DIXON', 'SRF',
    'MANKIND', 'LTM', 'JINDALSTEL', 'GRASIM', 'HAVELLS',
    'BAJAJ-AUTO', 'NYKAA', 'COFORGE', 'TRENT', 'HINDPETRO',
    'ASTRAL', 'POLYCAB', 'MAZDOCK', 'PREMIERENE', 'APARINDS',
    'GAIL', 'UPL', 'DIVISLAB', 'JSWSTEEL', 'GODREJCP',
    'GODREJPROP', 'VOLTAS', 'APLAPOLLO', 'AUROPHARMA', 'RECLTD',
    'TATAPOWER', 'PIIND', 'GLENMARK', 'MPHASIS', 'LTF',
    'FORTIS', 'BIOCON', 'OBEROIRLTY', 'COLPAL', 'LAURUSLABS',
    'COCHINSHIP', 'PETRONET', 'TIINDIA', 'JSL', 'PHOENIXLTD',
    'TATACOMM', 'ESCORTS', 'SHREECEM', 'TORNTPOWER', 'LENSKART',
    'EXIDEIND', 'COROMANDEL', 'KEI', 'AMBUJACEM', 'PRESTIGE',
    'SUPREMEIND', 'IPCALAB', 'BALKRISIND', 'CONCOR', 'TATAELXSI',
    'FLUOROCHEM', 'KPITTECH', 'UNOMINDA', 'LINDEINDIA', 'AIAENG',
    'IRCTC', 'AJANTPHARM', 'GLAXO', 'JKCEMENT', 'GODREJIND',
    'APOLLOTYRE', 'LTTS', 'TATAINVEST', 'BERGAPAINT', 'KPRMILL',
    'ABBOTINDIA', 'ACC'
]

# --- NIFTY Index for Index Trading ---
NIFTY_SYMBOL = "^NSEI"

# --- 15-Minute Candle Signal (Stocks) ---
def get_15min_signal_stock(ticker_obj):
    try:
        df = ticker_obj.history(period="1h", interval="15m")
        if len(df) >= 3:
            current_close = df['Close'].iloc[-1]
            prev_high = df['High'].iloc[-2]
            prev_low = df['Low'].iloc[-2]
            current_vol = df['Volume'].iloc[-1]
            prev_vol = df['Volume'].iloc[-2]
            
            # Buy Call Signal
            if current_close > prev_high and current_vol > prev_vol * 1.5:
                return "📈 BUY CALL", "Bullish Breakout"
            # Buy Put Signal
            elif current_close < prev_low and current_vol > prev_vol * 1.5:
                return "📉 BUY PUT", "Bearish Breakdown"
        return "⏳ WAIT", "No Signal"
    except:
        return "⏳ WAIT", "Error"

# --- 15-Minute Candle Signal (NIFTY Index) ---
def get_15min_signal_index():
    try:
        nifty = yf.Ticker(NIFTY_SYMBOL)
        df = nifty.history(period="1h", interval="15m")
        if len(df) >= 3:
            current_close = df['Close'].iloc[-1]
            prev_high = df['High'].iloc[-2]
            prev_low = df['Low'].iloc[-2]
            current_vol = df['Volume'].iloc[-1]
            prev_vol = df['Volume'].iloc[-2]
            
            # Buy Call Signal
            if current_close > prev_high and current_vol > prev_vol * 1.5:
                return "📈 BUY CALL", "NIFTY Bullish"
            # Buy Put Signal
            elif current_close < prev_low and current_vol > prev_vol * 1.5:
                return "📉 BUY PUT", "NIFTY Bearish"
        return "⏳ WAIT", "No Signal"
    except:
        return "⏳ WAIT", "Error"

# --- Main Update Function ---
def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – 10-Min Update (15-Min Candle Strategy)")
    
    try:
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info("✅ Connected to Google Sheet")
        
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        final_data = []
        
        # --- Index Signal (NIFTY) ---
        index_signal, index_reason = get_15min_signal_index()
        final_data.append([
            "NIFTY_INDEX", "-", index_signal, index_reason, "-", "-", "-", "-", "-", "-", "-", "-", "-", timestamp
        ])
        
        # --- Stocks Signals ---
        for sym in UNIVERSE[:20]:  # Limit to 20 stocks for speed
            try:
                ticker = yf.Ticker(sym + ".NS")
                signal, reason = get_15min_signal_stock(ticker)
                final_data.append([
                    sym + ".NS", "-", signal, reason, "-", "-", "-", "-", "-", "-", "-", "-", "-", timestamp
                ])
                time.sleep(0.5)
            except Exception as e:
                logging.error(f"Error processing {sym}: {e}")
                continue
        
        # --- Update Sheet ---
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SCANNER - {date_stamp} (10-Min Update, 15-Min Candle)", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [['Symbol', 'LTP', 'Action', 'Reason', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'ENTRY DECISION', 'Time']]
        dash_sheet.update(range_name='A2', values=header2)
        
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        
        dash_sheet.freeze(rows=2)
        logging.info("✅ Update completed!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
