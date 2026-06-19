# update_sheet.py
import os
import json
import gspread
import yfinance as yf
import pytz
import pandas as pd
import logging
import sys
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

# --- Stock Universe (Nifty 50 + Midcap) ---
UNIVERSE = [
    # Nifty 50
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR',
    'ICICIBANK', 'ITC', 'KOTAKBANK', 'SBIN', 'BHARTIARTL',
    'LT', 'AXISBANK', 'BAJFINANCE', 'HCLTECH', 'WIPRO',
    'SUNPHARMA', 'TITAN', 'MARUTI', 'ONGC', 'NTPC',
    # Your existing universe
    'TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI', 'TORNTPHARM',
    'AVANTIFEED', 'DIXON', 'EICHERMOT', 'RVNL', 'KAYNES',
    'WAAREEENER', 'SOLARINDS', 'WABAG', 'ALKEM', 'DIVISLAB',
    'JSWSTEEL', 'APOLLOHOSP', 'POWERINDIA', 'BAJAJ-AUTO',
    'ULTRACEMCO', 'INDIGO', 'MAXHEALTH'
]

# --- Institutional Score Logic ---
def get_institutional_score(ticker_obj):
    """Calculate institutional score based on price action and volume."""
    try:
        df = ticker_obj.history(period="5d")
        if df.empty:
            return "⏳ NO DATA", 0, 0, 0, 0
        
        ltp = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else ltp
        high = df['High'].iloc[-1]
        low = df['Low'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].mean()
        
        # Calculate 5-day change
        week_change = ((ltp - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100 if len(df) >= 5 else 0
        
        # Score logic
        score = 5  # neutral
        if ltp > prev_close and vol > avg_vol * 1.5:
            score = 11  # 🎯 Strong breakout with volume
        elif ltp > prev_close and vol > avg_vol:
            score = 9   # 📈 Healthy uptrend
        elif ltp > prev_close:
            score = 7   # 🟡 Mild buying
        elif ltp < prev_close and vol > avg_vol * 1.5:
            score = 2   # 📉 Institutional dumping
        elif ltp < prev_close:
            score = 3   # 🔻 Mild selling
        
        # Status
        if score >= 9:
            status = "🎯 STRONG BUY"
        elif score >= 7:
            status = "📈 BUY ZONE"
        elif score <= 2:
            status = "⚠️ DUMPING"
        else:
            status = "🛡️ RANGE-BOUND"
        
        return status, score, round(ltp, 2), round(vol, 0), round(week_change, 2)
    
    except Exception as e:
        logging.error(f"Error calculating score: {e}")
        return "⏳ SYNCING", 0, 0, 0, 0

# --- Fetch All Stocks in Parallel ---
def fetch_all_stocks(universe):
    """Fetch data for all stocks using ThreadPoolExecutor."""
    results = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_symbol = {
            executor.submit(get_institutional_score, yf.Ticker(sym + ".NS")): sym
            for sym in universe
        }
        for future in as_completed(future_to_symbol):
            sym = future_to_symbol[future]
            try:
                status, score, ltp, vol, week_change = future.result()
                results.append((sym, status, score, ltp, vol, week_change))
            except Exception as e:
                logging.error(f"Error processing {sym}: {e}")
                results.append((sym, "❌ ERROR", 0, 0, 0, 0))
    return results

# --- Main Update Function ---
def update_google_sheet():
    """Main function to update Google Sheet."""
    logging.info("🚀 Starting sheet update process...")
    
    try:
        # 1. Authenticate with Google
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info("✅ Connected to Google Sheet")
        
        # 2. Fetch data
        results = fetch_all_stocks(UNIVERSE)
        logging.info(f"📊 Fetched data for {len(results)} stocks")
        
        # 3. Prepare data for sheet
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        # Sort by score (highest first)
        results.sort(key=lambda x: x[2], reverse=True)
        
        final_data = []
        for sym, status, score, ltp, vol, week_change in results:
            # Action Plan based on score
            if score >= 9:
                action = "🚀 BUY NOW"
            elif score >= 7:
                action = "📈 WATCH"
            elif score <= 2:
                action = "📉 SELL"
            else:
                action = "⏳ HOLD"
            
            final_data.append([
                sym + ".NS",
                ltp,
                action,
                status,
                score,
                f"{vol:,}",
                f"{week_change}%",
                timestamp
            ])
        
        # 4. Clear and Update Sheet
        dash_sheet.clear()
        
        # Update Header with date
        header = [[f"📊 DASHBOARD LIVE - {date_stamp}", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [['Symbol', 'LTP', 'Action', 'Trend Status', 'Score', 'Volume', 'Week %', 'Time']]
        dash_sheet.update(range_name='A2', values=header2)
        
        # Update Data (starting from A3)
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows in sheet")
        
        # 5. Freeze rows
        dash_sheet.freeze(rows=2)
        
        logging.info("✅ Sheet update completed successfully!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed to update sheet: {e}")
        return False

# --- Run ---
if __name__ == "__main__":
    update_google_sheet()
