# update_sheet.py – OI-VCP Integrated (V8 PRO MAX) – 250 Stocks
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

# --- 250 STOCKS UNIVERSE ---
UNIVERSE = [
    'NIFTY_50', 'TORNTPHARM.NS', 'ASHOKLEY.NS', 'KAYNES.NS', 'INOXWIND.NS',
    'GAIL.NS', 'KEI.NS', 'PREMIERENE.NS', 'CGPOWER.NS', 'M&M.NS',
    'BSE.NS', 'DIVISLAB.NS', 'MOTHERSON.NS', 'POWERINDIA.NS', 'GLENMARK.NS',
    'MAZDOCK.NS', 'DELHIVERY.NS', 'GVT&D.NS', 'TVSMOTOR.NS', 'POLYCAB.NS',
    'TIINDIA.NS', 'SIEMENS.NS', 'CUMMINSIND.NS', 'JSWENERGY.NS', 'ANGELONE.NS',
    'COCHINSHIP.NS', 'WAAREEENER.NS', 'LAURUSLABS.NS', 'MOTILALOFS.NS', 'BHARATFORG.NS',
    'TMPV.NS', 'SOLARINDS.NS', 'TATASTEEL.NS', 'LTF.NS', 'FORCEMOT.NS',
    'PRESTIGE.NS', 'BPCL.NS', 'HAL.NS', 'SUZLON.NS', 'GMRAIRPORT.NS',
    'TATAPOWER.NS', 'NBCC.NS', 'DMART.NS', 'HEROMOTOCO.NS', 'KPITTECH.NS',
    'RVNL.NS', 'RELIANCE.NS', 'PNB.NS', 'ZYDUSLIFE.NS', 'BHEL.NS',
    'NATIONALUM.NS', 'NHPC.NS', 'SRF.NS', 'JINDALSTEL.NS', 'BAJAJ-AUTO.NS',
    'BEL.NS', 'TITAN.NS', 'SONACOMS.NS', 'HINDZINC.NS', 'UNOMINDA.NS',
    'OBEROIRLTY.NS', 'BHARTIARTL.NS', 'OFSS.NS', 'BDL.NS', 'SUPREMEIND.NS',
    'OIL.NS', 'SHREECEM.NS', 'NTPC.NS', 'TATAELXSI.NS', 'HINDALCO.NS',
    'PETRONET.NS', 'CIPLA.NS', 'MARUTI.NS', 'PAYTM.NS', 'PERSISTENT.NS',
    'AMBER.NS', 'DLF.NS', 'DALBHARAT.NS', 'ULTRACEMCO.NS', 'ONGC.NS',
    'PHOENIXLTD.NS', 'HINDPETRO.NS', 'CAMS.NS', 'AUROPHARMA.NS', 'BIOCON.NS',
    'TRENT.NS', 'DRREDDY.NS', 'JSWSTEEL.NS', 'NMDC.NS', 'IOC.NS',
    'UPL.NS', 'NYKAA.NS', 'LT.NS', 'CROMPTON.NS', 'INDUSTOWER.NS',
    'HAVELLS.NS', 'CONCOR.NS', 'SAIL.NS', 'JUBLFOOD.NS', 'GRASIM.NS',
    'PFC.NS', 'ASIANPAINT.NS', 'LUPIN.NS', 'CDSL.NS', 'IREDA.NS',
    'HINDUNILVR.NS', 'GODREJPROP.NS', 'KFINTECH.NS', 'AMBUJACEM.NS', 'APOLLOHOSP.NS',
    'HCLTECH.NS', 'POWERGRID.NS', 'RECLTD.NS', 'GODREJCP.NS', 'FORTIS.NS',
    'PGEL.NS', 'ABB.NS', 'COALINDIA.NS', 'SUNPHARMA.NS', 'MPHASIS.NS',
    'PIIND.NS', 'COLPAL.NS', 'BLUESTARCO.NS', 'VMM.NS', 'VOLTAS.NS',
    'TECHM.NS', 'EICHERMOT.NS', 'INDIGO.NS', 'DABUR.NS', 'NESTLEIND.NS',
    'TATACONSUM.NS', 'BOSCHLTD.NS', 'VEDL.NS', 'PIDILITIND.NS', 'NAUKRI.NS',
    'WIPRO.NS', 'ALKEM.NS', 'ITC.NS', 'COFORGE.NS', 'ASTRAL.NS',
    'LTM.NS', 'MARICO.NS', 'PAGEIND.NS', 'MAXHEALTH.NS', 'BRITANNIA.NS',
    'INFY.NS', 'ETERNAL.NS', 'TCS.NS', 'KALYANKJIL.NS', 'LODHA.NS',
    'SWIGGY.NS', 'MANKIND.NS', 'DIXON.NS', 'APLAPOLLO.NS'
]

