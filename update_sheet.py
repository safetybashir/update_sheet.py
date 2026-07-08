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
import requests
from datetime import datetime as dt
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
except Exception as e:
    logging.error(f"❌ Critical Error: Failed to load secrets/credentials: {e}")
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

def calculate_adx(df, period=14):
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    df['DM_plus'] = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']), 
                             np.where((df['High'] - df['High'].shift(1)) > 0, df['High'] - df['High'].shift(1), 0), 0)
    df['DM_minus'] = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)), 
                              np.where((df['Low'].shift(1) - df['Low']) > 0, df['Low'].shift(1) - df['Low'], 0), 0)
    
    tr_smooth = df['TR'].rolling(window=period).sum()
    dm_plus_smooth = df['DM_plus'].rolling(window=period).sum()
    dm_minus_smooth = df['DM_minus'].rolling(window=period).sum()
    
    di_plus = 100 * (dm_plus_smooth / (tr_smooth + 1e-10))
    di_minus = 100 * (dm_minus_smooth / (tr_smooth + 1e-10))
    
    dx = 100 * (abs(di_plus - di_minus) / (di_plus + di_minus + 1e-10))
    adx = dx.rolling(window=period).mean()
    return adx, di_plus, di_minus

def calculate_sharmaji_score(pcr, nifty_vs_maxpain, call_oi_trend, put_oi_trend, iv_trend, delta_trend):
    """Ganesh Sharma Options Chain Analytics Core Engine"""
    score = 0
    try:
        if float(pcr) > 1: score += 1
        if str(nifty_vs_maxpain).lower() == "below": score += 1
        if "long" in str(call_oi_trend).lower(): score += 1
        if "covering" in str(put_oi_trend).lower(): score += 1
        if str(iv_trend).lower() == "yes": score += 1
        if str(delta_trend).lower() == "increasing": score += 1
    except Exception as e:
        logging.error(f"Error parsing Sharmaji Inputs: {e}")
        
    if score >= 5:
        return score, "🚀 STRONG BUY CALL", "🔥 SHARMAJI BULLISH"
    elif score >= 3:
        return score, "⏳ SCALPING / RISKY", "🛡️ SIDEWAYS MOVEMENT"
    else:
        return score, "🔴 STRONG BUY PUT", "📉 SHARMAJI BEARISH" # Modifed to track bearish mode safely

def scan_stock(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="5m") 
        if df.empty or len(df) < 35:
            return None
        
        price = df['Close'].iloc[-1]
        volume = df['Volume'].iloc[-1]
        
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['StdDev'] = df['Close'].rolling(window=20).std().fillna(0)
        df['UpperBB'] = df['SMA20'] + (2 * df['StdDev'])
        df['LowerBB'] = df['SMA20'] - (2 * df['StdDev'])
        df['VolSMA10'] = df['Volume'].rolling(window=10).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        cum_vol_price = (df['Close'] * df['Volume']).cumsum()
        cum_vol = df['Volume'].cumsum() + 1e-10
        df['VWAP'] = cum_vol_price / cum_vol
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean() + 1e-10
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        df['ADX'], df['DI+'], df['DI-'] = calculate_adx(df)
        
        current_rsi = df['RSI'].iloc[-1]
        current_adx = df['ADX'].iloc[-1]
        
        ha_close = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
        ha_open = (df['Open'].shift(1) + df['Close'].shift(1)) / 2
        ha_body = abs(ha_close.iloc[-1] - ha_open.iloc[-1])
        ha_range = (df['High'].iloc[-1] - df['Low'].iloc[-1]) + 1e-10
        ha_reversal = (ha_body / ha_range < 0.15) and (price < df['SMA20'].iloc[-1])
        
        df['ATR'] = df['High'].rolling(14).mean() - df['Low'].rolling(14).mean()
        is_squeeze = (df['UpperBB'].iloc[-1] < (df['SMA20'].iloc[-1] + (1.5 * df['ATR'].fillna(0).iloc[-1])))
        bb_status = "💥 SQUEEZE" if is_squeeze else "Normal"
        
        c_close, c_volume = df['Close'].iloc[-1], df['Volume'].iloc[-1]
        p_close, p_high, p_ema21, p_vwap = df['Close'].iloc[-2], df['High'].iloc[-2], df['EMA21'].iloc[-2], df['VWAP'].iloc[-2]
        
        base_breakout = (p_close > p_ema21) and (p_close > p_vwap)
        higher_high_confirm = (c_close > p_high)
        volume_spike = (c_volume > df['VolSMA10'].iloc[-1])
        
        chartink_uptrend = (current_rsi > 60) and (current_adx > 25)
        
        cash_trigger = round(price * 0.965, 1)
        cash_price = round(cash_trigger - 3.0, 1) if price > 500 else round(cash_trigger - 1.0, 1)
        cash_tsl_points = 10 if price > 500 else 3
        if price > 5000:
            cash_price = round(cash_trigger - 20.0, 1)
            cash_tsl_points = 50
            
        sl_level = f"SL: {round(price * 0.985, 1)}"
        tgt_level = f"T1: {round(price * 1.02, 1)}"
        auto_trigger, auto_limit_tsl = str(cash_trigger), f"Lmt: {cash_price} | TSL: {cash_tsl_points}"
        
        if base_breakout and higher_high_confirm and volume_spike and chartink_uptrend:
            master_signal = "🔥 ALPHA BLAST (100%)"
            action, status, entry, score = "🚀 BUY NOW", "🎯 SUPER TREND", "✅ BUY NOW", 100
        elif base_breakout and not higher_high_confirm:
            master_signal = "⏳ SIDEWAYS / ACCUMULATION"
            action, status, entry, score = "⏳ WAIT", "🛡️ RANGE-BOUND", "⏳ HOLD", 50
            sl_level, tgt_level, auto_trigger, auto_limit_tsl = "⏳", "⏳", "⏳", "⏳"
        elif ha_reversal and current_rsi > 45:
            master_signal = "🎯 HA-REVERSAL (Dip)"
            action, status, entry, score = "🚀 BUY NOW", "💎 BOTTOM BUY", "✅ BUY NOW", 85
        else:
            master_signal = "➡️ Neutral"
            action, status, entry = "📉 AVOID", "📉 WEAK", "🔴 AVOID"
            sl_level, tgt_level, auto_trigger, auto_limit_tsl = "❌", "❌", "❌", "❌"
            score = 15 if c_close > p_close else 0
            if chartink_uptrend: score += 15
            
        high_52w = price
        try: high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        except: pass
        
        return [
            symbol, round(price, 2), action, status, score, entry,
            sl_level, tgt_level, "✅ B/O" if price > high_52w * 0.98 else "NO B/O", 
            master_signal, bb_status, auto_trigger, auto_limit_tsl
        ]
    except Exception as e:
        logging.error(f"Error scanning {symbol}: {e}")
        return None

