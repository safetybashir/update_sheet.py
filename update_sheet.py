# update_sheet.py – FINAL WORKING (No 15-Min Strategy)
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

# --- Load Secrets ---
try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1T0r-MG2oxImCyhJv0q98bdCEnjNschePHBhOtMmW9Bg')
except Exception as e:
    logging.error(f"❌ Failed to load credentials: {e}")
    sys.exit(1)

# --- UNIVERSE (Original + Diversified, No Banks/Financials) ---
UNIVERSE = [
    # Original
    'BHARTIARTL', 'INFY', 'RELIANCE', 'NATIONALUM',
    'COALINDIA', 'HYUNDAI', 'HINDUNILVR', 'TCS', 'M&M',
    'ULTRACEMCO', 'LT', 'HAL', 'KALYANKJIL',
    'NESTLEIND', 'SUNPHARMA', 'JUBLFOOD', 'WIPRO', 'RVNL',
    'MAXHEALTH', 'HCLTECH', 'TATASTEEL', 'ASHOKLEY',
    'HINDALCO', 'ASIANPAINT', 'CIPLA', 'TORNTPHARM', 'ETERNAL',
    'MARUTI', 'TMPV', 'WAAREEENER', 'GVT&D',
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
    'GODREJPROP', 'VOLTAS', 'APLAPOLLO', 'AUROPHARMA',
    'TATAPOWER', 'PIIND', 'GLENMARK', 'MPHASIS',
    'FORTIS', 'BIOCON', 'OBEROIRLTY', 'COLPAL', 'LAURUSLABS',
    'COCHINSHIP', 'PETRONET', 'TIINDIA', 'JSL', 'PHOENIXLTD',
    'TATACOMM', 'ESCORTS', 'SHREECEM', 'TORNTPOWER', 'LENSKART',
    'EXIDEIND', 'COROMANDEL', 'KEI', 'AMBUJACEM', 'PRESTIGE',
    'SUPREMEIND', 'IPCALAB', 'BALKRISIND', 'CONCOR', 'TATAELXSI',
    'FLUOROCHEM', 'KPITTECH', 'UNOMINDA', 'LINDEINDIA', 'AIAENG',
    'IRCTC', 'AJANTPHARM', 'GLAXO', 'JKCEMENT', 'GODREJIND',
    'APOLLOTYRE', 'LTTS', 'TATAINVEST', 'BERGAPAINT', 'KPRMILL',
    'ABBOTINDIA', 'ACC', 'ONGC', 'DRREDDY', 'TATAMOTORS'
]

# --- Stock Data Fetch (Daily Only) ---
def get_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="5d")
        if df.empty:
            return None
        
        ltp = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else ltp
        vol = df['Volume'].iloc[-1]
        
        week_change = ((ltp - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100 if len(df) >= 5 else 0
        
        sma50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else ltp
        sma200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else ltp
        
        if len(df) > 14:
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70
        else:
            rsi = 50
        
        traded_value = ltp * vol
        
        score = 0
        if traded_value > 100_00_00_000:
            score += 40
        elif traded_value > 50_00_00_000:
            score += 30
        elif traded_value > 10_00_00_000:
            score += 15
        else:
            score += 5
        
        if ltp > sma50:
            score += 10
        if ltp > sma200:
            score += 10
        if rsi > 60:
            score += 20
        elif rsi > 50:
            score += 10
        if week_change > 5:
            score += 10
        elif week_change > 2:
            score += 5
        
        score = min(100, score)
        score = max(0, score)
        
        if score >= 75:
            status = "🎯 STRONG BUY"
            action = "🚀 BUY NOW"
        elif score >= 60:
            status = "📈 BUY ZONE"
            action = "📈 WATCH"
        elif score >= 40:
            status = "🛡️ RANGE-BOUND"
            action = "⏳ HOLD"
        elif score >= 20:
            status = "📉 WEAK"
            action = "📉 AVOID"
        else:
            status = "⚠️ DUMPING"
            action = "📉 AVOID"
        
        if score >= 75 and ltp > sma50 and ltp > sma200 and rsi > 60 and week_change > 0:
            entry = "✅ BUY NOW"
        elif score >= 60 and ltp > sma50 and ltp > sma200 and rsi > 50:
            entry = "🟡 WATCH"
        elif score >= 40:
            entry = "⏳ HOLD"
        else:
            entry = "🔴 AVOID"
        
        return {
            'symbol': symbol + ".NS",
            'ltp': round(ltp, 2),
            'action': action,
            'status': status,
            'score': score,
            'volume': f"{vol:,}",
            'traded_value': f"₹{traded_value/1e7:.2f}Cr",
            'week_change': f"{week_change:.2f}%",
            'rsi': round(rsi, 2),
            'sma50': round(sma50, 2),
            'sma200': round(sma200, 2),
            'prev_close': round(prev_close, 2),
            'entry': entry
        }
    except Exception as e:
        logging.error(f"Error processing {symbol}: {e}")
        return None

# --- Main Update Function ---
def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Starting update...")
    
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
        
        for sym in UNIVERSE:
            data = get_stock_data(sym)
            if data:
                final_data.append([
                    data['symbol'], data['ltp'], data['action'], data['status'],
                    data['score'], data['volume'], data['traded_value'],
                    data['week_change'], data['rsi'], data['sma50'],
                    data['sma200'], data['prev_close'], data['entry'],
                    timestamp
                ])
            time.sleep(0.2)
        
        logging.info(f"📊 final_data rows: {len(final_data)}")
        
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SCANNER - {date_stamp} (10-Min Update)", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision', 'Time']]
        dash_sheet.update(range_name='A2', values=header2)
        
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        else:
            logging.warning("⚠️ No data to update")
            # Fallback test row
            test_row = [["TEST", "100", "HOLD", "TEST", "50", "1000", "₹1Cr", "1%", "50", "100", "90", "95", "HOLD", timestamp]]
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
