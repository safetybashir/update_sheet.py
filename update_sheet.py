# update_sheet.py – AI Bro Scanner (Fixed with Chunk-Based API Upload)
import os
import json
import gspread
import yfinance as yf
import pytz
import pandas as pd
import numpy as np
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

# --- UNIVERSE (150+ Stocks) ---
UNIVERSE = [
    'RELIANCE', 'TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM',
    'HINDUNILVR', 'ITC', 'BHARTIARTL', 'SUNPHARMA', 'DRREDDY',
    'CIPLA', 'TORNTPHARM', 'DIVISLAB', 'LUPIN', 'ALKEM', 'BIOCON',
    'GLENMARK', 'APOLLOHOSP', 'FORTIS', 'MAXHEALTH', 'TATASTEEL',
    'JSWSTEEL', 'HINDALCO', 'NATIONALUM', 'JINDALSTEL', 'COALINDIA',
    'MARUTI', 'TATAMOTORS', 'M&M', 'EICHERMOT', 'HEROMOTOCO',
    'BAJAJ-AUTO', 'ASHOKLEY', 'TVSMOTOR', 'MOTHERSON', 'TITAN',
    'HAVELLS', 'VOLTAS', 'DIXON', 'WHIRLPOOL', 'NTPC', 'POWERGRID',
    'TATAPOWER', 'JSWENERGY', 'TORNTPOWER', 'ULTRACEMCO', 'SHREECEM',
    'AMBUJACEM', 'ACC', 'DLF', 'GODREJPROP', 'OBEROIRLTY', 'PRESTIGE',
    'PHOENIXLTD', 'INDIGO', 'HAL', 'BEL', 'MAZDOCK', 'COCHINSHIP',
    'BDL', 'PIDILITIND', 'SRF', 'UPL', 'ASTRAL', 'APLAPOLLO',
    'SUPREMEIND', 'TATACONSUM', 'TATAELXSI', 'TATAINVEST', 'ABB',
    'SIEMENS', 'BOSCHLTD', 'THERMAX', 'CGPOWER', 'KEI', 'LODHA',
    'ESCORTS', 'EXIDEIND', 'LENSKART', 'PIIND', 'UNOMINDA',
    'LINDEINDIA', 'AIAENG', 'IRCTC', 'AJANTPHARM', 'GLAXO',
    'JKCEMENT', 'GODREJIND', 'APOLLOTYRE', 'BERGAPAINT', 'KPRMILL',
    'ABBOTINDIA', 'ETERNAL', 'WAAREEENER', 'GVT&D', 'CUMMINSIND',
    'SOLARINDS', 'KALYANKJIL', 'NYKAA', 'MANKIND', 'LT', 'JUBLFOOD',
    'POWERINDIA', 'RVNL', 'MCX', 'BSE', 'SWIGGY', 'DMART', 'NAUKRI',
    'ONGC', 'BPCL', 'HINDPETRO', 'PETRONET'
]

NIFTY_SYMBOL = "^NSEI"

# --- Indicator Functions ---
def calc_ema21(df):
    return df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]

def calc_vwap(df):
    return (df['Close'] * df['Volume']).sum() / df['Volume'].sum()

def calc_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70

def calc_bb_squeeze(df, period=20):
    middle = df['Close'].rolling(period).mean()
    std = df['Close'].rolling(period).std()
    upper = middle + (std * 2)
    lower = middle - (std * 2)
    return (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1]

def detect_momentum_burst(df):
    if len(df) < 5: return False
    recent = df['Close'].iloc[-5:]
    price_change = ((recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0]) * 100
    vol_change = ((df['Volume'].iloc[-1] - df['Volume'].iloc[-5:].mean()) / df['Volume'].iloc[-5:].mean()) * 100
    return price_change > 2 and vol_change > 50

def detect_consolidation_breakout(df, lookback=10):
    if len(df) < lookback: return False
    high = df['High'].iloc[-lookback:].max()
    low = df['Low'].iloc[-lookback:].min()
    range_pct = ((high - low) / low) * 100
    return range_pct < 8 and df['Close'].iloc[-1] > high

def detect_swing_high_low(df):
    if len(df) < 5: return "➡️ Neutral"
    high = df['High'].iloc[-5:].max()
    low = df['Low'].iloc[-5:].min()
    current = df['Close'].iloc[-1]
    if current == high: return "📈 Higher High"
    elif current == low: return "📉 Lower Low"
    return "➡️ Neutral"

