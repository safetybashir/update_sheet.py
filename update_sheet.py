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
from datetime import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.oauth2.service_account import Credentials

# Optional: Google Gemini AI for interpretation (if API key available)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

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
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', None)
except Exception as e:
    logging.error(f"❌ Failed to load credentials: {e}")
    sys.exit(1)

# --- Stock Universe (Nifty 50 + Midcap + Your existing) ---
UNIVERSE = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'HINDUNILVR',
    'ICICIBANK', 'ITC', 'KOTAKBANK', 'SBIN', 'BHARTIARTL',
    'LT', 'AXISBANK', 'BAJFINANCE', 'HCLTECH', 'WIPRO',
    'SUNPHARMA', 'TITAN', 'MARUTI', 'ONGC', 'NTPC',
    'TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI', 'TORNTPHARM',
    'AVANTIFEED', 'DIXON', 'EICHERMOT', 'RVNL', 'KAYNES',
    'WAAREEENER', 'SOLARINDS', 'WABAG', 'ALKEM', 'DIVISLAB',
    'JSWSTEEL', 'APOLLOHOSP', 'POWERINDIA', 'BAJAJ-AUTO',
    'ULTRACEMCO', 'INDIGO', 'MAXHEALTH'
]

# --- AI Interpretation (Gemini) ---
def get_ai_insight(symbol, score, ltp, week_change, volume, sma50, sma200):
    """Generate AI interpretation using Gemini."""
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return "-"
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Stock: {symbol}
        Price: {ltp}, Week Change: {week_change}%, Volume: {volume}
        SMA50: {sma50}, SMA200: {sma200}
        Institutional Score: {score}
        
        Generate one-line actionable insight for a trader.
        """
        response = model.generate_content(prompt)
        return response.text[:60]  # Trim to 60 chars
    except:
        return "AI insight unavailable"

# --- Core Logic: Institutional Score 2.0 ---
def get_institutional_score(ticker_obj):
    """Enhanced institutional score with multi-timeframe trend."""
    try:
        df = ticker_obj.history(period="6mo")
        if df.empty:
            return "⏳ NO DATA", 0, 0, 0, 0, 0, 0, 0
        
        ltp = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else ltp
        high = df['High'].iloc[-1]
        low = df['Low'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].mean()
        
        # Moving Averages
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        sma50 = df['Close'].rolling(50).mean().iloc[-1]
        sma200 = df['Close'].rolling(200).mean().iloc[-1]
        
        # --- Institutional Score Components ---
        price_score = 0
        volume_score = 0
        trend_score = 0
        
        # Price Action
        if ltp > prev_close:
            price_score += 3
        if ltp > sma20:
            price_score += 2
        if ltp > sma50:
            price_score += 1
        if ltp > sma200:
            price_score += 1
        
        # Volume
        if vol > avg_vol * 1.5:
            volume_score += 3
        elif vol > avg_vol:
            volume_score += 1
        
        # Trend
        if sma20 > sma50 > sma200:
            trend_score += 3
        elif sma50 > sma200:
            trend_score += 1
        
        # --- Relative Strength (RSI) ---
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs.iloc[-1])) if loss.iloc[-1] != 0 else 70
        
        rsi_score = 1 if rsi > 60 else 0
        if rsi > 70:
            rsi_score = -1  # Overbought warning
        
        # --- Final Institutional Score (0-100) ---
        score = min(100, int((price_score + volume_score + trend_score + rsi_score + 3) * 10))
        score = max(0, score)  # Ensure non-negative
        
        # --- Status ---
        if score >= 75:
            status = "🎯 STRONG BUY"
        elif score >= 60:
            status = "📈 BUY ZONE"
        elif score >= 40:
            status = "🛡️ RANGE-BOUND"
        elif score >= 20:
            status = "📉 WEAK"
        else:
            status = "⚠️ DUMPING"
        
        return status, score, round(ltp, 2), round(vol, 0), round(week_change, 2), round(sma50, 2), round(sma200, 2), round(rsi, 2)
    
    except Exception as e:
        logging.error(f"Error calculating score: {e}")
        return "⏳ SYNCING", 0, 0, 0, 0, 0, 0, 0

# --- Fetch All Stocks in Parallel ---
def fetch_all_stocks(universe):
    """Fetch data for all stocks using ThreadPoolExecutor."""
    results = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_symbol = {
            executor.submit(get_institutional_score, yf.Ticker(sym + ".NS")): sym
            for sym in universe
        }
        for future in as_completed(future_to_symbol):
            sym = future_to_symbol[future]
            try:
                status, score, ltp, vol, week_change, sma50, sma200, rsi = future.result()
                results.append((sym, status, score, ltp, vol, week_change, sma50, sma200, rsi))
            except Exception as e:
                logging.error(f"Error processing {sym}: {e}")
                results.append((sym, "❌ ERROR", 0, 0, 0, 0, 0, 0, 0))
    return results

# --- Main Update Function ---
def update_google_sheet():
    """Main function to update Google Sheet."""
    logging.info("🚀 AI Bro Super Scanner 2.0 – Starting...")
    
    try:
        # 1. Authenticate with Google
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        dash_sheet = sh.get_worksheet(0)
        logging.info("✅ Connected to Google Sheet")
        
        # 2. Fetch data
        results = fetch_all_stocks(UNIVERSE)
        logging.info(f"📊 Fetched data for {len(results)} stocks")
        
        # 3. Prepare data for sheet
        ist = pytz.timezone('Asia/Kolkata')
        timestamp = dt.now(ist).strftime("%H:%M:%S")
        date_stamp = dt.now(ist).strftime("%Y-%m-%d")
        
        # Sort by score (highest first)
        results.sort(key=lambda x: x[2], reverse=True)
        
        final_data = []
        for sym, status, score, ltp, vol, week_change, sma50, sma200, rsi in results:
            # Action Plan based on score
            if score >= 75:
                action = "🚀 BUY NOW"
            elif score >= 60:
                action = "📈 WATCH"
            elif score >= 40:
                action = "⏳ HOLD"
            else:
                action = "📉 AVOID"
            
            # AI Insight
            ai_insight = get_ai_insight(sym, score, ltp, week_change, vol, sma50, sma200)
            
            final_data.append([
                sym + ".NS",
                ltp,
                action,
                status,
                score,
                f"{vol:,}",
                f"{week_change}%",
                rsi,
                f"{sma50:.2f}",
                f"{sma200:.2f}",
                ai_insight,
                timestamp
            ])
        
        # 4. Clear and Update Sheet
        dash_sheet.clear()
        
        # Header with date
        header = [[f"📊 AI BRO SUPER SCANNER 2.0 - {date_stamp}", "", "", "", "", "", "", "", "", "", "", ""]]
        dash_sheet.update(range_name='A1', values=header)
        
        header2 = [['Symbol', 'LTP', 'Action', 'Trend Status', 'Score', 'Volume', 'Week %', 'RSI', 'SMA50', 'SMA200', 'AI Insight', 'Time']]
        dash_sheet.update(range_name='A2', values=header2)
        
        if final_data:
            dash_sheet.update(range_name='A3', values=final_data)
            logging.info(f"✅ Updated {len(final_data)} rows in sheet")
        
        dash_sheet.freeze(rows=2)
        logging.info("✅ AI Bro Super Scanner 2.0 – Update completed!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed to update sheet: {e}")
        return False

# --- Run ---
if __name__ == "__main__":
    update_google_sheet()
