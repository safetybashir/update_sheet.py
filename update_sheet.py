# update_sheet.py – AI Bro Scanner (All Breakout Columns Visible)
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.oauth2.service_account import Credentials

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- Load Secrets ---
try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
    logging.info(f"✅ SHEET_ID: {SHEET_ID}")
except Exception as e:
    logging.error(f"❌ Failed to load credentials: {e}")
    sys.exit(1)

# --- UNIVERSE (150+ Stocks) ---
UNIVERSE = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR',
    'ICICIBANK', 'ITC', 'KOTAKBANK', 'SBIN', 'BHARTIARTL',
    'LT', 'AXISBANK', 'BAJFINANCE', 'HCLTECH', 'WIPRO',
    'SUNPHARMA', 'TITAN', 'MARUTI', 'ONGC', 'NTPC',
    'POWERGRID', 'ULTRACEMCO', 'ASIANPAINT', 'M&M', 'NESTLE',
    'JSWSTEEL', 'TATAMOTORS', 'TATASTEEL', 'TECHM', 'HDFCLIFE',
    'ADANIPORTS', 'ADANIENT', 'GRASIM', 'BRITANNIA', 'DIVISLAB',
    'DRREDDY', 'CIPLA', 'UPL', 'EICHERMOT', 'COALINDIA',
    'BPCL', 'HINDALCO', 'SHREECEM', 'HEROMOTOCO', 'BAJAJ-AUTO',
    'TATACONSUM', 'INDUSINDBK', 'PIDILITIND', 'BERGAPAINT', 'DABUR',
    'MCX', 'NATIONALUM', 'HYUNDAI', 'HAL', 'BSE', 'KALYANKJIL',
    'NESTLEIND', 'JUBLFOOD', 'RVNL', 'MAXHEALTH', 'POWERINDIA',
    'ASHOKLEY', 'HINDALCO', 'CIPLA', 'TORNTPHARM', 'ETERNAL',
    'MARUTI', 'TMPV', 'WAAREEENER', 'MOTHERSON', 'GVT&D',
    'CUMMINSIND', 'TATACONSUM', 'BEL', 'EICHERMOT', 'DLF',
    'ENRIN', 'ITC', 'BDL', 'SOLARINDS', 'BRITANNIA',
    'DMART', 'THERMAX', 'CGPOWER', 'LODHA', 'APOLLOHOSP',
    'NAUKRI', 'TVSMOTOR', 'TMCV', 'TITAN', 'HEROMOTOCO',
    'ABB', 'BPCL', 'ALKEM', 'SIEMENS', 'PERSISTENT',
    'DRREDDY', 'OFSS', 'SWIGGY', 'LUPIN', 'JSWENERGY',
    'PIDILITIND', 'INDUSTOWER', 'BOSCHLTD', 'BHARATFORG', 'INDIGO',
    'MARICO', 'TECHM', 'DABUR', 'DIXON', 'SRF',
    'MANKIND', 'LTM', 'JINDALSTEL', 'GRASIM', 'HAVELLS',
    'BAJAJ-AUTO', 'NYKAA', 'COFORGE', 'TRENT', 'HINDPETRO',
    'ASTRAL', 'POLYCAB', 'MAZDOCK', 'PREMIERENE', 'APARINDS',
    'GAIL', 'UPL', 'DIVISLAB', 'JSWSTEEL', 'GODREJCP',
    'GODREJPROP', 'VOLTAS', 'APLAPOLLO', 'AUROPHARMA', 'RECLTD',
    'TATAPOWER', 'PIIND', 'GLENMARK', 'MPHASIS', 'LTF',
    'FORTIS', 'BIOCON', 'OBEROIRLTY', 'COLPAL', 'LAURUSLABS',
    'COCHINSHIP', 'PETRONET', 'TIINDIA', 'JSL', 'PHOENIXLTD',
    'TATACOMM', 'ESCORTS', 'SHREECEM', 'TORNTPOWER', 'LENSKART',
    'EXIDEIND', 'COROMANDEL', 'KEI', 'AMBUJACEM', 'PRESTIGE',
    'SUPREMEIND', 'IPCALAB', 'BALKRISIND', 'CONCOR', 'TATAELXSI',
    'FLUOROCHEM', 'KPITTECH', 'UNOMINDA', 'LINDEINDIA', 'AIAENG',
    'IRCTC', 'AJANTPHARM', 'GLAXO', 'JKCEMENT', 'GODREJIND',
    'APOLLOTYRE', 'LTTS', 'TATAINVEST', 'BERGAPAINT', 'KPRMILL',
    'ABBOTINDIA', 'ACC'
]

