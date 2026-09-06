import os
import json
import warnings
from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
import pytz

warnings.filterwarnings("ignore")

# 🎯 TARGET MASTER SPREADSHEET CONFIGURATION
SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg"
BULLISH_TAB_NAME = "LIVE_BULLISH_CASH_DASHBOARD"

# ==========================================
# 📌 CASH SEGMENT WATCHLIST (GLOBAL DEFINITION)
# ==========================================
CASH_STOCKS = [
    "BSE", "KAYNES", "ULTRACEMCO", "ASHOKLEY", "COALINDIA", "CONCOR", "DABUR",
    "INOXWIND", "GAIL", "KEI", "CGPOWER", "M&M", "DIVISLAB", "MOTHERSON", "GLENMARK",
    "MAZDOCK", "DELHIVERY", "TVSMOTOR", "POLYCAB", "SIEMENS", "CUMMINSIND", "JSWENERGY",
    "ANGELONE", "COCHINSHIP", "LAURUSLABS", "MOTILALOFS", "BHARATFORG", "TATASTEEL",
    "LTF", "PRESTIGE", "HAL", "SUZLON", "TATAPOWER", "DMART", "RVNL", "RELIANCE",
    "BHEL", "NHPC", "JINDALSTEL", "BEL", "TITAN", "OBEROIRLTY", "BHARTIARTL",
    "TATAELXSI", "HINDALCO", "CIPLA", "MARUTI", "ZOMATO", "TRENT", "DRREDDY",
    "JSWSTEEL", "SAIL", "PFC", "RECLTD", "ITC"
]

def get_gspread_client():
    """Authenticates with Google Sheets API using GitHub Secrets or local JSON."""
    creds_json = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDS")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if creds_json:
        creds_dict = json.loads(creds_json)
        return gspread.service_account_from_dict(creds_dict, scopes=scopes)
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json", scopes=scopes)
    else:
        raise FileNotFoundError("❌ Google Credentials not found in Secrets or local file!")

def analyze_cash_breakouts():
    """Fetches market data, applies VCP & Volume filters, and generates dashboard signals."""
    print("⏳ Fetching Real Market Data for Cash Segment...")
    tickers = [f"{sym}.NS" for sym in CASH_STOCKS]
    
    # Download 60 days OHLCV batch data
    data = yf.download(tickers, period="60d", interval="1d", group_by="ticker", progress=False)
    
    ist = pytz.timezone("Asia/Kolkata")
    time_str = datetime.now(ist).strftime("%H:%M:%S")
    
    results = []

    for sym in CASH_STOCKS:
        try:
            t_str = f"{sym}.NS"
            df = data[t_str].dropna() if len(CASH_STOCKS) > 1 else data.dropna()
            
            if len(df) < 10:
                continue

            # Core Metrics Calculation
            ltp = float(df['Close'].iloc[-1])
            prev_close = float(df['Close'].iloc[-2])
            day_change_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
            
            high_day = float(df['High'].iloc[-1])
            low_day = float(df['Low'].iloc[-1])
            vol_today = float(df['Volume'].iloc[-1])
            
            # 5-Day High Breakout
            five_day_high = float(df['High'].iloc[-6:-1].max())
            weekly_breakout = "YES (5-DAY HIGH)" if ltp >= five_day_high else "NO"
            
            # Day Range Position %
            day_range = high_day - low_day
            day_pos_pct = round(((ltp - low_day) / day_range) * 100, 2) if day_range > 0 else 50.0
            
            # Volume Multiplier (vs 10-day Avg)
            vol_avg_10 = float(df['Volume'].iloc[-11:-1].mean())
            vol_mult = round(vol_today / vol_avg_10, 2) if vol_avg_10 > 0 else 1.0
            
            # Volume Spike Status
            if vol_mult >= 2.5:
                vol_status = "🔥 MASSIVE DELIVERY"
            elif vol_mult >= 1.4:
                vol_status = "⚡ MODERATE VOLUME"
            else:
                vol_status = "NORMAL VOLUME"
                
            # Intraday VWAP Approximation
            vwap = round((high_day + low_day + ltp) / 3, 2)
            price_vs_vwap = "ABOVE VWAP" if ltp >= vwap else "BELOW VWAP"
            
            # Target (+3%) & Stoploss (-1.5%)
            target_price = round(ltp * 1.03, 2)
            stop_loss = round(ltp * 0.985, 2)
            
            # Cash Setup Classification
            if weekly_breakout.startswith("YES") and vol_mult >= 2.5 and day_pos_pct >= 85:
                setup = "EXTREME INSTITUTIONAL BUYING"
                strength = "⭐ TOP FRIDAY BULLISH CASH BREAKOUT"
                action = "🟢 STRONG BUY CASH / DELIVERY"
            elif day_change_pct > 1.0 and vol_mult >= 1.3:
                setup = "GOOD ACCUMULATION"
                strength = "⚡ HIGH WATCH BUY"
                action = "👀 MONITOR FOR CASH ENTRY"
            else:
                setup = "CONSOLIDATION"
                strength = "NEUTRAL"
                action = "HOLD / WAIT"

            # Filter for Quality Signals
            if action != "HOLD / WAIT":
                results.append([
                    sym,
                    ltp,
                    f"{day_change_pct:.2f}%",
                    weekly_breakout,
                    f"{day_pos_pct:.2f}%",
                    vol_mult,
                    vol_status,
                    vwap,
                    price_vs_vwap,
                    target_price,
                    stop_loss,
                    setup,
                    strength,
                    action,
                    time_str
                ])
        except Exception as e:
            continue

    # Sort results by Volume Multiplier & Day Change %
    results = sorted(results, key=lambda x: (x[5], float(x[2].replace('%', ''))), reverse=True)
    return results

def run_live_cash_sync():
    """Syncs processed scanner output into Master Google Sheet."""
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SHEET_ID)
        
        try:
            worksheet = sheet.worksheet(BULLISH_TAB_NAME)
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=BULLISH_TAB_NAME, rows="100", cols="20")

        headers = [
            "STOCK TICKER", "CASH LTP", "DAY CHANGE %", "WEEKLY HIGH BREAKOUT",
            "DAY RANGE POS %", "VOLUME MULTIPLIER", "VOLUME SPIKE STATUS", "VWAP",
            "PRICE vs VWAP", "TARGET PRICE (+3%)", "STOP LOSS (-1.5%)", 
            "CASH BREAKOUT SETUP", "SIGNAL STRENGTH", "ACTION TRIGGER", "LAST UPDATED"
        ]
        
        scanned_data = analyze_cash_breakouts()
        
        # Clear existing sheet data and update with fresh layout
        worksheet.clear()
        full_payload = [headers] + scanned_data
        worksheet.update(values=full_payload, range_name="A1")
        
        print(f"✅ Successfully Updated {len(scanned_data)} Cash Breakout Signals to '{BULLISH_TAB_NAME}'!")

    except Exception as err:
        print(f"❌ Error during Google Sheet Sync: {str(err)}")
        raise err

if __name__ == "__main__":
    run_live_cash_sync()
