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
    logging.error(f"❌ Critical Error: {e}")
    sys.exit(1)

UNIVERSE = [
    'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HCLTECH.NS', 'WIPRO.NS', 'TECHM.NS', 'MAXHEALTH.NS'
    'HINDUNILVR.NS', 'BHARTIARTL.NS', 'SUNPHARMA.NS', 'DRREDDY.NS', 'MAZDOCK.NS', 'COCHINSHIP.NS',
    'CIPLA.NS', 'TORNTPHARM.NS', 'DIVISLAB.NS', 'LUPIN.NS', 'ALKEM.NS', 'GRSE.NS', 'PREMIERENE.NS',
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
    'HINDPETRO.NS', 'PETRONET.NS', 'SUMICHEM.NS', 'PERSISTENT.NS', 'CDSL.NS', 
]

NIFTY_SYMBOL = "^NSEI"

def calculate_adx(df, period=14):
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['DM_plus'] = np.where((df['High'] - df['High'].shift(1)) > (df['Low'].shift(1) - df['Low']), np.where((df['High'] - df['High'].shift(1)) > 0, df['High'] - df['High'].shift(1), 0), 0)
    df['DM_minus'] = np.where((df['Low'].shift(1) - df['Low']) > (df['High'] - df['High'].shift(1)), np.where((df['Low'].shift(1) - df['Low']) > 0, df['Low'].shift(1) - df['Low'], 0), 0)
    tr_smooth = df['TR'].rolling(window=period).sum()
    di_plus = 100 * (df['DM_plus'].rolling(window=period).sum() / (tr_smooth + 1e-10))
    di_minus = 100 * (df['DM_minus'].rolling(window=period).sum() / (tr_smooth + 1e-10))
    dx = 100 * (abs(di_plus - di_minus) / (di_plus + di_minus + 1e-10))
    return dx.rolling(window=period).mean(), di_plus, di_minus

def calculate_sharmaji_score(pcr, nifty_vs_maxpain, call_oi_trend, put_oi_trend, iv_trend, delta_trend):
    score = 0
    try:
        if float(pcr) > 1: score += 1
        if str(nifty_vs_maxpain).lower() == "below": score += 1
        if "long" in str(call_oi_trend).lower(): score += 1
        if "covering" in str(put_oi_trend).lower(): score += 1
        if str(iv_trend).lower() == "yes": score += 1
        if str(delta_trend).lower() == "increasing": score += 1
    except: pass
    return score

def check_fundamentals(ticker_obj):
    try:
        info = ticker_obj.info
        roe = info.get('returnOnEquity', 0.16)
        debt = info.get('debtToEquity', 0.5)
        if roe is None: roe = 0.16
        if debt is None: debt = 0.5
        return roe > 0.12 and debt < 2.0
    except: return True

def get_expiry_risk_status():
    try:
        now_ist = dt.now(pytz.timezone('Asia/Kolkata'))
        if now_ist.day >= 22:
            return "⚠️ EXPIRE RISK: NEXT SERIES"
        return "Normal"
    except: return "Normal"

