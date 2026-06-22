# update_sheet.py – BULLETPROOF BATCH ENGINE (Flattened Columns)
import os
import json
import gspread
import yfinance as yf
import pytz
import logging
import sys
import time
import pandas as pd
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

# --- YOUR CHOSEN UNIVERSE (Aap isme jitne chahe stocks rakhein) ---
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
    'LODHA.NS', 'ESCORTS.NS', 'EXIDEIND.NS', 'LENSKART.NS', 'PIIND.NS',
    'UNOMINDA.NS', 'LINDEINDIA.NS', 'AIAENG.NS', 'IRCTC.NS', 'GLAXO.NS',
    'JKCEMENT.NS', 'GODREJIND.NS', 'APOLLOTYRE.NS', 'BERGAPAINT.NS',
    'KPRMILL.NS', 'ABBOTINDIA.NS', 'ETERNAL.NS', 'CUMMINSIND.NS',
    'SOLARINDS.NS', 'KALYANKJIL.NS', 'NYKAA.NS', 'MANKIND.NS', 'LT.NS',
    'JUBLFOOD.NS', 'POWERINDIA.NS', 'RVNL.NS', 'MCX.NS', 'BSE.NS',
    'SWIGGY.NS', 'DMART.NS', 'NAUKRI.NS', 'ONGC.NS', 'BPCL.NS',
    'HINDPETRO.NS', 'PETRONET.NS'
]

NIFTY_SYMBOL = "^NSEI"

def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Initializing Flattened Batch Engine...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        final_data = []
        
        # --- 1. FETCH NIFTY ---
        try:
            nifty_df = yf.download(NIFTY_SYMBOL, period="5d", progress=False)
            if not nifty_df.empty:
                ltp = float(nifty_df['Close'].iloc[-1])
                prev_close = float(nifty_df['Close'].iloc[-2]) if len(nifty_df) > 1 else ltp
                final_data.append(["NIFTY_INDEX", round(ltp, 2), "NIFTY", "INDEX", "-", "-", "-", 0, "-", "-", "-", round(prev_close, 2), "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", timestamp])
        except Exception as ne:
            logging.error(f"⚠️ Nifty fetch failed: {ne}")

        # --- 2. FETCH STOCKS BATCH ---
        logging.info(f"📦 Downloading Batch for {len(UNIVERSE)} stocks...")
        master_df = yf.download(UNIVERSE, period="5d", progress=False)
        
        if master_df.empty:
            logging.error("❌ yfinance returned a completely empty batch!")
        else:
            logging.info("⚙ Extracting data using robust cross-section logic...")
            for sym in UNIVERSE:
                try:
                    # Fail-safe method to extract individual stock's Close & Volume from multi-index
                    if ('Close', sym) in master_df.columns:
                        close_series = master_df[('Close', sym)].dropna()
                        volume_series = master_df[('Volume', sym)].dropna()
                    elif (sym, 'Close') in master_df.columns:
                        close_series = master_df[(sym, 'Close')].dropna()
                        volume_series = master_df[(sym, 'Volume')].dropna()
                    else:
                        continue
                        
                    if close_series.empty:
                        continue
                        
                    ltp = float(close_series.iloc[-1])
                    prev_close = float(close_series.iloc[-2]) if len(close_series) > 1 else ltp
                    volume = int(volume_series.iloc[-1]) if not volume_series.empty else 0
                    traded_value = ltp * volume
                    
                    final_data.append([
                        sym, round(ltp, 2), "⏳ HOLD", "TEST", 50,
                        volume, f"₹{traded_value/1e7:.2f}Cr", 0, 50,
                        round(ltp, 2), round(ltp, 2), round(prev_close, 2), "⏳ HOLD",
                        round(ltp, 2), round(ltp, 2), 0.02, "❌", "❌", "NO B/O", "➡️ Neutral",
                        round(ltp * 1.1, 2), round(ltp * 0.9, 2), timestamp
                    ])
                except Exception as inner_e:
                    logging.debug(f"Skipping structural variant for {sym}: {inner_e}")
                    continue

        logging.info(f"📊 Rows prepared to write: {len(final_data)}")
        
        # --- 3. FORCE UPDATE GOOGLE SHEET ---
        dash_sheet.clear()
        
        headers = [
            [f"📊 AI BRO SCANNER - {date_stamp} (FLATTENED BATCH)", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision', 'EMA21', 'VWAP', 'BB Squeeze', 'Momentum Burst', 'Consolidation', 'Breakout', 'Swing', '52W High', '52W Low', 'Time']
        ]
        
        payload = headers + final_data
        end_row = len(payload)
        
        # Single safe API update call
        dash_sheet.update(f"A1:W{end_row}", payload)
        dash_sheet.freeze(rows=2)
        
        logging.info("🚀 [BOOM] ALL STOCKS FLASHED SUCCESSFULLY IN GOOGLE SHEET!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Master Update Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
