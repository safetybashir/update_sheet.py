# update_sheet.py – AI Bro Super Scanner 2.0
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
    SHEET_ID = os.environ.get('SHEET_ID', '1T0r-MG2oxImCyhJv0q98bdCEnjNschePHBhOtMmW9Bg')
except Exception as e:
    logging.error(f"❌ Failed to load credentials: {e}")
    sys.exit(1)

# --- UNIVERSE (150 Stocks) ---
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
    'MCX', 'NATIONALUM', 'HYUNDAI', 'M&M', 'HAL', 'BSE', 'KALYANKJIL',
    'NESTLEIND', 'JUBLFOOD', 'RVNL', 'MAXHEALTH', 'POWERINDIA',
    'ASHOKLEY', 'HINDALCO', 'CIPLA', 'TORNTPHARM', 'ETERNAL',
    'TMPV', 'WAAREEENER', 'MOTHERSON', 'GVT&D', 'CUMMINSIND',
    'BEL', 'EICHERMOT', 'DLF', 'ENRIN', 'BDL', 'SOLARINDS',
    'DMART', 'THERMAX', 'CGPOWER', 'LODHA', 'APOLLOHOSP',
    'NAUKRI', 'TVSMOTOR', 'TMCV', 'HEROMOTOCO', 'ABB', 'ALKEM',
    'SIEMENS', 'PERSISTENT', 'OFSS', 'SWIGGY', 'LUPIN', 'JSWENERGY',
    'INDUSTOWER', 'BOSCHLTD', 'BHARATFORG', 'INDIGO', 'MARICO',
    'DABUR', 'DIXON', 'SRF', 'MANKIND', 'LTM', 'JINDALSTEL',
    'HAVELLS', 'BAJAJ-AUTO', 'NYKAA', 'COFORGE', 'TRENT', 'HINDPETRO',
    'ASTRAL', 'POLYCAB', 'MAZDOCK', 'PREMIERENE', 'APARINDS',
    'GAIL', 'DIVISLAB', 'GODREJCP', 'GODREJPROP', 'VOLTAS',
    'APLAPOLLO', 'AUROPHARMA', 'RECLTD', 'TATAPOWER', 'PIIND',
    'GLENMARK', 'MPHASIS', 'LTF', 'FORTIS', 'BIOCON', 'OBEROIRLTY',
    'COLPAL', 'LAURUSLABS', 'COCHINSHIP', 'PETRONET', 'TIINDIA',
    'JSL', 'PHOENIXLTD', 'TATACOMM', 'ESCORTS', 'SHREECEM',
    'TORNTPOWER', 'LENSKART', 'EXIDEIND', 'COROMANDEL', 'KEI',
    'AMBUJACEM', 'PRESTIGE', 'SUPREMEIND', 'IPCALAB', 'BALKRISIND',
    'CONCOR', 'TATAELXSI', 'FLUOROCHEM', 'KPITTECH', 'UNOMINDA',
    'LINDEINDIA', 'AIAENG', 'IRCTC', 'AJANTPHARM', 'GLAXO',
    'JKCEMENT', 'GODREJIND', 'APOLLOTYRE', 'LTTS', 'TATAINVEST',
    'BERGAPAINT', 'KPRMILL', 'ABBOTINDIA', 'ACC'
]

# --- NIFTY 50 Index ---
NIFTY_SYMBOL = "^NSEI"

# --- Function: EMA 21 ---
def calculate_ema21(df):
    return df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]

# --- Function: VWAP (Volume Weighted Average Price) ---
def calculate_vwap(df):
    return (df['Close'] * df['Volume']).sum() / df['Volume'].sum()