def scan_stock(symbol, sharma_score, live_delta_trend):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="5m") 
        df_15 = ticker.history(period="5d", interval="15m")
        
        if df.empty or len(df) < 35 or df_15.empty or len(df_15) < 15: return None
        
        price = df['Close'].iloc[-1]
        volume = df['Volume'].iloc[-1]
        
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['StdDev'] = df['Close'].rolling(window=20).std().fillna(0)
        df['UpperBB'] = df['SMA20'] + (2 * df['StdDev'])
        df['LowerBB'] = df['SMA20'] - (2 * df['StdDev'])
        df['VolSMA10'] = df['Volume'].rolling(window=10).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        cum_vol_price = (df['Close'] * df['Volume']).cumsum()
        df['VWAP'] = cum_vol_price / (df['Volume'].cumsum() + 1e-10)
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean() + 1e-10
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        df['ADX'], _, _ = calculate_adx(df)
        
        current_rsi = df['RSI'].iloc[-1]
        current_adx = df['ADX'].iloc[-1]
        
        try:
            prev_close = ticker.info.get('previousClose', df['Close'].iloc[0])
            day_gain_pct = ((price - prev_close) / prev_close) * 100
        except:
            day_gain_pct = 0.0
        
        last_10 = df.tail(10)
        crossings = np.sum(np.diff(np.sign(last_10['Close'] - last_10['EMA21'])) != 0)
        day_high, day_low = df.iloc[-1]['High'], df.iloc[-1]['Low']
        day_range_pct = ((day_high - day_low) / (day_low + 1e-10)) * 100
        is_sideways_trap = (crossings >= 3) or (day_range_pct < 0.6) or (current_adx < 20)
        
        df['ATR'] = df['High'].rolling(14).mean() - df['Low'].rolling(14).mean()
        is_squeeze = (df['UpperBB'].iloc[-1] < (df['SMA20'].iloc[-1] + (1.5 * df['ATR'].fillna(0).iloc[-1])))
        bb_status = "💥 SQUEEZE" if is_squeeze else "Normal"
        
        high_52w = price
        try: high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        except: pass
        is_breakout_zone = price > high_52w * 0.98
        bo_status = "✅ B/O" if is_breakout_zone else "NO B/O"
        
        p15_high = df_15['High'].iloc[-2]
        p15_low = df_15['Low'].iloc[-2]
        is_15m_bullish = price > p15_high
        is_15m_bearish = price < p15_low
        
        volume_spike_heavy = volume > (df['VolSMA10'].iloc[-1] * 1.5)
        is_delta_confirmed = "increasing" in str(live_delta_trend).lower()
        is_institution_backed = volume_spike_heavy and is_delta_confirmed
        
        c_close = df['Close'].iloc[-1]
        p_close, p_high, p_low, p_ema21, p_vwap = df['Close'].iloc[-2], df['High'].iloc[-2], df['Low'].iloc[-2], df['EMA21'].iloc[-2], df['VWAP'].iloc[-2]
        
        base_breakout = (p_close > p_ema21) and (p_close > p_vwap) and (c_close > p_high)
        base_breakdown = (p_close < p_ema21) and (p_close < p_vwap) and (c_close < p_low)
        chartink_uptrend = (current_rsi > 60) and (current_adx > 25)
        chartink_downtrend = (current_rsi < 40) and (current_adx > 25)
        
        is_fundamentally_strong = check_fundamentals(ticker)
        expiry_alert = get_expiry_risk_status()
        
        if is_breakout_zone and is_squeeze and not is_institution_backed:
            master_signal = "👀 READY TO BLAST: NEED VOL DELTA"
            action, status, entry, score = "⏳ MONITOR", "🛡️ HURDLE 3 PENDING", "⏳ WATCH VOL", 75
        elif not is_breakout_zone and day_gain_pct >= 3.0 and is_institution_backed:
            master_signal = f"🚀 INTRADAY MOMENTUM BLAST (+{round(day_gain_pct,1)}%)"
            action, status, entry, score = "🚀 BUY NOW", "🔥 VOL MOMENTUM", "✅ BUY NOW", 90
        elif is_sideways_trap and day_gain_pct < 3.0:
            master_signal = "⏳ SIDEWAYS / ACCUMULATION"
            action, status, entry, score = "⏳ WAIT", "🛡️ RANGE-BOUND", "⏳ HOLD", 50
        elif base_breakout and chartink_uptrend and is_15m_bullish and is_institution_backed and is_fundamentally_strong:
            master_signal = "🔥 ALPHA BLAST (100%)"
            action, status, entry, score = "🚀 BUY NOW", "🎯 SUPER TREND", "✅ BUY NOW", 100
        elif base_breakdown and chartink_downtrend and is_15m_bearish and is_institution_backed and sharma_score < 3:
            master_signal = "📉 ALPHA CRASH (PUT)"
            action, status, entry, score = "🚀 BUY PUT / SHORT", "🚨 SEVERE WEAKNESS", "🔻 SHORT NOW", 95
        elif (base_breakout or base_breakdown) and not is_institution_backed:
            master_signal = "⏳ FAKEOUT RISK: LOW VOLUME DELTA"
            action, status, entry, score = "⏳ WAIT", "🛡️ VOLUME BLOCK", "⏳ HOLD", 35
        else:
            master_signal = "➡️ Neutral"
            action, status, entry, score = "📉 AVOID", "📉 WEAK", "🔴 AVOID", 0
            
        if "🚀 BUY" in action and expiry_alert != "Normal":
            master_signal = f"⚠️ {expiry_alert}"
            status = "🛡️ THETA RISK"
            
        if sharma_score < 3 and "🚀 BUY NOW" in action and "INTRADAY" not in master_signal:
            master_signal, action, status, entry, score = "⚠️ RISK: NIFTY WEAK", "⏳ WAIT", "🛡️ BEARISH MARKET", "⏳ HOLD", 60

        if "BUY NOW" in action:
            cash_trigger = round(price * 0.995, 1)
            sl_level, tgt_level = f"SL: {round(price * 0.985, 1)}", f"T1: {round(price * 1.02, 1)}"
            auto_trigger, auto_limit_tsl = str(cash_trigger), f"Lmt: {round(cash_trigger-2,1)} | TSL: 10"
        elif "BUY PUT" in action:
            cash_trigger = round(price * 0.997, 1)
            sl_level, tgt_level = f"SL: {round(price * 1.015, 1)}", f"T1: {round(price * 0.98, 1)}"
            auto_trigger, auto_limit_tsl = str(cash_trigger), f"Lmt: {round(cash_trigger-1.5,1)} | TSL: 10"
        else:
            sl_level, tgt_level, auto_trigger, auto_limit_tsl = "⏳" if "MONITOR" in action or "WAIT" in action else "❌", "⏳" if "MONITOR" in action or "WAIT" in action else "❌", "⏳" if "MONITOR" in action or "WAIT" in action else "❌", "⏳" if "MONITOR" in action or "WAIT" in action else "❌"
            
        return [symbol, round(price, 2), action, status, score, entry, sl_level, tgt_level, bo_status, bb_status, master_signal, auto_trigger, auto_limit_tsl]
    except Exception as e:
        logging.error(f"Error {symbol}: {e}")
        return None

