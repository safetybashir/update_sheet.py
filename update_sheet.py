# update_sheet.py – DEBUGGING VERSION
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

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- Load Secrets ---
try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1T0r-MG2oxImCyhJv0q98bdCEnjNschePHBhOtMmW9Bg')
    logging.info(f"✅ SHEET_ID loaded: {SHEET_ID}")
except Exception as e:
    logging.error(f"❌ Failed to load credentials: {e}")
    sys.exit(1)

# --- UNIVERSE (Debug: Sirf 5 stocks test ke liye) ---
UNIVERSE = ['RELIANCE', 'TCS', 'INFY', 'BHARTIARTL', 'HINDUNILVR']

NIFTY_SYMBOL = "^NSEI"

def get_stock_data_with_signal(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="5d")
        if df.empty:
            logging.warning(f"⚠️ No data for {symbol}")
            return None
        ltp = df['Close'].iloc[-1]
        return {
            'symbol': symbol + ".NS",
            'ltp': round(ltp, 2),
            'action': "⏳ HOLD",
            'status': "TEST",
            'score': 50,
            'volume': "1,000",
            'traded_value': "₹100Cr",
            'week_change': "1.00%",
            'rsi': 50,
            'sma50': 100,
            'sma200': 90,
            'prev_close': 95,
            'entry': "⏳ HOLD",
            'signal': "⏳ WAIT",
            'reason': "Test"
        }
    except Exception as e:
        logging.error(f"❌ Error in {symbol}: {e}")
        return None

def update_google_sheet():
    logging.info("🚀 DEBUG: Starting update...")
    try:
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title} (ID: {sh.id})")

        final_data = []
        for sym in UNIVERSE:
            data = get_stock_data_with_signal(sym)
            if data:
                final_data.append([
                    data['symbol'], data['ltp'], data['action'], data['status'],
                    data['score'], data['volume'], data['traded_value'],
                    data['week_change'], data['rsi'], data['sma50'],
                    data['sma200'], data['prev_close'], data['entry'],
                    data['signal'] + " - " + data['reason'],
                    dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
                ])
                logging.info(f"✅ Added {data['symbol']}")
            else:
                logging.warning(f"⚠️ No data for {sym}")

        logging.info(f"📊 final_data has {len(final_data)} rows")
        dash_sheet.clear()
        header = [["DEBUG TEST - " + dt.now().strftime("%Y-%m-%d %H:%M:%S"), "", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        header2 = [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision', '15-Min Signal', 'Time']]
        dash_sheet.update(range_name='A2', values=header2)
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        else:
            logging.warning("⚠️ No data to update")
        logging.info("✅ Update completed!")
        return True
    except Exception as e:
        logging.error(f"❌ FAILED: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