NIFTY_SYMBOL = "^NSEI"

# --- NSE Option Chain Functions (OI-VCP) ---
def get_nse_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/"
    })
    session.get("https://www.nseindia.com")
    return session

def get_nse_option_chain(symbol="NIFTY"):
    try:
        session = get_nse_session()
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        response = session.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def find_call_wall(data, spot_price):
    try:
        max_call_oi = 0
        call_wall = 0
        for record in data['records']['data']:
            ce_data = record.get('CE', {})
            if ce_data:
                oi = ce_data.get('openInterest', 0)
                strike = record.get('strikePrice', 0)
                if oi > max_call_oi and strike > spot_price * 0.95:
                    max_call_oi = oi
                    call_wall = strike
        return call_wall, max_call_oi
    except:
        return 0, 0

def find_put_wall(data, spot_price):
    try:
        max_put_oi = 0
        put_wall = 0
        for record in data['records']['data']:
            pe_data = record.get('PE', {})
            if pe_data:
                oi = pe_data.get('openInterest', 0)
                strike = record.get('strikePrice', 0)
                if oi > max_put_oi and strike < spot_price * 1.05:
                    max_put_oi = oi
                    put_wall = strike
        return put_wall, max_put_oi
    except:
        return 0, 0

def calculate_oi_vcp_score(data, spot_price):
    call_wall, call_oi = find_call_wall(data, spot_price)
    put_wall, put_oi = find_put_wall(data, spot_price)
    score = 0
    oi_vcp_status = "Neutral"
    if call_wall > 0 and spot_price < call_wall * 0.98:
        score += 1
        oi_vcp_status = "Resistance Ahead (Call Wall)"
    if put_wall > 0 and spot_price > put_wall * 1.02:
        score += 1
        oi_vcp_status = "Support Below (Put Wall)"
    if call_oi > 0 and put_oi > 0:
        pcr = put_oi / call_oi
        if 0.8 < pcr < 1.2:
            score += 1
            oi_vcp_status = "Neutral PCR"
    return score, call_wall, put_wall, oi_vcp_status

# --- ADX Calculation ---
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

# --- VCP Pattern Detection ---
def detect_vcp_pattern(df):
    try:
        if len(df) < 30: return False, "Insufficient data"
        highs = []
        lows = []
        for i in range(10, len(df)-10):
            if df['High'].iloc[i] > df['High'].iloc[i-5:i].max() and df['High'].iloc[i] > df['High'].iloc[i:i+5].max():
                highs.append((i, df['High'].iloc[i]))
            if df['Low'].iloc[i] < df['Low'].iloc[i-5:i].min() and df['Low'].iloc[i] < df['Low'].iloc[i:i+5].min():
                lows.append((i, df['Low'].iloc[i]))
        if len(highs) >= 3 and len(lows) >= 3:
            amp1 = highs[-1][1] - lows[-1][1]
            amp2 = highs[-2][1] - lows[-2][1]
            amp3 = highs[-3][1] - lows[-3][1]
            if amp1 < amp2 < amp3:
                return True, "VCP Pattern Detected"
        return False, "No VCP"
    except:
        return False, "Error"

# --- Sharma Score ---
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

def get_expiry_risk_status():
    try:
        now_ist = dt.now(pytz.timezone('Asia/Kolkata'))
        if now_ist.day >= 22:
            return "⚠️ EXPIRE RISK: NEXT SERIES"
        return "Normal"
    except: return "Normal"