# --- Scan Stock ---
def scan_stock(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="1mo")
        if df.empty: return None
        
        price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else price
        volume = df['Volume'].iloc[-1]
        traded_value = price * volume
        
        ema21 = calc_ema21(df)
        vwap = calc_vwap(df)
        rsi = calc_rsi(df)
        bb_squeeze = calc_bb_squeeze(df)
        momentum_burst = detect_momentum_burst(df)
        consolidation = detect_consolidation_breakout(df)
        swing = detect_swing_high_low(df)
        
        high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        low_52w = ticker.info.get('fiftyTwoWeekLow', price)
        is_breakout = price > high_52w * 0.98
        
        score = 0
        if price > ema21: score += 10
        if price > vwap: score += 10
        if rsi > 60: score += 15
        elif rsi > 50: score += 8
        if momentum_burst: score += 20
        if consolidation: score += 15
        if bb_squeeze < 0.03: score += 10
        if is_breakout: score += 10
        if traded_value > 100_00_00_000: score += 5
        score = min(100, max(0, score))
        
        if score >= 75: action, status = "🚀 BUY NOW", "🎯 STRONG BUY"
        elif score >= 60: action, status = "📈 WATCH", "📈 BUY ZONE"
        elif score >= 40: action, status = "⏳ HOLD", "🛡️ RANGE-BOUND"
        else: action, status = "📉 AVOID", "📉 WEAK"
        
        entry = "✅ BUY NOW" if score >= 75 and price > ema21 and price > vwap and rsi > 60 else ("🟡 WATCH" if score >= 60 else "⏳ HOLD")
        week_change = ((price - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100 if len(df) >= 5 else 0
        
        return {
            'symbol': symbol + ".NS", 'ltp': round(price, 2), 'action': action, 'status': status, 'score': score,
            'volume': volume, 'traded_value': traded_value, 'week_change': round(week_change, 2), 'rsi': round(rsi, 2),
            'sma50': round(df['Close'].rolling(50).mean().iloc[-1], 2) if len(df) >= 50 else price,
            'sma200': round(df['Close'].rolling(200).mean().iloc[-1], 2) if len(df) >= 200 else price,
            'prev_close': round(prev_close, 2), 'entry': entry, 'ema21': round(ema21, 2), 'vwap': round(vwap, 2),
            'bb_squeeze': round(bb_squeeze, 4), 'momentum_burst': "✅" if momentum_burst else "❌",
            'consolidation': "✅" if consolidation else "❌", 'breakout': "✅ B/O" if is_breakout else "NO B/O",
            'swing': swing, 'high_52w': round(high_52w, 2), 'low_52w': round(low_52w, 2)
        }
    except Exception as e:
        logging.error(f"Error scanning {symbol}: {e}")
        return None

def scan_nifty():
    try:
        ticker = yf.Ticker(NIFTY_SYMBOL)
        df = ticker.history(period="1mo")
        if df.empty: return None
        price = df['Close'].iloc[-1]
        week_change = ((price - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100 if len(df) >= 5 else 0
        return {
            'symbol': "NIFTY_INDEX", 'ltp': round(price, 2), 'action': "NIFTY", 'status': f"{round(week_change, 2)}%",
            'score': "-", 'volume': "-", 'traded_value': "-", 'week_change': round(week_change, 2), 'rsi': "-",
            'sma50': "-", 'sma200': "-", 'prev_close': round(df['Close'].iloc[-2], 2) if len(df) > 1 else price,
            'entry': "-", 'ema21': "-", 'vwap': "-", 'bb_squeeze': "-", 'momentum_burst': "-",
            'consolidation': "-", 'breakout': "-", 'swing': "-", 'high_52w': "-", 'low_52w': "-"
        }
    except Exception as e:
        logging.error(f"Error scanning NIFTY: {e}")
        return None

# --- Main Update ---
def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Starting Chunk-Based Process...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        final_data = []
        
        # Nifty data
        nifty = scan_nifty()
        if nifty:
            final_data.append([nifty['symbol'], nifty['ltp'], nifty['action'], nifty['status'], nifty['score'],
                              nifty['volume'], nifty['traded_value'], nifty['week_change'], nifty['rsi'],
                              nifty['sma50'], nifty['sma200'], nifty['prev_close'], nifty['entry'],
                              nifty['ema21'], nifty['vwap'], nifty['bb_squeeze'], nifty['momentum_burst'],
                              nifty['consolidation'], nifty['breakout'], nifty['swing'], nifty['high_52w'],
                              nifty['low_52w'], timestamp])
        
        # Universe Fetch Loop
        for sym in UNIVERSE:
            data = scan_stock(sym)
            if data:
                final_data.append([data['symbol'], data['ltp'], data['action'], data['status'], data['score'],
                                  data['volume'], f"₹{data['traded_value']/1e7:.2f}Cr", data['week_change'],
                                  data['rsi'], data['sma50'], data['sma200'], data['prev_close'], data['entry'],
                                  data['ema21'], data['vwap'], data['bb_squeeze'], data['momentum_burst'],
                                  data['consolidation'], data['breakout'], data['swing'], data['high_52w'],
                                  data['low_52w'], timestamp])
                logging.info(f"✔ Fetched Local Data: {sym}")
            time.sleep(0.05)
        
        logging.info(f"📊 Total Rows Generated: {len(final_data)}")
        
        if not final_data:
            logging.error("❌ No data fetched! Stopping.")
            return False

        # --- SAFE BULK UPLOAD WITH CHUNKS ---
        dash_sheet.clear()
        
        # 1. Update Headers First
        dash_sheet.update('A1', [[f"📊 AI BRO SCANNER - {date_stamp}", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]])
        dash_sheet.update('A2', [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value',
                                  'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision',
                                  'EMA21', 'VWAP', 'BB Squeeze', 'Momentum Burst', 'Consolidation',
                                  'Breakout', 'Swing', '52W High', '52W Low', 'Time']])
        
        # 2. Upload Data in Chunks of 30 rows
        chunk_size = 30
        start_row = 3
        
        for i in range(0, len(final_data), chunk_size):
            chunk = final_data[i:i + chunk_size]
            end_row = start_row + len(chunk) - 1
            range_string = f"A{start_row}:W{end_row}"
            
            logging.info(f"📤 Uploading chunk {i//chunk_size + 1}... Range: {range_string}")
            dash_sheet.update(range_string, chunk)
            
            start_row = end_row + 1
            time.sleep(1) # Small cool-down to prevent API block
        
        dash_sheet.freeze(rows=2)
        logging.info("🚀 [BOOM] ALL CHUNKS SUCCESSFUL. GOOGLE SHEET COMPLETELY UPDATED!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