# --- NIFTY 50 Index ---
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
    rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70
    return rsi

def calc_bb_squeeze(df, period=20):
    middle = df['Close'].rolling(period).mean()
    std = df['Close'].rolling(period).std()
    upper = middle + (std * 2)
    lower = middle - (std * 2)
    bandwidth = (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1]
    return bandwidth

def detect_momentum_burst(df):
    if len(df) < 5:
        return False
    recent = df['Close'].iloc[-5:]
    price_change = ((recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0]) * 100
    vol_change = ((df['Volume'].iloc[-1] - df['Volume'].iloc[-5:].mean()) / df['Volume'].iloc[-5:].mean()) * 100
    return price_change > 2 and vol_change > 50

def detect_consolidation_breakout(df, lookback=10):
    if len(df) < lookback:
        return False
    high = df['High'].iloc[-lookback:].max()
    low = df['Low'].iloc[-lookback:].min()
    range_pct = ((high - low) / low) * 100
    recent_close = df['Close'].iloc[-1]
    return range_pct < 8 and recent_close > high

def detect_swing_high_low(df):
    if len(df) < 5:
        return "➡️ Neutral"
    high = df['High'].iloc[-5:].max()
    low = df['Low'].iloc[-5:].min()
    current = df['Close'].iloc[-1]
    if current == high:
        return "📈 Higher High"
    elif current == low:
        return "📉 Lower Low"
    return "➡️ Neutral"

