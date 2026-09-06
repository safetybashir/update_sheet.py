import os
import json
import warnings
import yfinance as yf
import pandas as pd
import numpy as np
import gspread
from datetime import datetime
import pytz
from gspread_formatting import *

warnings.filterwarnings("ignore")

# 🎯 TARGET MASTER SPREADSHEET ID
SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg"
BULLISH_TAB_NAME = "LIVE_BULLISH_CASH_DASHBOARD"

def get_gspread_client():
    creds_json = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDS")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if creds_json:
        return gspread.authorize(gspread.auth.Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes))
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json")
    else:
        raise FileNotFoundError("❌ Credentials not found!")

def setup_dashboard_formatting(worksheet, num_rows):
    print("🎨 Applying Professional Dynamic Formatting...")
    header_fmt = cellFormat(backgroundColor=color(0.11, 0.16, 0.20), textFormat=textFormat(bold=True, foregroundColor=color(1, 1, 1), fontSize=10), horizontalAlignment='CENTER')
    default_row_fmt = cellFormat(backgroundColor=color(1, 1, 1), textFormat=textFormat(bold=False, foregroundColor=color(0.2, 0.2, 0.2), fontSize=9), horizontalAlignment='CENTER')
    format_cell_ranges(worksheet, [("A1:O1", header_fmt), (f"A2:O{num_rows+1}", default_row_fmt)])
    
    set_row_height(worksheet, "1:1", 35)
    set_column_width(worksheet, "A", 150)
    set_column_width(worksheet, "C", 140)
    set_column_width(worksheet, "D", 220)
    set_column_width(worksheet, "M", 280)
    set_column_width(worksheet, "N", 240)

    # Dynamic Highlight Rules based on Signal Strength
    rule_range = GridRange.from_a1_range(f'A2:O{num_rows+1}', worksheet)
    rule_green = ConditionalFormatRule(
        ranges=[rule_range],
        booleanRule=BooleanRule(
            condition=BooleanCondition(type='CUSTOM_FORMULA', values=['=ISNUMBER(SEARCH("SUPER STRONG", $M2))']),
            format=cellFormat(backgroundColor=color(0.83, 0.93, 0.87), textFormat=textFormat(bold=True, foregroundColor=color(0, 0.4, 0.1)))
        )
    )
    rule_yellow = ConditionalFormatRule(
        ranges=[rule_range],
        booleanRule=BooleanRule(
            condition=BooleanCondition(type='CUSTOM_FORMULA', values=['=ISNUMBER(SEARCH("HIGH WATCH", $M2))']),
            format=cellFormat(backgroundColor=color(0.98, 0.95, 0.81), textFormat=textFormat(bold=False, foregroundColor=color(0.4, 0.3, 0)))
        )
    )
    rules = get_conditional_format_rules(worksheet)
    rules.clear()
    rules.append(rule_green)
    rules.append(rule_yellow)
    rules.save()

# CASH SEGMENT WATCHLIST (NSE TICKERS)
CASH_STOCKS = [
    "ULTRACEMCO", "BSE", "KAYNES", "TORNTPHARM", "ASHOKLEY", "INOXWIND", "GAIL", "KEI", 
    "CGPOWER", "M&M", "DIVISLAB", "MOTHERSON", "GLENMARK", "MAZDOCK", "DELHIVERY",
    "TVSMOTOR", "POLYCAB", "SIEMENS", "CUMMINSIND", "JSWENERGY", "ANGELONE", "COCHINSHIP", 
    "LAURUSLABS", "MOTILALOFS", "BHARATFORG", "TATASTEEL", "LTF", "PRESTIGE", "HAL", 
    "SUZLON", "TATAPOWER", "DMART", "RVNL", "RELIANCE", "BHEL", "NHPC", "JINDALSTEL", 
    "BEL", "TITAN", "OBEROIRLTY", "BHARTIARTL", "TATAELXSI", "HINDALCO", "CIPLA", 
    "MARUTI", "ZOMATO", "TRENT", "DRREDDY", "JSWSTEEL", "SAIL", "PFC", "RECLTD", "ITC"
]

