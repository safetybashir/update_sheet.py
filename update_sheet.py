# update_sheet.py – AI Bro Scanner (Lightweight 5-Stock Test Version)
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

# --- LIGHTWEIGHT TEST UNIVERSE (Only 5 Mega Caps) ---
UNIVERSE = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'TATASTEEL']
NIFTY_SYMBOL = "^NSEI"

# Fake browser headers to prevent yfinance blocking
yf.set_tz_cache_location(os.getcwd())

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

def scan_stock(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        # Explicitly fetching 1mo daily data
        df = ticker.history(period="1mo")
        if df.empty: 
            logging.warning(f"⚠️ {symbol} returned empty data.")
            return None
        
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
        
        high_52w, low_52w = price, price
        try:
            high_52w = ticker.info.get('fiftyTwoWeekHigh', price)
            low_52w = ticker.info.get('fiftyTwoWeekLow', price)
        except:
            pass
            
        is_breakout = price > high_52w * 0.98
        score = 50  # Default baseline score
        
        action, status = "📈 WATCH", "📈 BUY ZONE"
        entry = "🟡 WATCH"
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

def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Starting 5-Stock Test Setup...")
    try:
        creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info(f"✅ Sheet Connected Successfully: {sh.title}")
        
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        date_stamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%Y-%m-%d")
        
        final_data = []
        
        # Nifty Index
        nifty = scan_nifty()
        if nifty:
            final_data.append([nifty['symbol'], nifty['ltp'], nifty['action'], nifty['status'], nifty['score'],
                              nifty['volume'], nifty['traded_value'], nifty['week_change'], nifty['rsi'],
                              nifty['sma50'], nifty['sma200'], nifty['prev_close'], nifty['entry'],
                              nifty['ema21'], nifty['vwap'], nifty['bb_squeeze'], nifty['momentum_burst'],
                              nifty['consolidation'], nifty['breakout'], nifty['swing'], nifty['high_52w'],
                              nifty['low_52w'], timestamp])
        
        # Core 5 Stocks Loop
        for sym in UNIVERSE:
            data = scan_stock(sym)
            if data:
                final_data.append([data['symbol'], data['ltp'], data['action'], data['status'], data['score'],
                                  data['volume'], f"₹{data