# --- Scan Stock (OI-VCP Integrated) ---
def scan_stock(symbol, oi_vcp_score, call_wall, put_wall):
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
        vcp_detected, vcp_status = detect_vcp_pattern(df)
        
        high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        is_breakout_zone = price > high_52w * 0.98
        bo_status = "✅ B/O" if is_breakout_zone else "NO B/O"
        volume_spike = volume > (df['VolSMA10'].iloc[-1] * 1.5)
        p_close, p_high, p_ema21, p_vwap = df['Close'].iloc[-2], df['High'].iloc[-2], df['EMA21'].iloc[-2], df['VWAP'].iloc[-2]
        c_close = df['Close'].iloc[-1]
        base_breakout = (p_close > p_ema21) and (p_close > p_vwap) and (c_close > p_high)
        
        oi_vcp_confirmed = oi_vcp_score >= 2 and base_breakout and volume_spike
        
        if oi_vcp_confirmed and is_breakout_zone and vcp_detected:
            master_signal = f"🔥 OI-VCP CONFIRMED (CW:{call_wall}, PW:{put_wall})"
            action, status, entry, score = "🚀 BUY NOW", "🎯 OI-VCP BLAST", "✅ BUY NOW", 100
        elif is_breakout_zone and vcp_detected and volume_spike:
            master_signal = "🔥 VCP BREAKOUT CONFIRMED"
            action, status, entry, score = "🚀 BUY NOW", "🎯 VCP BLAST", "✅ BUY NOW", 95
        elif is_breakout_zone and volume_spike:
            master_signal = "🚀 STRONG BREAKOUT (VOLUME SPIKE)"
            action, status, entry, score = "🚀 BUY NOW", "📈 VOL MOMENTUM", "✅ BUY NOW", 85
        elif is_breakout_zone:
            master_signal = "🟡 NEAR BREAKOUT - WATCH"
            action, status, entry, score = "⏳ WATCH", "👀 BREAKOUT ZONE", "⏳ HOLD", 60
        elif base_breakout and current_rsi > 60 and current_adx > 25:
            master_signal = "📈 UPTREND CONTINUATION"
            action, status, entry, score = "📈 WATCH", "📈 BUY ZONE", "🟡 WATCH", 70
        else:
            master_signal = "➡️ Neutral"
            action, status, entry, score = "📉 AVOID", "📉 WEAK", "🔴 AVOID", 0
        
        if "BUY NOW" in action:
            sl_level, tgt_level = f"SL: {round(price * 0.985, 1)}", f"T1: {round(price * 1.02, 1)}"
        else:
            sl_level, tgt_level = "⏳", "⏳"
        
        return [symbol, round(price, 2), action, status, score, entry, sl_level, tgt_level, bo_status, "Normal", master_signal, "⏳", "⏳"]
    except Exception as e:
        logging.error(f"Error {symbol}: {e}")
        return None

# --- NIFTY Options ---
def get_nifty_options_data():
    rows = []
    try:
        nifty_ticker = yf.Ticker(NIFTY_SYMBOL)
        nifty_df = nifty_ticker.history(period="2d", interval="5m")
        if nifty_df.empty: return rows
        nifty_spot = float(nifty_df['Close'].iloc[-1])
        option_data = get_nse_option_chain("NIFTY")
        oi_vcp_score = 0
        call_wall = 0
        put_wall = 0
        oi_vcp_status = "Neutral"
        if option_data:
            oi_vcp_score, call_wall, put_wall, oi_vcp_status = calculate_oi_vcp_score(option_data, nifty_spot)
            rows.append(["NIFTY_INDEX", round(nifty_spot, 2), "NIFTY", "OI-VCP", oi_vcp_score, oi_vcp_status, f"CW:{call_wall}", f"PW:{put_wall}", "-", "Normal", "OI-VCP SCAN", "-", "-"])
        else:
            rows.append(["NIFTY_INDEX", round(nifty_spot, 2), "NIFTY", "INDEX", "-", "-", "-", "-", "-", "Normal", "INDEX", "-", "-"])
    except:
        pass
    return rows

# --- Main Update ---
def update_google_sheet():
    logging.info("🚀 Deploying OI-VCP Integrated Engine...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        
        nifty_rows = get_nifty_options_data()
        for r in nifty_rows: r.append(timestamp)
        
        option_data = get_nse_option_chain("NIFTY")
        oi_vcp_score = 0
        call_wall = 0
        put_wall = 0
        if option_data:
            nifty_ticker = yf.Ticker(NIFTY_SYMBOL)
            nifty_df = nifty_ticker.history(period="2d", interval="5m")
            if not nifty_df.empty:
                nifty_spot = float(nifty_df['Close'].iloc[-1])
                oi_vcp_score, call_wall, put_wall, _ = calculate_oi_vcp_score(option_data, nifty_spot)
        
        stock_rows = []
        for sym in UNIVERSE:
            data = scan_stock(sym, oi_vcp_score, call_wall, put_wall)
            if data:
                data.append(timestamp)
                stock_rows.append(data)
            time.sleep(0.01)
        
        breakout_rows = [row for row in stock_rows if "BUY NOW" in row[2] or "BUY" in row[2]]
        other_rows = [row for row in stock_rows if "BUY NOW" not in row[2] and "BUY" not in row[2]]
        final_data = nifty_rows + breakout_rows + other_rows
        
        dash_sheet.clear()
        dash_sheet.update('A1', [[f"📊 AI BRO OI-VCP SCANNER - {date_stamp} (250 STOCKS)", "", "", "", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Entry Decision', 'Stop Loss', 'Target 1', 'Breakout', 'BB Squeeze', 'Master Signal', 'Auto Trigger Price', 'Limit Price & TSL', 'Time']])
        if final_data:
            dash_sheet.update('A3', final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        dash_sheet.freeze(rows=2)
        return True
    except Exception as e:
        logging.error(f"Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
