# update_sheet.py – AI Bro Super Scanner 2.0 (DEBUGGING)
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
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- Load Secrets ---
try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
    logging.info(f"✅ SHEET_ID: {SHEET_ID}")
except Exception as e:
    logging.error(f"❌ Failed to load secrets: {e}")
    sys.exit(1)

# --- UNIVERSE (Sirf 5 stocks test ke liye) ---
UNIVERSE = ['RELIANCE', 'TCS', 'INFY', 'BHARTIARTL', 'HINDUNILVR']

# --- NIFTY 50 Index ---
NIFTY_SYMBOL = "^NSEI"

# --- Simple Stock Data Fetch (Debug) ---
def get_simple_stock_data(symbol):
    try:
        logging.debug(f"🔍 Fetching {symbol}...")
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="5d")
        if df.empty:
            logging.warning(f"⚠️ No data for {symbol}")
            return None
        ltp = df['Close'].iloc[-1]
        logging.info(f"✅ {symbol} LTP: {ltp}")
        return {
            'symbol': symbol + ".NS",
            'ltp': round(ltp, 2),
            'action': "⏳ HOLD",
            'status': "TEST",
            'score': 50,
            'volume': int(df['Volume'].iloc[-1]),
            'traded_value': ltp * df['Volume'].iloc[-1],
            'week_change': 0,
            'rsi': 50,
            'sma50': ltp,
            'sma200': ltp,
            'prev_close': df['Close'].iloc[-2] if len(df) > 1 else ltp,
            'entry': "⏳ HOLD",
            'ema21': ltp,
            'vwap': ltp,
            'bb_squeeze': 0.02,
            'momentum_burst': "❌",
            'consolidation': "❌",
            'breakout': "❌",
            'swing': "➡️ Neutral",
            'high_52w': ltp * 1.1,
            'low_52w': ltp * 0.9
        }
    except Exception as e:
        logging.error(f"❌ Error in {symbol}: {e}")
        return None

# --- NIFTY Index Data ---
def get_nifty_data():
    try:
        ticker = yf.Ticker(NIFTY_SYMBOL)
        df = ticker.history(period="5d")
        if df.empty:
            return None
        ltp = df['Close'].iloc[-1]
        return {
            'symbol': "NIFTY_INDEX",
            'ltp': round(ltp, 2),
            'action': "NIFTY",
            'status': "INDEX",
            'score': "-",
            'volume': "-",
            'traded_value': "-",
            'week_change': 0,
            'rsi': "-",
            'sma50': "-",
            'sma200': "-",
            'prev_close': round(df['Close'].iloc[-2], 2) if len(df) > 1 else ltp,
            'entry': "-",
            'ema21': "-",
            'vwap': "-",
            'bb_squeeze': "-",
            'momentum_burst': "-",
            'consolidation': "-",
            'breakout': "-",
            'swing': "-",
            'high_52w': "-",
            'low_52w': "-"
        }
    except Exception as e:
        logging.error(f"Error fetching NIFTY: {e}")
        return None

# --- Main Update ---
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
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        final_data = []
        
        # --- NIFTY Index ---
        nifty = get_nifty_data()
        if nifty:
            final_data.append([
                nifty['symbol'], nifty['ltp'], nifty['action'], nifty['status'],
                nifty['score'], nifty['volume'], nifty['traded_value'],
                nifty['week_change'], nifty['rsi'], nifty['sma50'],
                nifty['sma200'], nifty['prev_close'], nifty['entry'],
                nifty['ema21'], nifty['vwap'], nifty['bb_squeeze'],
                nifty['momentum_burst'], nifty['consolidation'], nifty['breakout'],
                nifty['swing'], nifty['high_52w'], nifty['low_52w'],
                timestamp
            ])
            logging.info("✅ NIFTY data added")
        
        # --- Stocks ---
        for sym in UNIVERSE:
            data = get_simple_stock_data(sym)
            if data:
                final_data.append([
                    data['symbol'], data['ltp'], data['action'], data['status'],
                    data['score'], data['volume'], f"₹{data['traded_value']/1e7:.2f}Cr",
                    data['week_change'], data['rsi'], data['sma50'],
                    data['sma200'], data['prev_close'], data['entry'],
                    data['ema21'], data['vwap'], data['bb_squeeze'],
                    data['momentum_burst'], data['consolidation'], data['breakout'],
                    data['swing'], data['high_52w'], data['low_52w'],
                    timestamp
                ])
                logging.info(f"✅ Added {data['symbol']}")
            else:
                logging.warning(f"⚠️ No data for {sym}")
            time.sleep(0.1)
        
        logging.info(f"📊 final_data rows: {len(final_data)}")
        
        # --- Update Sheet ---
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SUPER SCANNER 2.0 - {date_stamp}", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [
            ['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value',
             'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision',
             'EMA21', 'VWAP', 'BB Squeeze', 'Momentum Burst', 'Consolidation',
             'Breakout', 'Swing', '52W High', '52W Low', 'Time']
        ]
        dash_sheet.update(range_name='A2', values=header2)
        
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        else:
            test_row = [["TEST", 100, "HOLD", "TEST", 50, 1000, "1 Cr", "1%", 50, 100, 90, 95, "HOLD", 100, 95, 0.02, "✅", "✅", "✅", "📈 Higher High", 110, 90, timestamp]]
            dash_sheet.update(range_name='A3', values=test_row)
            logging.info("✅ Added test row")
        
        dash_sheet.freeze(rows=2)
        logging.info("✅ Update completed!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