def get_nifty_options_data(sharma_score, live_delta_trend):
    rows = []
    try:
        nifty_ticker = yf.Ticker(NIFTY_SYMBOL)
        nifty_df = nifty_ticker.history(period="2d", interval="5m")
        if nifty_df.empty: return rows
        nifty_spot = float(nifty_df['Close'].iloc[-1])
        
        last_10_nifty = nifty_df.tail(10)
        nifty_crossings = np.sum(np.diff(np.sign(last_10_nifty['Close'] - last_10_nifty['Close'].rolling(21).mean())) != 0)
        
        sharma_action_map = "🚀 BUY CALL" if sharma_score >= 5 else ("🚀 BUY PUT" if sharma_score < 3 else "⏳ WAIT / SIDEWAYS")
        sharma_signal_map = "🔥 SHARMAJI BULLISH" if sharma_score >= 5 else ("📉 SHARMAJI BEARISH" if sharma_score < 3 else "🛡️ RANGE BOUND TRAP")

        if nifty_crossings >= 4:
            sharma_action_map, sharma_signal_map, sharma_score = "⏳ WAIT / SIDEWAYS", "🛡️ RANGE BOUND TRAP", 3
        elif "increasing" not in str(live_delta_trend).lower():
            sharma_action_map, sharma_signal_map, sharma_score = "⏳ WAIT / DELTA LOW", "🛡️ DELTA STAGNANT", 3

        rows.append(["NIFTY_INDEX", round(nifty_spot, 2), sharma_action_map, sharma_signal_map, f"Score: {sharma_score}/6", "LIVE ALIGNED", "-", "-", "-", "Normal", "OPTS ENGINE", "-", "-"])
        atm_strike = int(round(nifty_spot / 50.0) * 50)
        
        if "BUY CALL" in sharma_action_map:
            rows.append([f"NIFTY {atm_strike} CE (ATM)", "Premium SCAN", "🚀 BUY CALL", "🔥 BULLISH TREND", 95, "✅ BUY NOW", "-", "-", "NO B/O", "Normal", "🔥 SHARMAJI ENGINE", "LTP - 25", "Lmt: Trig-3 | TSL: 10"])
            rows.append([f"NIFTY {atm_strike} PE (ATM)", "Premium SCAN", "📉 AVOID PUT", "🛡️ CRASHING OI", 10, "🔴 AVOID", "-", "-", "NO B/O", "Normal", "➡️ Neutral", "⏳", "⏳"])
        elif "BUY PUT" in sharma_action_map:
            rows.append([f"NIFTY {atm_strike} CE (ATM)", "Premium SCAN", "📉 AVOID CALL", "❌ DATA WEAK", 10, "🔴 AVOID", "-", "-", "NO B/O", "Normal", "➡️ Neutral", "⏳", "⏳"])
            rows.append([f"NIFTY {atm_strike} PE (ATM)", "Premium SCAN", "🚀 BUY PUT", "📉 BEARISH TREND", 95, "✅ BUY NOW", "-", "-", "NO B/O", "Normal", "🔥 SHARMAJI ENGINE", "LTP - 25", "Lmt: Trig-3 | TSL: 10"])
        else:
            rows.append([f"NIFTY {atm_strike} CE (ATM)", "Premium SCAN", "⏳ HOLD CALL", "🛡️ NO TREND", 45, "⏳ HOLD", "-", "-", "NO B/O", "Normal", "➡️ Neutral", "⏳", "⏳"])
            rows.append([f"NIFTY {atm_strike} PE (ATM)", "Premium SCAN", "⏳ HOLD PUT", "🛡️ NO TREND", 45, "⏳ HOLD", "-", "-", "NO B/O", "Normal", "➡️ Neutral", "⏳", "⏳"])
    except: pass
    return rows

