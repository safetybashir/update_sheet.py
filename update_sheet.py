# update_sheet.py – SINGLE LOOP ENGINE (Anti-Block 150+ Stocks Success)
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

# --- YOUR FULL UNIVERSE (Aap isme 150-250 jitne chahe stocks add kijiye) ---
UNIVERSE = [
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HCLTECH.NS', 'WIPRO.NS', 'TECHM.NS',
    'HINDUNILVR.NS', 'BHARTIARTL.NS', 'SUNPHARMA.NS', 'DRREDDY.NS',
    'CIPLA.NS', 'TORNTPHARM.NS', 'DIVISLAB.NS', 'LUPIN.NS', 'ALKEM.NS',
    'BIOCON.NS', 'APOLLOHOSP.NS', 'FORTIS.NS', 'MAXHEALTH.NS', 'TATASTEEL.NS',
    'JSWSTEEL.NS', 'HINDALCO.NS', 'NATIONALUM.NS', 'JINDALSTEL.NS', 'COALINDIA.NS',
    'MARUTI.NS', 'TATAMOTORS.NS', 'M&M.NS', 'EICHERMOT.NS', 'HEROMOTOCO.NS',
    'BAJAJ-AUTO.NS', 'ASHOKLEY.NS', 'TVSMOTOR.NS', 'MOTHERSON.NS', 'TITAN.NS',
    'HAVELLS.NS', 'VOLTAS.NS', 'DIXON.NS', 'WHIRLPOOL.NS', 'NTPC.NS', 'POWERGRID.NS',
    'TATAPOWER.NS', 'JSWENERGY.NS', 'ULTRACEMCO.NS', 'SHREECEM.NS',
    'AMBUJACEM.NS', 'ACC.NS', 'DLF.NS', 'GODREJPROP.NS', 'OBEROIRLTY.NS',
    'PRESTIGE.NS', 'PHOENIXLTD.NS', 'INDIGO.NS', 'HAL.NS', 'BEL.NS',
    'PIDILITIND.NS', 'SRF.NS', 'ASTRAL.NS', 'APLAPOLLO.NS',
    'SUPREMEIND.NS', 'TATACONSUM.NS', 'TATAELXSI.NS', 'TATAINVEST.NS',
    'ABB.NS', 'SIEMENS.NS', 'BOSCHLTD.NS', 'CGPOWER.NS', 'KEI.NS',
    'LODHA.NS', 'ESCORTS.NS', 'EXIDEIND.NS', 'PIIND.NS',
    'UNOMINDA.NS', 'LINDEINDIA.NS', 'AIAENG.NS', 'IRCTC.NS', 'GLAXO.NS',
    'JKCEMENT.NS', 'GODREJIND.NS', 'APOLLOTYRE.NS', 'BERGAPAINT.NS',
    'KPRMILL.NS', 'ABBOTINDIA.NS', 'CUMMINSIND.NS',
    'SOLARINDS.NS', 'KALYANKJIL.NS', 'NYKAA.NS', 'MANKIND.NS', 'LT.NS',
    'JUBLFOOD.NS', 'RVNL.NS', 'MCX.NS', 'BSE.NS',
    'SWIGGY.NS', 'DMART.NS', 'NAUKRI.NS', 'ONGC.NS', 'BPCL.NS',
    'HINDPETRO.NS', 'PETRONET.NS'
]

NIFTY_SYMBOL = "^NSEI"

def get_simple_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d")
        if df.empty:
            logging.warning(f"⚠️ No data for {symbol}")
            return None
        
        ltp = df['Close'].iloc[-1]
        volume = int(df['Volume'].iloc[-1])
        traded_value = ltp * volume
        
        return [
            symbol, round(ltp, 2), "⏳ HOLD", "TEST", 50,
            volume, f"₹{traded_value/1e7:.2f}Cr", 0, 50,
            round(ltp, 2), round(ltp, 2), round(df['Close'].iloc[-2] if len(df) > 1 else ltp, 2), "⏳ HOLD",
            round(ltp, 2), round(ltp, 2), 0.02, "❌", "❌", "NO B/O", "➡️ Neutral",
            round(ltp * 1.1, 2), round(ltp * 0.9, 2)
        ]
    except Exception as e:
        logging.error(f"❌ Error in {symbol}: {e}")
        return None

def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Initializing Safe Loop Engine...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        final_data = []
        
        # 1. Fetch NIFTY
        try:
            nifty_ticker = yf.Ticker(NIFTY_SYMBOL)
            nifty_df = nifty_ticker.history(period="5d")
            if not nifty_df.empty:
                n_ltp = nifty_df['Close'].iloc[-1]
                n_prev = nifty_df['Close'].iloc[-2] if len(nifty_df) > 1 else n_ltp
                final_data.append(["NIFTY_INDEX", round(n_ltp, 2), "NIFTY", "INDEX", "-", "-", "-", 0, "-", "-", "-", round(n_prev, 2), "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", timestamp])
        except Exception as ne:
            logging.error(f"⚠️ Nifty failed: {ne}")

        # 2. Loop through each Stock (with a safe delay)
        logging.info(f"⚡ Processing {len(UNIVERSE)} stocks sequentially...")
        for idx, sym in enumerate(UNIVERSE):
            row = get_simple_stock_data(sym)
            if row:
                row.append(timestamp) # Append Time column
                final_data.append(row)
                logging.info(f"✅ [{idx+1}/{len(UNIVERSE)}] Added: {sym}")
            
            # Rate limit buffer to prevent Yahoo blocking
            time.sleep(0.25)
        
        logging.info(f"📊 Total rows collected: {len(final_data)}")
        
        # 3. Force Write to Sheet
        if len(final_data) > 1:
            logging.info("🧹 Clearing sheet and writing fresh data...")
            dash_sheet.clear()
            
            headers = [
                [f"📊 AI BRO SCANNER - {date_stamp} (SAFE LOOP WORKING)", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
                ['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision', 'EMA21', 'VWAP', 'BB Squeeze', 'Momentum Burst', 'Consolidation', 'Breakout', 'Swing', '52W High', '52W Low', 'Time']
            ]
            
            payload = headers + final_data
            end_row = len(payload)
            
            dash_sheet.update(f"A1:W{end_row}", payload)
            dash_sheet.freeze(rows=2)
            logging.info("🚀 [BOOM] SHEET UPDATED SUCCESSFULLY!")
            return True
        else:
            logging.error("❌ No stock data fetched.")
            return False
            
    except Exception as e:
        logging.error(f"❌ Execution Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
