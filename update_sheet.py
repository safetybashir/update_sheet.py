# update_sheet.py – Fixed Version
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

# --- Stock Universe ---
UNIVERSE = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR',
    'ICICIBANK', 'ITC', 'KOTAKBANK', 'SBIN', 'BHARTIARTL',
    'LT', 'AXISBANK', 'BAJFINANCE', 'HCLTECH', 'WIPRO',
    'SUNPHARMA', 'TITAN', 'MARUTI', 'ONGC', 'NTPC',
    'TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI', 'TORNTPHARM',
    'AVANTIFEED', 'DIXON', 'EICHERMOT', 'RVNL', 'KAYNES',
    'WAAREEENER', 'SOLARINDS', 'WABAG', 'ALKEM', 'DIVISLAB',
    'JSWSTEEL', 'APOLLOHOSP', 'POWERINDIA', 'BAJAJ-AUTO',
    'ULTRACEMCO', 'INDIGO', 'MAXHEALTH'
]

def safe_fetch(symbol):
    """Safe fetch with retry logic."""
    for attempt in range(3):
        try:
            ticker = yf.Ticker(symbol + ".NS")
            df = ticker.history(period="5d", interval="1d")
            if not df.empty:
                return ticker, df
            time.sleep(1)
        except Exception as e:
            logging.warning(f"Attempt {attempt+1} failed for {symbol}: {e}")
            time.sleep(2)
    return None, None

def get_institutional_score(ticker_obj, symbol):
    """Calculate institutional score with proper error handling."""
    try:
        if ticker_obj is None:
            return "⏳ NO DATA", 0, 0, 0, 0, 0, 0, 0, 0
        
        # Try getting data directly
        df = ticker_obj.history(period="5d")
        if df.empty:
            logging.warning(f"No data for {symbol}")
            return "⏳ NO DATA", 0, 0, 0, 0, 0, 0, 0, 0
        
        ltp = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else ltp
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].mean()
        
        # 5-day change
        week_change = ((ltp - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100 if len(df) >= 5 else 0
        
        # Moving Averages
        sma20 = df['Close'].rolling(20).mean().iloc[-1] if len(df) >= 20 else ltp
        sma50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else ltp
        sma200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else ltp
        
        # RSI calculation
        if len(df) > 14:
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70
        else:
            rsi = 50
        
        # --- Institutional Score ---
        score = 0
        if ltp > prev_close:
            score += 3
        if ltp > sma20:
            score += 2
        if ltp > sma50:
            score += 1
        if ltp > sma200:
            score += 1
        if vol > avg_vol * 1.5:
            score += 3
        elif vol > avg_vol:
            score += 1
        if sma20 > sma50 > sma200:
            score += 3
        elif sma50 > sma200:
            score += 1
        if rsi > 60:
            score += 1
        
        score = min(100, int((score / 15) * 100))
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
        
        return status, score, round(ltp, 2), round(vol, 0), round(week_change, 2), round(sma50, 2), round(sma200, 2), round(rsi, 2), round(prev_close, 2)
    
    except Exception as e:
        logging.error(f"Error processing {symbol}: {e}")
        return "⏳ SYNCING", 0, 0, 0, 0, 0, 0, 0, 0

def fetch_all_stocks(universe):
    """Fetch data for all stocks with retry."""
    results = []
    for sym in universe:
        try:
            ticker = yf.Ticker(sym + ".NS")
            # Wait a bit between requests
            time.sleep(0.5)
            status, score, ltp, vol, week_change, sma50, sma200, rsi, prev_close = get_institutional_score(ticker, sym)
            results.append((sym, status, score, ltp, vol, week_change, sma50, sma200, rsi, prev_close))
        except Exception as e:
            logging.error(f"Error processing {sym}: {e}")
            results.append((sym, "❌ ERROR", 0, 0, 0, 0, 0, 0, 0, 0))
    return results

# --- Main Update Function ---
def update_google_sheet():
    logging.info("🚀 AI Bro Super Scanner 2.0 – Starting...")
    
    try:
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info("✅ Connected to Google Sheet")
        
        results = fetch_all_stocks(UNIVERSE)
        logging.info(f"📊 Fetched data for {len(results)} stocks")
        
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        results.sort(key=lambda x: x[2], reverse=True)
        
        final_data = []
        for sym, status, score, ltp, vol, week_change, sma50, sma200, rsi, prev_close in results:
            if score >= 75:
                action = "🚀 BUY NOW"
            elif score >= 60:
                action = "📈 WATCH"
            elif score >= 40:
                action = "⏳ HOLD"
            else:
                action = "📉 AVOID"
            
            final_data.append([
                sym + ".NS",
                ltp,
                action,
                status,
                score,
                f"{vol:,}",
                f"{week_change}%",
                rsi,
                f"{sma50:.2f}",
                f"{sma200:.2f}",
                f"PC:{prev_close:.2f}",
                timestamp
            ])
        
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SUPER SCANNER 2.0 - {date_stamp}", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [['Symbol', 'LTP', 'Action', 'Trend Status', 'Score', 'Volume', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Time']]
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
