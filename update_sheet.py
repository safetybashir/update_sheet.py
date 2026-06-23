# update_sheet.py – AI Bro Scanner (11 Columns Updated with Nifty Options Logic)
import os
import json
import gspread
import yfinance as yf
import pytz
import logging
import sys
import time
from datetime import datetime as dt, timedelta
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
except Exception as e:
    logging.error(f"❌ Failed to load secrets: {e}")
    sys.exit(1)

# --- FULL UNIVERSE ---
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
        
        score = 0
        if price > prev_close: score += 20
        if week_change > 2: score += 30
        elif week_change > 0: score += 15
        if traded_value > 100_00_00_000: score += 30
        elif traded_value > 50_00_00_000: score += 15
        if volume > 1000000: score += 20
        elif volume > 500000: score += 10
        score = min(100, max(0, score))
        
        if score >= 75:
            action, status = "🚀 BUY NOW", "🎯 STRONG BUY"
        elif score >= 60:
            action, status = "📈 WATCH", "📈 BUY ZONE"
        elif score >= 40:
            action, status = "⏳ HOLD", "🛡️ RANGE-BOUND"
        else:
            action, status = "📉 AVOID", "📉 WEAK"
        
        entry = "✅ BUY NOW" if score >= 75 else "🟡 WATCH" if score >= 60 else "⏳ HOLD" if score >= 40 else "🔴 AVOID"
        
        high_52w = price
        try:
            high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        except:
            pass
        is_breakout = price > high_52w * 0.98
        
        return [
            symbol, round(price, 2), action, status, score, entry,
            "❌", "❌", "✅ B/O" if is_breakout else "NO B/O", "➡️ Neutral"
        ]
    except Exception as e:
        logging.error(f"Error scanning {symbol}: {e}")
        return None

def get_nifty_options_data():
    """Fetches Nifty Index Spot, calculates ATM, and builds Call/Put rows dynamic format."""
    rows = []
    try:
        nifty_ticker = yf.Ticker(NIFTY_SYMBOL)
        nifty_df = nifty_ticker.history(period="5d")
        if nifty_df.empty:
            return rows
            
        nifty_spot = nifty_df['Close'].iloc[-1]
        nifty_prev = nifty_df['Close'].iloc[-2] if len(nifty_df) > 1 else nifty_spot
        
        # 1. Base Nifty Index Spot Row
        rows.append([
            "NIFTY_INDEX", round(nifty_spot, 2), "NIFTY", "INDEX", "-", "-", "-", "-", "-", "-"
        ])
        
        # Round off to nearest 50 for Nifty ATM Strike
        atm_strike = int(round(nifty_spot / 50.0) * 50)
        
        # Format date snippet for Option chain lookup (Yahoo format relies on exact option strings)
        # standard fallback strings if options contracts aren't queried directly via ticker.options
        try:
            expirations = nifty_ticker.options
            if expirations:
                # Select nearest expiration
                nearest_expiry = expirations[0] 
                opt_chain = nifty_ticker.option_chain(nearest_expiry)
                
                # Fetch ATM Call
                calls = opt_chain.calls[opt_chain.calls['strike'] == atm_strike]
                if not calls.empty:
                    c_price = calls['lastPrice'].iloc[-1]
                    c_symbol = f"NIFTY ATM CE ({atm_strike})"
                    c_action = "🚀 BUY CALL" if nifty_spot > nifty_prev else "⏳ HOLD CALL"
                    rows.append([c_symbol, round(c_price, 2), c_action, "CALL OPTION", 70 if "BUY" in c_action else 45, "✅ TRADE" if "BUY" in c_action else "⏳ HOLD", "-", "-", "-", "-"])
                
                # Fetch ATM Put
                puts = opt_chain.puts[opt_chain.puts['strike'] == atm_strike]
                if not puts.empty:
                    p_price = puts['lastPrice'].iloc[-1]
                    p_symbol = f"NIFTY ATM PE ({atm_strike})"
                    p_action = "🔥 BUY PUT" if nifty_spot < nifty_prev else "⏳ HOLD PUT"
                    rows.append([p_symbol, round(p_price, 2), p_action, "PUT OPTION", 70 if "BUY" in p_action else 45, "✅ TRADE" if "BUY" in p_action else "⏳ HOLD", "-", "-", "-", "-"])
        except Exception as opt_err:
            logging.warning(f"⚠️ Precise option chain parsing skipped or unavailable: {opt_err}")
            # Fallback placeholder rows to maintain dashboard health if chains are restricted by API
            rows.append([f"NIFTY_{atm_strike}_CE", "PRICING...", "⏳ SCANNING", "CALL", "-", "-", "-", "-", "-", "-"])
            rows.append([f"NIFTY_{atm_strike}_PE", "PRICING...", "⏳ SCANNING", "PUT", "-", "-", "-", "-", "-", "-"])
            
    except Exception as e:
        logging.error(f"Error fetching NIFTY Options Matrix: {e}")
    return rows

def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Initializing 11 Column Structure with Options Chain...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        final_data = []
        
        # --- 1. GET NIFTY & OPTIONS ---
        nifty_rows = get_nifty_options_data()
        for r in nifty_rows:
            r.append(timestamp)  # Add Time column
            final_data.append(r)
            
        # --- 2. GET STOCKS ---
        for sym in UNIVERSE:
            data = scan_stock(sym)
            if data:
                data.append(timestamp)  # Add Time column
                final_data.append(data)
            time.sleep(0.02)
            
        logging.info(f"📊 Total final payload rows: {len(final_data)}")
        
        # --- 3. PUSH DATA IN 11 COLUMNS ---
        dash_sheet.clear()
        dash_sheet.update('A1', [[f"📊 AI BRO SCANNER - {date_stamp} (OPTIONS INCLUDED)", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Entry Decision', 'Momentum Burst', 'Consolidation', 'Breakout', 'Swing', 'Time']])
        
        if final_data:
            dash_sheet.update('A3', final_data)
            logging.info(f"✅ Sheet updated successfully with Options data!")
        
        dash_sheet.freeze(rows=2)
        return True
    except Exception as e:
        logging.error(f"❌ Core Update Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