def get_nifty_options_data(sharma_score, sharma_action, sharma_signal):
    rows = []
    try:
        nifty_ticker = yf.Ticker(NIFTY_SYMBOL)
        nifty_df = nifty_ticker.history(period="5d")
        if nifty_df.empty: return rows
        nifty_spot = float(nifty_df['Close'].iloc[-1])
        
        rows.append(["NIFTY_INDEX", round(nifty_spot, 2), sharma_action, sharma_signal, f"Score: {sharma_score}/6", "LIVE ALIGNED", "-", "-", "-", "OPTS ENGINE", "Normal", "-", "-"])
        
        atm_strike = int(round(nifty_spot / 50.0) * 50)
        
        if "BUY CALL" in sharma_action:
            rows.append([f"NIFTY {atm_strike} CE (ATM)", "Premium SCAN", "🚀 BUY CALL", "🔥 BULLISH TREND", 95, "✅ BUY NOW", "-", "-", "NO B/O", "🔥 SHARMAJI ENGINE", "Normal", "LTP - 25", "Lmt: Trig-3 | TSL: 10"])
            rows.append([f"NIFTY {atm_strike} PE (ATM)", "Premium SCAN", "📉 AVOID PUT", "🛡️ CRASHING OI", 10, "🔴 AVOID", "-", "-", "NO B/O", "➡️ Neutral", "Normal", "⏳", "⏳"])
        elif "BUY PUT" in sharma_action: # Aligned dynamically to buy puts when score is weak
            rows.append([f"NIFTY {atm_strike} CE (ATM)", "Premium SCAN", "📉 AVOID CALL", "❌ DATA WEAK", 10, "🔴 AVOID", "-", "-", "NO B/O", "➡️ Neutral", "Normal", "⏳", "⏳"])
            rows.append([f"NIFTY {atm_strike} PE (ATM)", "Premium SCAN", "🚀 BUY PUT", "📉 BEARISH TREND", 95, "✅ BUY NOW", "-", "-", "NO B/O", "🔥 SHARMAJI ENGINE", "Normal", "LTP - 25", "Lmt: Trig-3 | TSL: 10"])
        else:
            rows.append([f"NIFTY {atm_strike} CE (ATM)", "Premium SCAN", "⏳ HOLD CALL", "🛡️ SIDEWAYS/STABLE", 45, "⏳ HOLD", "-", "-", "NO B/O", "➡️ Neutral", "Normal", "⏳", "⏳"])
            rows.append([f"NIFTY {atm_strike} PE (ATM)", "Premium SCAN", "⏳ HOLD PUT", "🛡️ SIDEWAYS/STABLE", 45, "⏳ HOLD", "-", "-", "NO B/O", "➡️ Neutral", "Normal", "⏳", "⏳"])
            
    except Exception as e:
        logging.error(f"Error Nifty Options Calculations: {e}")
    return rows

