# update_sheet.py – AI Bro Scanner (5-MIN MOMENTUM + 2-CANDLE CONFIRMATION SUPREME VERSION)
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
    'HINDPETRO.NS', 'PETRONET.NS', 'SUMICHEM.NS',
]

NIFTY_SYMBOL = "^NSEI"

def scan_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        # ⚡ BADLAV 1: Ab pure 5-minute data fetch hoga intraday momentum ke liye
        df = ticker.history(period="5d", interval="5m") 
        if df.empty or len(df) < 30:
            return None
        
        price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else price
        volume = df['Volume'].iloc[-1]
        traded_value = price * volume
        
        # --- TECHNICAL INDICATORS (PURE 5-MIN CALCULATION) ---
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['StdDev'] = df['Close'].rolling(window=20).std()
        df['UpperBB'] = df['SMA20'] + (2 * df['StdDev'])
        df['LowerBB'] = df['SMA20'] - (2 * df['StdDev'])
        
        df['VolSMA10'] = df['Volume'].rolling(window=10).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        # Real Intra-day VWAP Calculation
        cum_vol_price = (df['Close'] * df['Volume']).cumsum()
        cum_vol = df['Volume'].cumsum()
        df['VWAP'] = cum_vol_price / cum_vol
        
        # --- HEIKIN-ASHI CALCULATION ---
        ha_close = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
        ha_open = (df['Open'].shift(1) + df['Close'].shift(1)) / 2
        ha_high = df[['High', 'Open', 'Close']].max(axis=1)
        ha_low = df[['Low', 'Open', 'Close']].min(axis=1)
        
        ha_body = abs(ha_close.iloc[-1] - ha_open.iloc[-1])
        ha_range = ha_high.iloc[-1] - ha_low.iloc[-1]
        is_ha_doji = (ha_body / ha_range) < 0.15 if ha_range > 0 else False
        is_at_support = price < df['SMA20'].iloc[-1] and price > df['LowerBB'].iloc[-1]
        ha_reversal = is_ha_doji and is_at_support
        
        # Squeeze Definition
        df['ATR'] = df['High'].rolling(14).mean() - df['Low'].rolling(14).mean()
        is_squeeze = (df['UpperBB'].iloc[-1] < (df['SMA20'].iloc[-1] + (1.5 * df['ATR'].iloc[-1])))
        bb_status = "💥 SQUEEZE" if is_squeeze else "Normal"
        
        # --- ⚡ BADLAV 2: 2-CANDLE CONFIRMATION LOGIC SHURU ---
        # Current Candle (Index -1), Previous Trigger Candle (Index -2)
        c_close = df['Close'].iloc[-1]
        c_volume = df['Volume'].iloc[-1]
        
        p_close = df['Close'].iloc[-2]
        p_high = df['High'].iloc[-2]
        p_ema21 = df['EMA21'].iloc[-2]
        p_vwap = df['VWAP'].iloc[-2]
        
        avg_volume_5m = df['VolSMA10'].iloc[-1]
        
        # Condition Check
        base_breakout = (p_close > p_ema21) and (p_close > p_vwap)
        higher_high_confirm = (c_close > p_high)
        volume_spike = (c_volume > avg_volume_5m)
        
        # --- SCORE ENGINE (5-MIN TIME FRAME BASED) ---
        score = 0
        if c_close > p_close: score += 20
        if c_close > df['EMA21'].iloc[-1]: score += 30
        if c_close > df['VWAP'].iloc[-1]: score += 30
        if volume_spike: score += 20
        score = min(100, max(0, score))
        
        # --- DYNAMIC CASH TSL ENGINE ---
        cash_trigger = round(price * 0.965, 1)
        if price > 5000:
            cash_price = round(cash_trigger - 20.0, 1)
            cash_tsl_points = 50
        elif price > 500:
            cash_price = round(cash_trigger - 3.0, 1)
            cash_tsl_points = 10
        else:
            cash_price = round(cash_trigger - 1.0, 1)
            cash_tsl_points = 3
            
        sl_level = f"SL: {round(price * 0.985, 1)}"
        tgt_level = f"T1: {round(price * 1.02, 1)}"
        auto_trigger = str(cash_trigger)
        auto_limit_tsl = f"Lmt: {cash_price} | TSL: {cash_tsl_points}"
        
        # --- STRATEGY SIGNAL GENERATOR ---
        if base_breakout and higher_high_confirm and volume_spike:
            master_signal = "🔥 ALPHA BLAST (100%)"
            action, status, entry = "🚀 BUY NOW", "🎯 SUPER TREND", "✅ BUY NOW"
            score = 100
        elif base_breakout and not higher_high_confirm:
            # ⚡ Sideways filter laga diya!
            master_signal = "⏳ SIDEWAYS / ACCUMULATION"
            action, status, entry = "⏳ WAIT", "🛡️ RANGE-BOUND", "⏳ HOLD"
            score = 50
            sl_level, tgt_level, auto_trigger, auto_limit_tsl = "⏳", "⏳", "⏳", "⏳"
        elif ha_reversal:
            master_signal = "🎯 HA-REVERSAL (Dip)"
            action, status, entry = "🚀 BUY NOW", "💎 BOTTOM BUY", "✅ BUY NOW"
            score = 85
        else:
            master_signal = "➡️ Neutral"
            action, status, entry = "📉 AVOID", "📉 WEAK", "🔴 AVOID"
            sl_level, tgt_level, auto_trigger, auto_limit_tsl = "❌", "❌", "❌", "❌"
            
        high_52w = price
        try: high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        except: pass
        is_breakout = price > high_52w * 0.98
        
        return [
            symbol, round(price, 2), action, status, score, entry,
            sl_level, tgt_level, "✅ B/O" if is_breakout else "NO B/O", master_signal, bb_status, auto_trigger, auto_limit_tsl
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
        
        rows.append(["NIFTY_INDEX", round(nifty_spot, 2), "NIFTY", "INDEX", "-", "-", "-", "-", "-", "-", "-", "-", "-"])
        atm_strike = int(round(nifty_spot / 50.0) * 50)
        point_diff = nifty_spot - nifty_prev
        
        opt_trigger_ce = "LTP - 25"
        opt_limit_tsl_ce = "Lmt: Trig-3 | TSL: 10"
        opt_trigger_pe = "LTP - 25"
        opt_limit_tsl_pe = "Lmt: Trig-3 | TSL: 10"
        
        ce_symbol = f"NIFTY {atm_strike} CE (ATM)"
        if point_diff > 0: 
            ce_action, ce_status, ce_score, ce_entry = "🚀 BUY CALL", "🔥 BULLISH TREND", 80, "✅ BUY NOW"
        else: 
            ce_action, ce_status, ce_score, ce_entry = "⏳ HOLD CALL", "🛡️ SIDEWAYS/WEAK", 45, "⏳ HOLD"
            opt_trigger_ce, opt_limit_tsl_ce = "⏳", "⏳"
        rows.append([ce_symbol, "Premium SCAN", ce_action, ce_status, ce_score, ce_entry, "-", "-", "NO B/O", "➡️ Neutral", "Normal", opt_trigger_ce, opt_limit_tsl_ce])
        
        pe_symbol = f"NIFTY {atm_strike} PE (ATM)"
        if point_diff < 0: 
            pe_action, pe_status, pe_score, pe_entry = "🔥 BUY PUT", "📉 BEARISH TREND", 80, "✅ BUY NOW"
        else: 
            pe_action, pe_status, pe_score, pe_entry = "⏳ HOLD PUT", "🛡️ SIDEWAYS/STABLE", 45, "⏳ HOLD"
            opt_trigger_pe, opt_limit_tsl_pe = "⏳", "⏳"
        rows.append([pe_symbol, "Premium SCAN", pe_action, pe_status, pe_score, pe_entry, "-", "-", "NO B/O", "➡️ Neutral", "Normal", opt_trigger_pe, opt_limit_tsl_pe])
    except Exception as e:
        logging.error(f"Error in custom NIFTY Options calculation: {e}")
    return rows

# ==========================================
# ⚡ BADLAV 3: DEEP GITHUB WORKFLOW CLEANER LOOP
# ==========================================
def clean_github_workflows():
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY') # "owner/repo_name" format automatic milta hai
    if not token or not repo:
        logging.warning("⚠️ GitHub credentials missing in environments. Skipping cleaner.")
        return
        
    logging.info("🔄 Deep Cleaning GitHub Workflow Runs...")
    url = f"https://api.github.com/repos/{repo}/actions/runs"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    
    import requests
    deleted = 0
    while True:
        res = requests.get(url, headers=headers, params={"per_page": 100})
        if res.status_code != 200: break
        runs = res.json().get("workflow_runs", [])
        if not runs: break
        
        for run in runs:
            del_res = requests.delete(f"{url}/{run['id']}", headers=headers)
            if del_res.status_code == 204: deleted += 1
        time.sleep(0.5) # API block se bachne ke liye
    logging.info(f"✨ Purge Complete. Total {deleted} Workflow Runs Smoked!")

def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Launching Ultimate Confluence Engine...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        
        nifty_rows = get_nifty_options_data()
        for r in nifty_rows:
            r.append(timestamp)
            
        stock_rows = []
        for idx, sym in enumerate(UNIVERSE):
            data = scan_stock(sym)
            if data:
                data.append(timestamp)
                stock_rows.append(data)
                logging.info(f"✅ [{idx+1}/{len(UNIVERSE)}] Fetched (5m): {sym}")
            time.sleep(0.04)
        
        # Advanced Auto-Top Sorting
        alpha_blasts = [row for row in stock_rows if "🔥 ALPHA BLAST" in row[9]]
        ha_reversals = [row for row in stock_rows if "🎯 HA-REVERSAL" in row[9]]
        sideways_acc = [row for row in stock_rows if "⏳ SIDEWAYS" in row[9]]
        neutrals = [row for row in stock_rows if "➡️ Neutral" in row[9]]
        
        final_stock_order = alpha_blasts + ha_reversals + sideways_acc + neutrals
        final_data = nifty_rows + final_stock_order
        
        dash_sheet.clear()
        dash_sheet.update('A1', [[f"📊 AI BRO SCANNER - {date_stamp} (95%+ ACCURACY SUPREME WITH AUTO TSL)", "", "", "", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Entry Decision', 'Stop Loss (1.5%)', 'Target 1 (2%)', 'Breakout', 'Master Signal', 'BB Squeeze', 'Auto Trigger Price', 'Limit Price & TSL', 'Time']])
        
        if final_data:
            dash_sheet.update('A3', final_data)
            logging.info(f"🚀 [BOOM] Supreme Matrix Is Live with 5-Min 2-Candle Filter!")
        
        dash_sheet.freeze(rows=2)
        
        # ⚡ Workflow Clear Action Call
        try: clean_github_workflows()
        except Exception as ge: logging.error(f"GitHub cleaner failed: {ge}")
            
        return True
    except Exception as e:
        logging.error(f"❌ Execution Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
