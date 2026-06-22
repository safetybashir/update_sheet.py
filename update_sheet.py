# update_sheet.py – AI Bro Scanner (Sirf 12 Columns)
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
except Exception as e:
    logging.error(f"❌ Failed to load secrets: {e}")
    sys.exit(1)

# --- FULL UNIVERSE (F&O Stocks Only) ---
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

def scan_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d")
        if df.empty:
            return None
        
        price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else price
        volume = df['Volume'].iloc[-1]
        traded_value = price * volume
        week_change = ((price - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100 if len(df) >= 5 else 0
        
        # --- REAL SCORE ---
        score = 0
        if price > prev_close: score += 20
        if week_change > 2: score += 30
        elif week_change > 0: score += 15
        if traded_value > 100_00_00_000: score += 30
        elif traded_value > 50_00_00_000: score += 15
        if volume > 1000000: score += 20
        elif volume > 500000: score += 10
        score = min(100, max(0, score))
        
        # --- REAL ACTION & STATUS ---
        if score >= 75:
            action, status = "🚀 BUY NOW", "🎯 STRONG BUY"
        elif score >= 60:
            action, status = "📈 WATCH", "📈 BUY ZONE"
        elif score >= 40:
            action, status = "⏳ HOLD", "🛡️ RANGE-BOUND"
        else:
            action, status = "📉 AVOID", "📉 WEAK"
        
        entry = "✅ BUY NOW" if score >= 75 else "🟡 WATCH" if score >= 60 else "⏳ HOLD" if score >= 40 else "🔴 AVOID"
        
        # --- BREAKOUT ---
        high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        is_breakout = price > high_52w * 0.98
        
        return {
            'symbol': symbol,
            'ltp': round(price, 2),
            'action': action,
            'status': status,
            'score': score,
            'entry': entry,
            'momentum_burst': "❌",
            'consolidation': "❌",
            'breakout': "✅ B/O" if is_breakout else "NO B/O",
            'swing': "➡️ Neutral",
        }
    except Exception as e:
        logging.error(f"Error scanning {symbol}: {e}")
        return None

def get_nifty_data():
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
            'entry': "-",
            'momentum_burst': "-",
            'consolidation': "-",
            'breakout': "-",
            'swing': "-",
        }
    except Exception as e:
        logging.error(f"Error fetching NIFTY: {e}")
        return None

def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – FINAL (12 Columns)")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        final_data = []
        
        nifty = get_nifty_data()
        if nifty:
            final_data.append([
                nifty['symbol'], nifty['ltp'], nifty['action'], nifty['status'],
                nifty['score'], nifty['entry'], nifty['momentum_burst'],
                nifty['consolidation'], nifty['breakout'], nifty['swing'], timestamp
            ])
        
        for sym in UNIVERSE:
            data = scan_stock(sym)
            if data:
                final_data.append([
                    data['symbol'], data['ltp'], data['action'], data['status'],
                    data['score'], data['entry'], data['momentum_burst'],
                    data['consolidation'], data['breakout'], data['swing'], timestamp
                ])
            time.sleep(0.02)
        
        logging.info(f"📊 final_data rows: {len(final_data)}")
        
        dash_sheet.clear()
        dash_sheet.update('A1', [[f"📊 AI BRO SCANNER - {date_stamp} (FINAL)", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Entry Decision',
                                 'Momentum Burst', 'Consolidation', 'Breakout', 'Swing', 'Time']])
        
        if final_data:
            dash_sheet.update('A3', final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        else:
            dash_sheet.update('A3', [["TEST", 100, "HOLD", "TEST", 50, "HOLD", "✅", "✅", "NO B/O", "➡️ Neutral", timestamp]])
            logging.info("✅ Added test row")
        
        dash_sheet.freeze(rows=2)
        logging.info("✅ Update completed!")
        return True
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