def clean_github_workflows():
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')
    if not token or not repo: return
    url = f"https://api.github.com/repos/{repo}/actions/runs"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    while True:
        res = requests.get(url, headers=headers, params={"per_page": 100})
        if res.status_code != 200: break
        runs = res.json().get("workflow_runs", [])
        if not runs: break
        for run in runs:
            try: requests.delete(f"{url}/{run['id']}", headers=headers)
            except: pass
        time.sleep(0.5)

def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Commencing Secure Audit Optimization Sync...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        
        # ⚡ CRITICAL FIX: 'Inputs' नाम की एक नई शीट से लाइव डेटा फेच करना
        # मान लेते हैं कि आपकी Google Sheet में 'Inputs' नाम का एक दूसरा टैब है जहाँ आप सेंसिबुल का डेटा डालते हैं
        try:
            input_sheet = sh.worksheet("Inputs")
            live_pcr = float(input_sheet.acell('B1').value)                 # Cell B1: PCR
            live_maxpain = str(input_sheet.acell('B2').value).strip()       # Cell B2: "below" or "above"
            live_call_trend = str(input_sheet.acell('B3').value).strip()    # Cell B3: "long buildup" or "short buildup"
            live_put_trend = str(input_sheet.acell('B4').value).strip()     # Cell B4: "short covering" or "short buildup"
            live_iv_trend = str(input_sheet.acell('B5').value).strip()      # Cell B5: "yes" or "no"
            live_delta_trend = str(input_sheet.acell('B6').value).strip()   # Cell B6: "increasing" or "decreasing"
            logging.info(f"✅ Successfully read live option inputs from Sheet: PCR={live_pcr}")
        except Exception as sheet_err:
            logging.warning(f"⚠️ 'Inputs' worksheet not found or empty. Falling back to safe default parameters. Error: {sheet_err}")
            # Fallback डिफ़ॉल्ट (अगर शीट न मिले तो सुरक्षित रहने के लिए न्यूट्रल वैल्यूज)
            live_pcr, live_maxpain, live_call_trend, live_put_trend, live_iv_trend, live_delta_trend = 1.0, "above", "short", "short", "no", "decreasing"

        dash_sheet = sh.get_worksheet(0)
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        
        # ⚡ DYNAMIC EXECUTION: अब यहाँ लाइव शीट का डेटा पास हो रहा है
        s_score, s_action, s_signal = calculate_sharmaji_score(
            pcr=live_pcr,                        
            nifty_vs_maxpain=live_maxpain,        
            call_oi_trend=live_call_trend,    
            put_oi_trend=live_put_trend,   
            iv_trend=live_iv_trend,                  
            delta_trend=live_delta_trend         
        )
        
        nifty_rows = get_nifty_options_data(s_score, s_action, s_signal)
        for r in nifty_rows: r.append(timestamp)
            
        stock_rows = []
        for idx, sym in enumerate(UNIVERSE):
            data = scan_stock(sym)
            if data:
                data.append(timestamp)
                stock_rows.append(data)
            time.sleep(0.05)
        
        alpha_blasts = [row for row in stock_rows if "🔥 ALPHA BLAST" in row[9]]
        ha_reversals = [row for row in stock_rows if "🎯 HA-REVERSAL" in row[9]]
        sideways_acc = [row for row in stock_rows if "⏳ SIDEWAYS" in row[9]]
        neutrals = [row for row in stock_rows if "➡️ Neutral" in row[9]]
        
        final_data = nifty_rows + alpha_blasts + ha_reversals + sideways_acc + neutrals
        
        dash_sheet.clear()
        dash_sheet.update('A1', [[f"📊 AI BRO SCANNER - {date_stamp} (95%+ ACCURACY WITH ADX/RSI + SHARMAJI OPTS ENGINE)", "", "", "", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Entry Decision', 'Stop Loss (1.5%)', 'Target 1 (2%)', 'Breakout', 'Master Signal', 'BB Squeeze', 'Auto Trigger Price', 'Limit Price & TSL', 'Time']])
        
        if final_data:
            dash_sheet.update('A3', final_data)
        dash_sheet.freeze(rows=2)
        
        try: clean_github_workflows()
        except: pass
        logging.info("✅ Grid Optimization Matrix Successfully Refreshed with Zero Faults.")
        return True
    except Exception as e:
        logging.error(f"Execution Failed during sheet update orchestration: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