# --- Scan Stock ---
def scan_stock(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="1mo")
        if df.empty:
            return None
        
        price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else price
        volume = df['Volume'].iloc[-1]
        traded_value = price * volume
        
        # Indicators
        ema21 = calc_ema21(df)
        vwap = calc_vwap(df)
        rsi = calc_rsi(df)
        bb_squeeze = calc_bb_squeeze(df)
        momentum_burst = detect_momentum_burst(df)
        consolidation = detect_consolidation_breakout(df)
        swing = detect_swing_high_low(df)
        
        # 52W High/Low
        high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
        low_52w = ticker.info.get('fiftyTwoWeekLow', price)
        is_breakout = price > high_52w * 0.98
        
        # --- Score ---
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
        
        # --- Action ---
        if score >= 75:
            action = "🚀 BUY NOW"
            status = "🎯 STRONG BUY"
        elif score >= 60:
            action = "📈 WATCH"
            status = "📈 BUY ZONE"
        elif score >= 40:
            action = "⏳ HOLD"
            status = "🛡️ RANGE-BOUND"
        else:
            action = "📉 AVOID"
            status = "📉 WEAK"
        
        # Entry Decision
        if score >= 75 and price > ema21 and price > vwap and rsi > 60:
            entry = "✅ BUY NOW"
        elif score >= 60 and price > ema21:
            entry = "🟡 WATCH"
        elif score >= 40:
            entry = "⏳ HOLD"
        else:
            entry = "🔴 AVOID"
        
        # Week Change
        week_change = ((price - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100 if len(df) >= 5 else 0
        
        return {
            'symbol': symbol + ".NS",
            'ltp': round(price, 2),
            'action': action,
            'status': status,
            'score': score,
            'volume': volume,
            'traded_value': traded_value,
            'week_change': round(week_change, 2),
            'rsi': round(rsi, 2),
            'sma50': round(df['Close'].rolling(50).mean().iloc[-1], 2) if len(df) >= 50 else price,
            'sma200': round(df['Close'].rolling(200).mean().iloc[-1], 2) if len(df) >= 200 else price,
            'prev_close': round(prev_close, 2),
            'entry': entry,
            'ema21': round(ema21, 2),
            'vwap': round(vwap, 2),
            'bb_squeeze': round(bb_squeeze, 4),
            'momentum_burst': "✅" if momentum_burst else "❌",
            'consolidation': "✅" if consolidation else "❌",
            'breakout': "✅" if is_breakout else "❌",
            'swing': swing,
            'high_52w': round(high_52w, 2),
            'low_52w': round(low_52w, 2)
        }
    except Exception as e:
        logging.error(f"Error scanning {symbol}: {e}")
        return None

# --- NIFTY Index Scan ---
def scan_nifty():
    try:
        ticker = yf.Ticker(NIFTY_SYMBOL)
        df = ticker.history(period="1mo")
        if df.empty:
            return None
        price = df['Close'].iloc[-1]
        ema21 = calc_ema21(df)
        vwap = calc_vwap(df)
        rsi = calc_rsi(df)
        week_change = ((price - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100 if len(df) >= 5 else 0
        return {
            'symbol': "NIFTY_INDEX",
            'ltp': round(price, 2),
            'action': "NIFTY",
            'status': f"{round(week_change, 2)}%",
            'score': "-",
            'volume': "-",
            'traded_value': "-",
            'week_change': round(week_change, 2),
            'rsi': round(rsi, 2),
            'sma50': "-",
            'sma200': "-",
            'prev_close': round(df['Close'].iloc[-2], 2) if len(df) > 1 else price,
            'entry': "-",
            'ema21': round(ema21, 2),
            'vwap': round(vwap, 2),
            'bb_squeeze': "-",
            'momentum_burst': "-",
            'consolidation': "-",
            'breakout': "-",
            'swing': "-",
            'high_52w': "-",
            'low_52w': "-"
        }
    except Exception as e:
        logging.error(f"Error scanning NIFTY: {e}")
        return None

# --- Main Update ---
def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – All Breakout Columns Visible")
    try:
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Connected to sheet: {sh.title}")
        
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        final_data = []
        
        # --- NIFTY Index ---
        nifty = scan_nifty()
        if nifty:
            final_data.append([
                nifty['symbol'], nifty['ltp'], nifty['action'], nifty['status'],
                nifty['score'], nifty['volume'], nifty['traded_value'],
                nifty['week_change'], nifty['rsi'], nifty['sma50'],
                nifty['sma200'], nifty['prev_close'], nifty['entry'],
                nifty['ema21'], nifty['vwap'], nifty['bb_squeeze'],
                nifty['momentum_burst'], nifty['consolidation'], nifty['breakout'],
                nifty['swing'], nifty['high_52w'], nifty['low_52w'],
                timestamp
            ])
        
        # --- Stocks ---
        for sym in UNIVERSE:
            data = scan_stock(sym)
            if data:
                final_data.append([
                    data['symbol'], data['ltp'], data['action'], data['status'],
                    data['score'], data['volume'], f"₹{data['traded_value']/1e7:.2f}Cr",
                    data['week_change'], data['rsi'], data['sma50'],
                    data['sma200'], data['prev_close'], data['entry'],
                    data['ema21'], data['vwap'], data['bb_squeeze'],
                    data['momentum_burst'], data['consolidation'], data['breakout'],
                    data['swing'], data['high_52w'], data['low_52w'],
                    timestamp
                ])
            time.sleep(0.1)
        
        logging.info(f"📊 final_data rows: {len(final_data)}")
        
        # --- Update Sheet ---
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SCANNER - {date_stamp} (All Breakout Columns)", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [
            ['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value',
             'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision',
             'EMA21', 'VWAP', 'BB Squeeze', 'Momentum Burst', 'Consolidation',
             'Breakout', 'Swing', '52W High', '52W Low', 'Time']
        ]
        dash_sheet.update(range_name='A2', values=header2)
        
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        else:
            test_row = [["TEST", 100, "HOLD", "TEST", 50, 1000, "1 Cr", "1%", 50, 100, 90, 95, "HOLD", 100, 95, 0.02, "✅", "✅", "✅", "📈 Higher High", 110, 90, timestamp]]
            dash_sheet.update(range_name='A3', values=test_row)
        
        dash_sheet.freeze(rows=2)
        logging.info("✅ Update completed!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
