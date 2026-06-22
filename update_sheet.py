# update_sheet.py – MINIMAL TEST (Sirf 10 Stocks)
import os
import json
import gspread
import yfinance as yf
import pytz
import logging
import sys
import time
from datetime import datetime as dt
from google.oauth2.service_account import Credentials

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Load Secrets ---
try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
except Exception as e:
    logging.error(f"❌ Failed to load secrets: {e}")
    sys.exit(1)

# --- TEST UNIVERSE (Sirf 10 Stocks) ---
UNIVERSE = [
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HCLTECH.NS', 'WIPRO.NS',
    'HINDUNILVR.NS', 'BHARTIARTL.NS', 'SUNPHARMA.NS', 'DRREDDY.NS', 'CIPLA.NS'
]

# --- NIFTY 50 Index ---
NIFTY_SYMBOL = "^NSEI"

# --- Scan Stock (Simple) ---
def scan_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d")
        if df.empty:
            return None
        
        price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else price
        volume = df['Volume'].iloc[-1]
        
        return {
            'symbol': symbol,
            'ltp': round(price, 2),
            'action': "⏳ HOLD",
            'status': "TEST",
            'score': 50,
            'volume': volume,
            'traded_value': price * volume,
            'week_change': 0,
            'rsi': 50,
            'sma50': price,
            'sma200': price,
            'prev_close': round(prev_close, 2),
            'entry': "⏳ HOLD",
            'ema21': price,
            'vwap': price,
            'bb_squeeze': 0.02,
            'momentum_burst': "❌",
            'consolidation': "❌",
            'breakout': "NO B/O",
            'swing': "➡️ Neutral",
            'high_52w': price * 1.1,
            'low_52w': price * 0.9
        }
    except Exception as e:
        logging.error(f"Error scanning {symbol}: {e}")
        return None

# --- NIFTY Index ---
def scan_nifty():
    try:
        ticker = yf.Ticker(NIFTY_SYMBOL)
        df = ticker.history(period="5d")
        if df.empty:
            return None
        price = df['Close'].iloc[-1]
        return {
            'symbol': "NIFTY_INDEX",
            'ltp': round(price, 2),
            'action': "NIFTY",
            'status': "INDEX",
            'score': "-",
            'volume': "-",
            'traded_value': "-",
            'week_change': 0,
            'rsi': "-",
            'sma50': "-",
            'sma200': "-",
            'prev_close': round(df['Close'].iloc[-2], 2) if len(df) > 1 else price,
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
        logging.error(f"Error scanning NIFTY: {e}")
        return None

# --- Main Update ---
def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – MINIMAL TEST (10 Stocks)")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        final_data = []
        
        nifty = scan_nifty()
        if nifty:
            final_data.append([nifty['symbol'], nifty['ltp'], nifty['action'], nifty['status'], nifty['score'],
                              nifty['volume'], nifty['traded_value'], nifty['week_change'], nifty['rsi'],
                              nifty['sma50'], nifty['sma200'], nifty['prev_close'], nifty['entry'],
                              nifty['ema21'], nifty['vwap'], nifty['bb_squeeze'], nifty['momentum_burst'],
                              nifty['consolidation'], nifty['breakout'], nifty['swing'], nifty['high_52w'],
                              nifty['low_52w'], timestamp])
        
        for sym in UNIVERSE:
            data = scan_stock(sym)
            if data:
                final_data.append([data['symbol'], data['ltp'], data['action'], data['status'], data['score'],
                                  data['volume'], f"₹{data['traded_value']/1e7:.2f}Cr", data['week_change'],
                                  data['rsi'], data['sma50'], data['sma200'], data['prev_close'], data['entry'],
                                  data['ema21'], data['vwap'], data['bb_squeeze'], data['momentum_burst'],
                                  data['consolidation'], data['breakout'], data['swing'], data['high_52w'],
                                  data['low_52w'], timestamp])
                logging.info(f"✅ Added {data['symbol']}")
            time.sleep(0.05)
        
        logging.info(f"📊 final_data rows: {len(final_data)}")
        
        dash_sheet.clear()
        dash_sheet.update('A1', [[f"📊 AI BRO SCANNER - {date_stamp} (MINIMAL TEST)", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value',
                                 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision',
                                 'EMA21', 'VWAP', 'BB Squeeze', 'Momentum Burst', 'Consolidation',
                                 'Breakout', 'Swing', '52W High', '52W Low', 'Time']])
        
        if final_data:
            dash_sheet.update('A3', final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        else:
            dash_sheet.update('A3', [["TEST", 100, "HOLD", "TEST", 50, 1000, "1 Cr", "1%", 50, 100, 90, 95, "HOLD", 100, 95, 0.02, "✅", "✅", "NO B/O", "➡️ Neutral", 110, 90, timestamp]])
            logging.info("✅ Added test row")
        
        dash_sheet.freeze(rows=2)
        logging.info("✅ Update completed!")
        return True
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