def analyze_stocks():
    print("⏳ Fetching Real Market Data (Last 60 Days) to analyze continuous uptrend...")
    tickers = [f"{sym}.NS" for sym in CASH_STOCKS]
    
    # Download 3 months data to accurately calculate 20 & 50 DMA
    data = yf.download(tickers, period="3mo", group_by="ticker", auto_adjust=True, progress=False)
    
    list_bullish = []
    ist_tz = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist_tz).strftime('%H:%M:%S')

    for sym in CASH_STOCKS:
        try:
            ticker_ns = f"{sym}.NS"
            df = data[ticker_ns].dropna()
            if len(df) < 50:
                continue

            # Core Values
            close = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            high = df['High'].iloc[-1]
            low = df['Low'].iloc[-1]
            vol_today = df['Volume'].iloc[-1]

            # Change & Range Calculations
            chg_pct = round(((close - prev_close) / prev_close) * 100, 2)
            day_range = round(high - low, 2)
            day_pos_pct = round(((close - low) / day_range) * 100, 1) if day_range > 0 else 0

            # 🚀 CONTINUOUS UPTREND METRICS (SUPER STRONG)
            df['20_DMA'] = df['Close'].rolling(window=20).mean()
            df['50_DMA'] = df['Close'].rolling(window=50).mean()
            df['20_Day_High'] = df['High'].rolling(window=20).max()
            df['10_Day_Vol_Avg'] = df['Volume'].rolling(window=10).mean()

            dma_20 = df['20_DMA'].iloc[-1]
            dma_50 = df['50_DMA'].iloc[-1]
            high_20_day = df['20_Day_High'].iloc[-2] # High before today
            vol_avg_10 = df['10_Day_Vol_Avg'].iloc[-2] # Avg before today

            # Multipliers & Breakouts
            vol_mult = round(vol_today / vol_avg_10, 2) if vol_avg_10 > 0 else 1.0
            
            # Trend Check (LTP > 20 DMA > 50 DMA)
            is_uptrend = "YES" if (close > dma_20 and dma_20 > dma_50) else "NO"
            
            # 20-Day Monthly Breakout Check
            monthly_breakout = "YES (20-DAY HIGH)" if close > high_20_day else "NO"

            # Strict Logic for SUPER STRONG FRIDAY SCAN
            target = round(close * 1.04, 2) # +4% Target
            sl = round(close * 0.98, 2)     # -2% Stop Loss

            if chg_pct >= 2.0 and is_uptrend == "YES" and monthly_breakout != "NO" and vol_mult >= 2.0 and day_pos_pct >= 85.0:
                bull_setup = "TRENDING & INSTITUTIONAL BUYING"
                bull_signal = "⭐ SUPER STRONG CASH BREAKOUT"
                bull_action = "🟢 STRONG BUY / DELIVERY"
                vol_spike_str = "🔥 MASSIVE DELIVERY"
            elif chg_pct >= 1.5 and is_uptrend == "YES" and vol_mult >= 1.5 and day_pos_pct >= 70.0:
                bull_setup = "UPTREND ACCUMULATION"
                bull_signal = "⚡ HIGH WATCH BUY"
                bull_action = "👀 MONITOR FOR PULLBACK"
                vol_spike_str = "⚡ GOOD VOLUME"
            else:
                if chg_pct < 0:
                    continue # Skip negative stocks from Bullish scan
                bull_setup = "NORMAL MOVEMENT"
                bull_signal = "😴 NO SIGNAL"
                bull_action = "❌ NO TRADE"
                vol_spike_str = "😴 NORMAL VOLUME"

            list_bullish.append([
                sym, round(close, 2), f"{chg_pct}%", monthly_breakout, is_uptrend, f"{day_pos_pct}%", 
                vol_mult, vol_spike_str, round(dma_20, 2), target, sl, 
                bull_setup, bull_signal, bull_action, curr_time
            ])

        except Exception as e:
            continue

    headers = [
        "STOCK TICKER", "CASH LTP", "DAY CHANGE %", "MONTHLY BREAKOUT", "CONTINUOUS UPTREND", 
        "DAY RANGE POS %", "VOLUME MULTIPLIER", "VOLUME SPIKE", "20 DMA SUPPORT", "TARGET PRICE (+4%)", 
        "STOP LOSS (-2%)", "CASH BREAKOUT SETUP", "SIGNAL STRENGTH", "ACTION TRIGGER", "LAST UPDATED"
    ]

    # Rank SUPER STRONG on TOP, then HIGH WATCH
    priority_map = {"⭐ SUPER STRONG CASH BREAKOUT": 0, "⚡ HIGH WATCH BUY": 1, "😴 NO SIGNAL": 2}
    
    df_bullish = pd.DataFrame(list_bullish, columns=headers)
    if not df_bullish.empty:
        df_bullish["RANK"] = df_bullish["SIGNAL STRENGTH"].map(priority_map).fillna(99)
        # Sort by Rank first, then by Volume Multiplier (highest volume on top)
        df_bullish = df_bullish.sort_values(by=["RANK", "VOLUME MULTIPLIER"], ascending=[True, False]).drop(columns=["RANK"])
        payload = [headers] + df_bullish.values.tolist()
    else:
        payload = [headers]

    return payload

def run_live_cash_sync():
    client = get_gspread_client()
    sheet = client.open_by_key(SHEET_ID)
    try:
        ws_bullish = sheet.worksheet(BULLISH_TAB_NAME)
    except:
        ws_bullish = sheet.add_worksheet(title=BULLISH_TAB_NAME, rows="300", cols="20")
    
    payload = analyze_stocks()
    
    # 1. Update Data
    ws_bullish.clear()
    ws_bullish.update(values=payload, range_name="A1", value_input_option="USER_ENTERED")
    
    # 2. Apply Custom Colors and Dynamic Conditions
    setup_dashboard_formatting(ws_bullish, len(payload))
    
    print(f"🚀 Dashboard Super Strong Scan Completed Successfully!")

if __name__ == "__main__":
    run_live_cash_sync()