def update_google_sheet():
    logging.info("🚀 Deploying V7 HYPER-HUNTER Engine Sync...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        
        try:
            input_sheet = sh.worksheet("Inputs")
            live_pcr = float(input_sheet.acell('B1').value)                 
            live_maxpain = str(input_sheet.acell('B2').value).strip()       
            live_call_trend = str(input_sheet.acell('B3').value).strip()    
            live_put_trend = str(input_sheet.acell('B4').value).strip()     
            live_iv_trend = str(input_sheet.acell('B5').value).strip()      
            live_delta_trend = str(input_sheet.acell('B6').value).strip()   
        except:
            live_pcr, live_maxpain, live_call_trend, live_put_trend, live_iv_trend, live_delta_trend = 1.0, "above", "short", "short", "no", "decreasing"

        dash_sheet = sh.get_worksheet(0)
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        
        s_score = calculate_sharmaji_score(live_pcr, live_maxpain, live_call_trend, live_put_trend, live_iv_trend, live_delta_trend)
        nifty_rows = get_nifty_options_data(s_score, live_delta_trend)
        for r in nifty_rows: r.append(timestamp)
            
        stock_rows = []
        for sym in UNIVERSE:
            data = scan_stock(sym, s_score, live_delta_trend)
            if data:
                data.append(timestamp)
                stock_rows.append(data)
            time.sleep(0.01)
        
        ready_blasts = [row for row in stock_rows if "👀 READY" in row[10]]
        alpha_blasts = [row for row in stock_rows if "🔥 ALPHA BLAST" in row[10]]
        intraday_blasts = [row for row in stock_rows if "🚀 INTRADAY" in row[10]] 
        alpha_crashes = [row for row in stock_rows if "📉 ALPHA CRASH" in row[10]]  
        volume_blocks = [row for row in stock_rows if "🛡️ VOLUME BLOCK" in row[3]]
        sideways_acc = [row for row in stock_rows if "⏳ SIDEWAYS" in row[10]]
        neutrals = [row for row in stock_rows if "➡️ Neutral" in row[10]]
        
        final_data = nifty_rows + ready_blasts + alpha_blasts + intraday_blasts + volume_blocks + sideways_acc + neutrals
        
        dash_sheet.clear()
        dash_sheet.update('A1', [[f"📊 AI BRO SCANNER - {date_stamp} (V7 PRO MAX - HYPER-HUNTER EDITION)", "", "", "", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Entry Decision', 'Stop Loss', 'Target 1', 'Breakout', 'BB Squeeze', 'Master Signal', 'Auto Trigger Price', 'Limit Price & TSL', 'Time']])
        
        if final_data: dash_sheet.update('A3', final_data)
        dash_sheet.freeze(rows=2)
        return True
    except Exception as e:
        logging.error(f"Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