# --- Function: RSI Power ---
def calculate_rsi_power(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70
    return rsi

# --- Function: Bollinger Band Squeeze ---
def calculate_bb_squeeze(df, period=20):
    bb_upper = df['Close'].rolling(period).mean() + (df['Close'].rolling(period).std() * 2)
    bb_lower = df['Close'].rolling(period).mean() - (df['Close'].rolling(period).std() * 2)
    bandwidth = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / df['Close'].rolling(period).mean().iloc[-1]
    return bandwidth

# --- Function: Momentum Burst ---
def detect_momentum_burst(df):
    if len(df) < 5:
        return False
    recent = df['Close'].iloc[-5:]
    price_change = ((recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0]) * 100
    vol_change = ((df['Volume'].iloc[-1] - df['Volume'].iloc[-5:].mean()) / df['Volume'].iloc[-5:].mean()) * 100
    return price_change > 2 and vol_change > 50

# --- Function: Consolidation Breakout ---
def detect_consolidation_breakout(df, lookback=10):
    if len(df) < lookback:
        return False
    high = df['High'].iloc[-lookback:].max()
    low = df['Low'].iloc[-lookback:].min()
    range_pct = ((high - low) / low) * 100
    recent_close = df['Close'].iloc[-1]
    return range_pct < 8 and recent_close > high

# --- Main Scanning Function ---
def scan_stock(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        df = ticker.history(period="1mo")
        if df.empty:
            return None
        
        price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else price
        
        # Indicators
        ema21 = calculate_ema21(df)
        vwap = calculate_vwap(df)
        rsi = calculate_rsi_power(df)
        bb_squeeze = calculate_bb_squeeze(df)
        momentum_burst = detect_momentum_burst(df)
        consolidation_breakout = detect_consolidation_breakout(df)
        
        # Traded Value
        volume = df['Volume'].iloc[-1]
        traded_value = price * volume
        
        # Score
        score = 0
        if price > ema21:
            score += 15
        if price > vwap:
            score += 15
        if rsi > 60:
            score += 15
        elif rsi > 50:
            score += 8
        if momentum_burst:
            score += 20
        if consolidation_breakout:
            score += 20
        if bb_squeeze < 0.03:
            score += 10  # Tight squeeze => potential expansion
        if traded_value > 100_00_00_000:
            score += 5
        score = min(100, score)
        score = max(0, score)
        
        # Status & Action
        if score >= 75:
            status = "🎯 STRONG BUY"
            action = "🚀 BUY NOW"
        elif score >= 60:
            status = "📈 BUY ZONE"
            action = "📈 WATCH"
        elif score >= 40:
            status = "🛡️ RANGE-BOUND"
            action = "⏳ HOLD"
        else:
            status = "📉 WEAK"
            action = "📉 AVOID"
        
        # Entry Decision
        if score >= 75 and price > ema21 and price > vwap and rsi > 60:
            entry = "✅ BUY NOW"
        elif score >= 60 and price > ema21:
            entry = "🟡 WATCH"
        else:
            entry = "⏳ HOLD"
        
        return {
            'symbol': symbol + ".NS",
            'price': round(price, 2),
            'ema21': round(ema21, 2),
            'vwap': round(vwap, 2),
            'rsi': round(rsi, 2),
            'bb_squeeze': round(bb_squeeze, 4),
            'momentum_burst': "✅" if momentum_burst else "❌",
            'consolidation': "✅" if consolidation_breakout else "❌",
            'traded_value': traded_value,
            'score': score,
            'action': action,
            'status': status,
            'entry': entry
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
        ema21 = calculate_ema21(df)
        vwap = calculate_vwap(df)
        rsi = calculate_rsi_power(df)
        return {
            'symbol': "NIFTY_INDEX",
            'price': round(price, 2),
            'ema21': round(ema21, 2),
            'vwap': round(vwap, 2),
            'rsi': round(rsi, 2),
            'bb_squeeze': "-",
            'momentum_burst': "-",
            'consolidation': "-",
            'traded_value': "-",
            'score': "-",
            'action': "NIFTY",
            'status': f"{((price - df['Close'].iloc[-5]) / df['Close'].iloc[-5]) * 100:.2f}%",
            'entry': "-"
        }
    except Exception as e:
        logging.error(f"Error scanning NIFTY: {e}")
        return None

# --- Main Update ---
def update_google_sheet():
    logging.info("🚀 AI Bro Super Scanner 2.0 – Starting...")
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
        
        # NIFTY Index
        nifty = scan_nifty()
        if nifty:
            final_data.append([
                nifty['symbol'], nifty['price'], nifty['action'], nifty['status'],
                nifty['score'], "-", "-",
                nifty['ema21'], nifty['vwap'], nifty['rsi'],
                "-", "-", nifty['entry'],
                timestamp
            ])
        
        # Stocks
        for sym in UNIVERSE[:150]:
            data = scan_stock(sym)
            if data:
                final_data.append([
                    data['symbol'], data['price'], data['action'], data['status'],
                    data['score'], f"₹{data['traded_value']/1e7:.2f}Cr", data['momentum_burst'],
                    data['ema21'], data['vwap'], data['rsi'],
                    data['bb_squeeze'], data['consolidation'], data['entry'],
                    timestamp
                ])
            time.sleep(0.1)
        
        logging.info(f"📊 final_data rows: {len(final_data)}")
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SUPER SCANNER 2.0 - {date_stamp}", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [
            ['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Traded Value', 'Momentum Burst',
             'EMA21', 'VWAP', 'RSI', 'BB Squeeze', 'Consolidation', 'Entry', 'Time']
        ]
        dash_sheet.update(range_name='A2', values=header2)
        
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows")
        else:
            test_row = [["TEST", 100, "HOLD", "TEST", 50, "1 Cr", "✅", 100, 95, 50, 0.02, "✅", "HOLD", timestamp]]
            dash_sheet.update(range_name='A3', values=test_row)
        
        dash_sheet.freeze(rows=2)
        logging.info("✅ Update completed!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
