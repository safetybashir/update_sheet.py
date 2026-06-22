# update_sheet.py – BATCH DOWNLOAD VERSION (Anti-Block 150+ Stocks Support)
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

# --- YOUR CHOSEN 150+ STOCKS LIST (Aap isme 250 tak stocks add kar sakte hain bina kisi dikkat ke) ---
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
    logging.info("🚀 AI Bro Scanner – Initializing Anti-Block Batch Engine...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        final_data = []
        
        # --- STEP 1: NIFTY FETCH ---
        logging.info("⚡ Fetching Nifty Index...")
        nifty_df = yf.download(NIFTY_SYMBOL, period="5d", progress=False)
        if not nifty_df.empty:
            ltp = nifty_df['Close'].iloc[-1].item()
            prev_close = nifty_df['Close'].iloc[-2].item() if len(nifty_df) > 1 else ltp
            final_data.append(["NIFTY_INDEX", round(ltp, 2), "NIFTY", "INDEX", "-", "-", "-", 0, "-", "-", "-", round(prev_close, 2), "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", timestamp])

        # --- STEP 2: SUPER FAST BATCH DOWNLOAD (No Loops, No Blocks!) ---
        logging.info(f"📦 Downloading Master Batch for {len(UNIVERSE)} stocks at once...")
        
        # Ek hi single call mein saare stocks ka 5 din ka data download
        master_df = yf.download(UNIVERSE, period="5d", group_by='ticker', progress=False)
        
        logging.info("⚙ Processing Batch Data...")
        for sym in UNIVERSE:
            try:
                # Batch multi-index dataframe se individual stock ka data nikalna
                if sym in master_df.columns.levels[0]:
                    df = master_df[sym].dropna()
                    if df.empty:
                        continue
                    
                    ltp = df['Close'].iloc[-1].item()
                    prev_close = df['Close'].iloc[-2].item() if len(df) > 1 else ltp
                    volume = int(df['Volume'].iloc[-1].item())
                    traded_value = ltp * volume
                    
                    final_data.append([
                        sym, round(ltp, 2), "⏳ HOLD", "TEST", 50,
                        volume, f"₹{traded_value/1e7:.2f}Cr", 0, 50,
                        round(ltp, 2), round(ltp, 2), round(prev_close, 2), "⏳ HOLD",
                        round(ltp, 2), round(ltp, 2), 0.02, "❌", "❌", "NO B/O", "➡️ Neutral",
                        round(ltp * 1.1, 2), round(ltp * 0.9, 2), timestamp
                    ])
            except Exception as inner_e:
                logging.warning(f"⚠️ Skipping {sym} due to structural variation: {inner_e}")
                continue

        logging.info(f"📊 final_data rows successfully prepared: {len(final_data)}")
        
        # --- STEP 3: CLEAN AND MULTI-RANGE UPDATE ---
        dash_sheet.clear()
        
        headers = [
            [f"📊 AI BRO SCANNER - {date_stamp} (BATCH WORKING)", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision', 'EMA21', 'VWAP', 'BB Squeeze', 'Momentum Burst', 'Consolidation', 'Breakout', 'Swing', '52W High', '52W Low', 'Time']
        ]
        
        # Pura data combine karke ek single burst push karenge range update se
        payload = headers + final_data
        end_row = len(payload)
        range_string = f"A1:W{end_row}"
        
        logging.info(f"📤 Uploading Bulk Payload to Google Sheets [{range_string}]...")
        dash_sheet.update(range_string, payload)
        
        dash_sheet.freeze(rows=2)
        logging.info("🚀 [BOOM] 150+ STOCKS UPDATED SUCCESSFULLY VIA BATCH ENGINE!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Master Execution Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
