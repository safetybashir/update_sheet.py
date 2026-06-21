# update_sheet.py – FINAL FIXED VERSION
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
    logging.info(f"✅ SHEET_ID: {SHEET_ID}")
except Exception as e:
    logging.error(f"❌ Failed to load credentials: {e}")
    sys.exit(1)

# --- UNIVERSE (Sirf Test Ke Liye 5 Stocks) ---
UNIVERSE = ['RELIANCE', 'TCS', 'INFY', 'BHARTIARTL', 'HINDUNILVR']

# --- NIFTY Index ---
NIFTY_SYMBOL = "^NSEI"

def get_stock_data_with_signal(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        df_daily = ticker.history(period="5d")
        if df_daily.empty:
            logging.warning(f"⚠️ No data for {symbol}")
            return None
        
        ltp = df_daily['Close'].iloc[-1]
        prev_close = df_daily['Close'].iloc[-2] if len(df_daily) > 1 else ltp
        vol = df_daily['Volume'].iloc[-1]
        
        # Week Change
        week_change = ((ltp - df_daily['Close'].iloc[0]) / df_daily['Close'].iloc[0]) * 100 if len(df_daily) >= 5 else 0
        
        # SMA50, SMA200
        sma50 = df_daily['Close'].rolling(50).mean().iloc[-1] if len(df_daily) >= 50 else ltp
        sma200 = df_daily['Close'].rolling(200).mean().iloc[-1] if len(df_daily) >= 200 else ltp
        
        # RSI
        if len(df_daily) > 14:
            delta = df_daily['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70
        else:
            rsi = 50
        
        # Traded Value
        traded_value = ltp * vol
        
        # Score
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
        
        # Status
        if score >= 75:
            status = "🎯 STRONG BUY"
        elif score >= 60:
            status = "📈 BUY ZONE"
        elif score >= 40:
            status = "🛡️ RANGE-BOUND"
        elif score >= 20:
            status = "📉 WEAK"
        else:
            status = "⚠️ DUMPING"
        
        # Action
        if score >= 75:
            action = "🚀 BUY NOW"
        elif score >= 60:
            action = "📈 WATCH"
        elif score >= 40:
            action = "⏳ HOLD"
        else:
            action = "📉 AVOID"
        
        # Entry Decision
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
            'entry': entry,
            'signal': "⏳ WAIT",
            'reason': "No Signal"
        }
    except Exception as e:
        logging.error(f"❌ Error in {symbol}: {e}")
        return None

def update_google_sheet():
    logging.info("🚀 Starting update...")
    
    try:
        # Authenticate
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        # Prepare data
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        final_data = []
        
        # Add NIFTY Index (hardcoded test)
        final_data.append([
            "NIFTY_INDEX", 24000, "⏳ WAIT", "No Signal", "-",
            "447,900", "-", "-", "-", "-", "-", "-", "-", "⏳ WAIT - No Signal", timestamp
        ])
        
        # Add stocks
        for sym in UNIVERSE:
            data = get_stock_data_with_signal(sym)
            if data:
                final_data.append([
                    data['symbol'], data['ltp'], data['action'], data['status'],
                    data['score'], data['volume'], data['traded_value'],
                    data['week_change'], data['rsi'], data['sma50'],
                    data['sma200'], data['prev_close'], data['entry'],
                    data['signal'] + " - " + data['reason'],
                    timestamp
                ])
                logging.info(f"✅ Added {data['symbol']}")
            time.sleep(0.2)
        
        logging.info(f"📊 final_data rows: {len(final_data)}")
        
        # --- Update Sheet ---
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SCANNER - {date_stamp} (10-Min Update)", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        logging.info("✅ Header updated")
        
        header2 = [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision', '15-Min Signal', 'Time']]
        dash_sheet.update(range_name='A2', values=header2)
        logging.info("✅ Header2 updated")
        
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        else:
            logging.warning("⚠️ No data to update")
            # Fallback: Add a test row
            test_row = [["TEST", "100", "HOLD", "TEST", "50", "1000", "₹1Cr", "1%", "50", "100", "90", "95", "HOLD", "WAIT", timestamp]]
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
