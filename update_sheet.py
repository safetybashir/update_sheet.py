# update_sheet.py – AI Bro Scanner (Diversified Stocks + NIFTY Index + 15-Min Candle)
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

# --- DIVERSIFIED UNIVERSE (1 Stock per Sector) ---
UNIVERSE = [
    'RELIANCE', 'ONGC', 'TCS', 'INFY', 'HCLTECH', 'HDFCBANK', 'ICICIBANK', 'SBIN',
    'HINDUNILVR', 'ITC', 'MARUTI', 'TATAMOTORS', 'SUNPHARMA', 'DRREDDY', 'TATASTEEL',
    'HINDALCO', 'BHARTIARTL', 'TITAN', 'NTPC', 'POWERGRID', 'DLF', 'ULTRACEMCO', 'INDIGO'
]

# --- NIFTY Index ---
NIFTY_SYMBOL = "^NSEI"

# --- Stock Data Fetch with 15-Min Signal ---
def get_stock_data_with_signal(symbol):
    try:
        ticker = yf.Ticker(symbol + ".NS")
        
        # FIXED BUG 1: Period changed from 5d to 1y to calculate 50/200 SMA and 14 RSI correctly
        df_daily = ticker.history(period="1y")
        if df_daily.empty or len(df_daily) < 2:
            return None
        
        ltp = df_daily['Close'].iloc[-1]
        prev_close = df_daily['Close'].iloc[-2]
        vol = df_daily['Volume'].iloc[-1]
        
        # Average Volume over last 20 days
        avg_vol = df_daily['Volume'].tail(20).mean()
        
        # Week Change (last 5 trading days)
        week_change = ((ltp - df_daily['Close'].iloc[-5]) / df_daily['Close'].iloc[-5]) * 100 if len(df_daily) >= 5 else 0
        
        # SMAs
        sma50 = df_daily['Close'].rolling(50).mean().iloc[-1] if len(df_daily) >= 50 else ltp
        sma200 = df_daily['Close'].rolling(200).mean().iloc[-1] if len(df_daily) >= 200 else ltp
        
        # Accurate RSI Calculation
        if len(df_daily) > 14:
            delta = df_daily['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70
        else:
            rsi = 50
        
        # Traded Value
        traded_value = ltp * vol
        
        # Scoring System
        score = 0
        if traded_value > 100_00_00_000:
            score += 40
        elif traded_value > 50_00_00_000:
            score += 30
        elif traded_value > 10_00_00_000:
            score += 15
        else:
            score += 5
        
        if ltp > sma50: score += 10
        if ltp > sma200: score += 10
        if rsi > 60: score += 20
        elif rsi > 50: score += 10
        if week_change > 5: score += 10
        elif week_change > 2: score += 5
        
        score = min(100, max(0, score))
        
        # Status Label
        if score >= 75: status = "🎯 STRONG BUY"
        elif score >= 60: status = "📈 BUY ZONE"
        elif score >= 40: status = "🛡️ RANGE-BOUND"
        elif score >= 20: status = "📉 WEAK"
        else: status = "⚠️ DUMPING"
        
        # 15-Minute Candle Strategy
        df_15min = ticker.history(period="1d", interval="15m")
        signal = "⏳ WAIT"
        reason = "No Signal"
        if len(df_15min) >= 3:
            current_close = df_15min['Close'].iloc[-1]
            prev_high = df_15min['High'].iloc[-2]
            prev_low = df_15min['Low'].iloc[-2]
            current_vol = df_15min['Volume'].iloc[-1]
            prev_vol = df_15min['Volume'].iloc[-2]
            
            if current_close > prev_high and current_vol > prev_vol * 1.5:
                signal = "📈 BUY CALL"
                reason = "Bullish Breakout"
            elif current_close < prev_low and current_vol > prev_vol * 1.5:
                signal = "📉 BUY PUT"
                reason = "Bearish Breakdown"
        
        # Entry Decision
        if score >= 75 and ltp > sma50 and ltp > sma200 and rsi > 60 and week_change > 0:
            entry = "✅ BUY NOW"
        elif score >= 60 and ltp > sma50 and ltp > sma200 and rsi > 50:
            entry = "🟡 WATCH"
        elif score >= 40:
            entry = "⏳ HOLD"
        else:
            entry = "🔴 AVOID"
            
        action = "🚀 BUY NOW" if score >= 75 else ("📈 WATCH" if score >= 60 else ("⏳ HOLD" if score >= 40 else "📉 AVOID"))
        
        return {
            'symbol': symbol + ".NS",
            'ltp': round(ltp, 2),
            'action': action,
            'status': status,
            'score': score,
            'volume': f"{vol:,}",
            'traded_value': f"₹{traded_value/1e7:.2f}Cr",
            'week_change': f"{week_change:.2f}%",
            'rsi': round(rsi, 2),
            'sma50': round(sma50, 2),
            'sma200': round(sma200, 2),
            'prev_close': round(prev_close, 2),
            'entry': entry,
            'signal': signal,
            'reason': reason
        }
    except Exception as e:
        logging.error(f"Error processing {symbol}: {e}")
        return None

# --- NIFTY Index Data ---
def get_index_data_with_signal():
    try:
        ticker = yf.Ticker(NIFTY_SYMBOL)
        df_daily = ticker.history(period="5d")
        if df_daily.empty:
            return None
        
        ltp = df_daily['Close'].iloc[-1]
        prev_close = df_daily['Close'].iloc[-2] if len(df_daily) > 1 else ltp
        vol = df_daily['Volume'].iloc[-1]
        
        df_15min = ticker.history(period="1d", interval="15m")
        signal = "⏳ WAIT"
        reason = "No Signal"
        if len(df_15min) >= 3:
            current_close = df_15min['Close'].iloc[-1]
            prev_high = df_15min['High'].iloc[-2]
            prev_low = df_15min['Low'].iloc[-2]
            current_vol = df_15min['Volume'].iloc[-1]
            prev_vol = df_15min['Volume'].iloc[-2]
            
            if current_close > prev_high and current_vol > prev_vol * 1.5:
                signal = "📈 BUY CALL"
                reason = "NIFTY Bullish"
            elif current_close < prev_low and current_vol > prev_vol * 1.5:
                signal = "📉 BUY PUT"
                reason = "NIFTY Bearish"
        
        return {
            'symbol': "NIFTY_INDEX",
            'ltp': round(ltp, 2),
            'action': signal,
            'status': reason,
            'score': "-",
            'volume': f"{vol:,}",
            'traded_value': "-",
            'week_change': "-",
            'rsi': "-",
            'sma50': "-",
            'sma200': "-",
            'prev_close': round(prev_close, 2),
            'entry': "-",
            'signal': signal,
            'reason': reason
        }
    except Exception as e:
        logging.error(f"Error fetching NIFTY: {e}")
        return None

# --- Main Update Function ---
def update_google_sheet():
    logging.info("🚀 AI Bro Scanner – Starting Update Process")
    
    try:
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info("✅ Connected to Google Sheet")
        
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        final_data = []
        
        # 1. Fetch NIFTY
        index_data = get_index_data_with_signal()
        if index_data:
            final_data.append([
                index_data['symbol'], index_data['ltp'], index_data['action'], index_data['status'],
                index_data['score'], index_data['volume'], index_data['traded_value'], index_data['week_change'],
                index_data['rsi'], index_data['sma50'], index_data['sma200'], index_data['prev_close'],
                index_data['entry'], index_data['signal'] + " - " + index_data['reason'], timestamp
            ])
        
        # 2. Fetch All Stocks
        for sym in UNIVERSE:
            data = get_stock_data_with_signal(sym)
            if data:
                final_data.append([
                    data['symbol'], data['ltp'], data['action'], data['status'],
                    data['score'], data['volume'], data['traded_value'], data['week_change'],
                    data['rsi'], data['sma50'], data['sma200'], data['prev_close'],
                    data['entry'], data['signal'] + " - " + data['reason'], timestamp
                ])
            time.sleep(0.2) # API Rate limit control for Yahoo Finance
        
        # 3. Clear and Update Sheet in Bulk
        dash_sheet.clear()
        
        header = [[f"📊 AI BRO SCANNER - {date_stamp} (10-Min Update, 15-Min Candle)", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [['Symbol', 'LTP', 'Action', 'Status', 'Score', 'Volume', 'Traded Value', 'Week %', 'RSI', 'SMA50', 'SMA200', 'Prev Close', 'Entry Decision', '15-Min Signal', 'Time']]
        dash_sheet.update(range_name='A2', values=header2)
        
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows successfully!")
        
        dash_sheet.freeze(rows=2)
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    update_google_sheet()
