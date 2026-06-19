# update_sheet.py – AI Bro Super Scanner 2.0 with Traded Value
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

# --- Fetch NIFTY LargeMidcap 250 Stocks ---
def fetch_nifty_largemidcap250():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_niftylargemidcap250list.csv"
        df = pd.read_csv(url)
        symbols = df['Symbol'].tolist()
        logging.info(f"✅ Fetched {len(symbols)} stocks from NIFTY LargeMidcap 250")
        return symbols
    except Exception as e:
        logging.error(f"❌ Failed to fetch NIFTY LargeMidcap 250: {e}")
        # Fallback to default universe
        return [
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR',
            'ICICIBANK', 'ITC', 'KOTAKBANK', 'SBIN', 'BHARTIARTL',
            'LT', 'AXISBANK', 'BAJFINANCE', 'HCLTECH', 'WIPRO',
            'SUNPHARMA', 'TITAN', 'MARUTI', 'ONGC', 'NTPC'
        ]

# Use this function to set UNIVERSE
UNIVERSE = fetch_nifty_largemidcap250()

# --- Main Scoring Function with Traded Value ---
def get_institutional_score(ticker_obj, symbol):
    try:
        if ticker_obj is None:
            return "⏳ NO DATA", 0, 0, 0, 0, 0, 0, 0, 0, 0
        
        df = ticker_obj.history(period="5d")
        if df.empty:
            return "⏳ NO DATA", 0, 0, 0, 0, 0, 0, 0, 0, 0
        
        ltp = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else ltp
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].mean()
        
        # --- TRADED VALUE (Price × Volume) ---
        traded_value = ltp * vol  # in rupees
        
        # --- Week Change ---
        week_change = ((ltp - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100 if len(df) >= 5 else 0
        
        # --- Moving Averages ---
        sma20 = df['Close'].rolling(20).mean().iloc[-1] if len(df) >= 20 else ltp
        sma50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else ltp
        sma200 = df['Close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else ltp
        
        # --- RSI ---
        if len(df) > 14:
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70
        else:
            rsi = 50
        
        # --- SCORE COMPONENTS ---
        # 1. Traded Value Score (40% weight)
        value_score = 0
        if traded_value > 100_00_00_000:  # 100+ Crore
            value_score = 40
        elif traded_value > 50_00_00_000:  # 50+ Crore
            value_score = 30
        elif traded_value > 10_00_00_000:  # 10+ Crore
            value_score = 15
        else:
            value_score = 5
        
        # 2. Trend Score (30%)
        trend_score = 0
        if ltp > sma20:
            trend_score += 10
        if ltp > sma50:
            trend_score += 10
        if ltp > sma200:
            trend_score += 10
        
        # 3. RSI Score (20%)
        rsi_score = 0
        if rsi > 60:
            rsi_score = 20
        elif rsi > 50:
            rsi_score = 10
        
        # 4. Week Performance Score (10%)
        week_score = 0
        if week_change > 5:
            week_score = 10
        elif week_change > 2:
            week_score = 5
        
        # --- Final Score (0-100) ---
        total_score = value_score + trend_score + rsi_score + week_score
        score = min(100, total_score)
        score = max(0, score)
        
        # --- Status ---
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
        
        return status, score, round(ltp, 2), round(vol, 0), round(traded_value, 2), round(week_change, 2), round(sma50, 2), round(sma200, 2), round(rsi, 2), round(prev_close, 2)
    
    except Exception as e:
        logging.error(f"Error processing {symbol}: {e}")
        return "⏳ SYNCING", 0, 0, 0, 0, 0, 0, 0, 0, 0

# --- Fetch All Stocks with Retry ---
def fetch_all_stocks(universe):
    results = []
    for sym in universe:
        try:
            ticker = yf.Ticker(sym + ".NS")
            time.sleep(0.5)
            status, score, ltp, vol, traded_value, week_change, sma50, sma200, rsi, prev_close = get_institutional_score(ticker, sym)
            results.append((sym, status, score, ltp, vol, traded_value, week_change, sma50, sma200, rsi, prev_close))
        except Exception as e:
            logging.error(f"Error processing {sym}: {e}")
            results.append((sym, "❌ ERROR", 0, 0, 0, 0, 0, 0, 0, 0, 0))
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
        for sym, status, score, ltp, vol, traded_value, week_change, sma50, sma200, rsi, prev_close in results:
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
                f"₹{traded_value/1e7:.2f}Cr",
                f"{week_change}%",
                rsi,
                f"{sma50:.2f}",
                f"{sma200:.2f}",
                f"PC:{prev_close:.2f}",
                timestamp
            ])
        
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SUPER SCANNER 2.0 - {date_stamp}", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [['Symbol', 'LTP', 'Action', 'Trend Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Time']]
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
