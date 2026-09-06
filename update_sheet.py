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

# 🎯 MASTER SPREADSHEET CONFIG
SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg"
BULLISH_TAB_NAME = "LIVE_BULLISH_CASH_DASHBOARD"

CASH_STOCKS = [
    "BSE", "KAYNES", "ULTRACEMCO", "ASHOKLEY", "COALINDIA", "CONCOR", "DABUR",
    "INOXWIND", "GAIL", "KEI", "CGPOWER", "M&M", "DIVISLAB", "MOTHERSON", "GLENMARK",
    "MAZDOCK", "DELHIVERY", "TVSMOTOR", "POLYCAB", "SIEMENS", "CUMMINSIND", "JSWENERGY",
    "ANGELONE", "COCHINSHIP", "LAURUSLABS", "MOTILALOFS", "BHARATFORG", "TATASTEEL",
    "LTF", "PRESTIGE", "HAL", "SUZLON", "TATAPOWER", "DMART", "RVNL", "RELIANCE",
    "BHEL", "NHPC", "JINDALSTEL", "BEL", "TITAN", "OBEROIRLTY", "BHARTIARTL"
]

def get_gspread_client():
    creds_json = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDS")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if creds_json:
        return gspread.service_account_from_dict(json.loads(creds_json), scopes=scopes)
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json", scopes=scopes)
    else:
        raise FileNotFoundError("❌ Credentials not found!")

def analyze_cash_breakouts():
    print("⏳ Running Strict Friday Breakout Scan...")
    tickers = [f"{sym}.NS" for sym in CASH_STOCKS]
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

            ltp = round(float(df['Close'].iloc[-1]), 2)
            prev_close = float(df['Close'].iloc[-2])
            day_change_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
            
            high_day = float(df['High'].iloc[-1])
            low_day = float(df['Low'].iloc[-1])
            vol_today = float(df['Volume'].iloc[-1])
            
            five_day_high = float(df['High'].iloc[-6:-1].max())
            weekly_breakout = "YES (5-DAY HIGH)" if ltp >= five_day_high else "NO"
            
            day_range = high_day - low_day
            day_pos_pct = round(((ltp - low_day) / day_range) * 100, 2) if day_range > 0 else 50.0
            
            vol_avg_10 = float(df['Volume'].iloc[-11:-1].mean())
            vol_mult = round(vol_today / vol_avg_10, 2) if vol_avg_10 > 0 else 1.0
            
            vol_status = "🔥 MASSIVE DELIVERY" if vol_mult >= 2.0 else "⚡ MODERATE VOLUME"
            vwap = round((high_day + low_day + ltp) / 3, 2)
            price_vs_vwap = "ABOVE VWAP" if ltp >= vwap else "BELOW VWAP"
            
            target_price = round(ltp * 1.03, 2)
            stop_loss = round(ltp * 0.985, 2)

            # 🎯 STRICT FRIDAY BREAKOUT CRITERIA RESTORATION
            setup_rank = 1
            if weekly_breakout.startswith("YES") and vol_mult >= 2.0 and day_pos_pct >= 85.0 and price_vs_vwap == "ABOVE VWAP":
                setup = "EXTREME INSTITUTIONAL BUYING"
                strength = "⭐ TOP FRIDAY BULLISH CASH BREAKOUT"
                action = "🟢 STRONG BUY CASH / DELIVERY"
                setup_rank = 3  # HIGHEST PRIORITY
            elif day_change_pct >= 1.5 and vol_mult >= 1.3:
                setup = "GOOD ACCUMULATION"
                strength = "⚡ HIGH WATCH BUY"
                action = "👀 MONITOR FOR CASH ENTRY"
                setup_rank = 2
            else:
                continue # Ignore non-quality setups

            results.append({
                "data": [
                    sym, ltp, f"{day_change_pct:.2f}%", weekly_breakout, f"{day_pos_pct:.2f}%",
                    vol_mult, vol_status, vwap, price_vs_vwap, target_price, stop_loss,
                    setup, strength, action, time_str
                ],
                "rank": setup_rank,
                "breakout": 1 if weekly_breakout.startswith("YES") else 0,
                "vol": vol_mult
            })
        except Exception:
            continue

    # Strict Sorting: 1. Setup Rank (TOP Friday Breakout First) -> 2. Weekly Breakout YES -> 3. Volume Multiplier
    sorted_results = sorted(results, key=lambda x: (x["rank"], x["breakout"], x["vol"]), reverse=True)
    return [item["data"] for item in sorted_results]

def run_live_cash_sync():
    client = get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)
    try:
        worksheet = sheet.worksheet(BULLISH_TAB_NAME)
    except:
        worksheet = sheet.add_worksheet(title=BULLISH_TAB_NAME, rows="100", cols="20")

    headers = [
        "STOCK TICKER", "CASH LTP", "DAY CHANGE %", "WEEKLY HIGH BREAKOUT",
        "DAY RANGE POS %", "VOLUME MULTIPLIER", "VOLUME SPIKE STATUS", "VWAP",
        "PRICE vs VWAP", "TARGET PRICE (+3%)", "STOP LOSS (-1.5%)", 
        "CASH BREAKOUT SETUP", "SIGNAL STRENGTH", "ACTION TRIGGER", "LAST UPDATED"
    ]
    
    scanned_data = analyze_cash_breakouts()
    worksheet.clear()
    worksheet.update(values=[headers] + scanned_data, range_name="A1")
    print(f"✅ Successfully Updated {len(scanned_data)} Restored Friday Signals!")

if __name__ == "__main__":
    run_live_cash_sync()
