# update_sheet.py – AI Bro Scanner (12 Columns MULTI-TIMEFRAME WITH AUTO-TOP SORTING)
import os
import json
import gspread
import yfinance as yf
import pytz
import logging
import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime as dt
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
except Exception as e:
    logging.error(f"❌ Failed to load secrets: {e}")
    sys.exit(1)

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
        df = ticker.history(period="1y") 
        if df.empty or len(df) < 50:
            return None
        
        price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else price
        volume = df['Volume'].iloc[-1]
        traded_value = price * volume
        
        weekly_bullish = price > df['Close'].iloc[-5] if len(df) >= 5 else True
        monthly_bullish = price > df['Close'].iloc[-20] if len(df) >= 20 else True
        
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['StdDev'] = df['Close'].rolling(window=20).std()
        df['UpperBB'] = df['SMA20'] + (2 * df['StdDev'])
        df['LowerBB'] = df['SMA20'] - (2 * df['StdDev'])
        
        df['ATR'] = df['High'].rolling(14).mean() - df['Low'].rolling(14).mean()
        df['LowerKC'] = df['SMA20'] - (1.5 * df['ATR'])
        df['UpperKC'] = df['SMA20'] + (1.5 * df['ATR'])
        
        df['VolSMA20'] = df['Volume'].rolling(window=20).mean()
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        is_squeeze = (df['UpperBB'].iloc[-1] < df['UpperKC'].iloc[-1]) and (df['LowerBB'].iloc[-1] > df['LowerKC'].iloc[-1])
        bb_status = "💥 SQUEEZE" if is_squeeze else "Normal"
        
        bb_breakout = price > df['UpperBB'].iloc[-2]
        volume_spike = volume > (df['VolSMA20'].iloc[-1] * 1.5)
        daily_trend_bullish = price > df['EMA20'].iloc[-1] and df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]
        
        score = 0
        if price > prev_close: score += 10
        if weekly_bullish: score += 20
        if monthly_bullish: score += 20
        if daily_trend_bullish: score += 20
        if traded_value > 50_00_00_000: score += 15
        if volume > df['VolSMA20'].iloc[-1]: score += 15
        score = min(100, max(0, score))
        
        if is_squeeze:
            master_signal = "⏳ SQUEEZING (Wait)"
            action, status, entry = "⏳ HOLD", "🛡️ COMPRESSING", "⏳ HOLD"
        elif bb_breakout and volume_spike and daily_trend_bullish and weekly_bullish and monthly_bullish:
            master_signal = "🔥 ALPHA BLAST (90%)"
            action, status, entry = "🚀 BUY NOW", "🎯 SUPER TREND", "✅ BUY NOW"
            score = 100
        else:
            master_signal = "➡️ Neutral"
            if score >= 75: action, status, entry = "🚀 BUY NOW", "🎯 STRONG BUY", "✅ BUY NOW"
            elif score >= 60: action, status, entry = "📈 WATCH", "📈 BUY ZONE", "🟡 WATCH"
            elif score >= 40: action, status, entry = "⏳ HOLD", "🛡️ RANGE-BOUND", "⏳ HOLD"
            else: action, status, entry = "📉 AVOID", "📉 WEAK", "🔴 AVOID"
            
        high_52w = price
        try: high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        except: pass
        is_breakout = price > high_52w * 0.98
        
        return [
            symbol, round(price, 2), action, status, score, entry,
            "❌", "❌", "✅ B/O" if is_breakout else "NO B/O", master_signal, bb_status
        ]
    except Exception as e:
        logging.error(f"Error scanning {symbol}: {e}")
        return None

def get_nifty_options_data():
    rows = []
    try:
        nifty_ticker = yf.Ticker(NIFTY_SYMBOL)
        nifty_df = nifty_ticker.history(period="5d")
        if nifty_df.empty:
            return rows
            
        nifty_spot = float(nifty_df['Close'].iloc[-1])
        nifty_prev = float(nifty_df['Close'].iloc[-2]) if len(nifty_df) > 1 else nifty_spot
        
        rows.append([
            "NIFTY_INDEX", round(nifty_spot, 2), "NIFTY", "INDEX", "-", "-", "-", "-", "-", "-", "-"
        ])
        
        atm_strike = int(round(nifty_spot / 50.0) * 50)
        point_diff = nifty_spot - nifty_prev
        
        ce_symbol = f"NIFTY {atm_strike} CE (ATM)"
        if point_diff > 0: ce_action, ce_status, ce_score, ce_entry = "🚀 BUY CALL", "🔥 BULLISH TREND", 80, "✅ BUY NOW"
        else: ce_action, ce_status, ce_score, ce_entry = "⏳ HOLD CALL", "🛡️ SIDEWAYS/WEAK", 45, "⏳ HOLD"
        rows.append([ce_symbol, "Premium SCAN", ce_action, ce_status, ce_score, ce_entry, "❌", "❌", "NO B/O", "➡️ Neutral", "Normal"])
        
        pe_symbol = f"NIFTY {atm_strike} PE (ATM)"
        if point_diff < 0: pe_action, pe_status, pe_score, pe_entry = "🔥 BUY PUT", "📉 BEARISH TREND", 80, "✅ BUY NOW"
        else: pe_action, pe_status, pe_score, pe_entry = "⏳ HOLD PUT", "🛡️ SIDEWAYS/STABLE", 45, "⏳ HOLD"
        rows.append([pe_symbol, "Premium SCAN", pe_action, pe_status, pe_score, pe_entry, "❌", "❌", "NO B/O", "➡️ Neutral", "Normal"])
            
    except Exception as e:
        logging.error(f"Error in custom NIFTY Options calculation: {e}")
    return rows

def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Initializing Multi-Timeframe Matrix with Auto-Top Sorting...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        
        # 1. Fetch Nifty Rows (Hamesha top par rahenge)
        nifty_rows = get_nifty_options_data()
        for r in nifty_rows:
            r.append(timestamp)
            
        # 2. Fetch Stock Universe
        stock_rows = []
        for idx, sym in enumerate(UNIVERSE):
            data = scan_stock(sym)
            if data:
                data.append(timestamp)
                stock_rows.append(data)
                logging.info(f"✅ [{idx+1}/{len(UNIVERSE)}] Fetched: {sym}")
            time.sleep(0.04)
        
        # --- 🔥 CRITICAL MAGIC: AUTO-TOP SORTING LOGIC ---
        # Stocks ko prioritize karenge unke Master Signal (Column Index 9) ke basis par
        alpha_blasts = [row for row in stock_rows if "🔥 ALPHA BLAST" in row[9]]
        squeezings = [row for row in stock_rows if "⏳ SQUEEZING" in row[9]]
        neutrals = [row for row in stock_rows if "➡️ Neutral" in row[9]]
        
        # Final priority list assemble karenge
        final_stock_order = alpha_blasts + squeezings + neutrals
        final_data = nifty_rows + final_stock_order
        
        # 3. Push to Sheet
        dash_sheet.clear()
        dash_sheet.update('A1', [[f"📊 AI BRO SCANNER - {date_stamp} (AUTO-TOP SORTED LIVE)", "", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Entry Decision', 'Momentum Burst', 'Consolidation', 'Breakout', 'Master Signal', 'BB Squeeze', 'Time']])
        
        if final_data:
            dash_sheet.update('A3', final_data)
            logging.info(f"🚀 [BOOM] Grid sorted with Alpha & Squeeze on TOP flawlessly!")
        
        dash_sheet.freeze(rows=2)
        return True
    except Exception as e:
        logging.error(f"❌ Execution Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
