import os
import json
import pytz
import numpy as np
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ==========================================
# 1. LIQUID F&O TICKERS LIST
# ==========================================
TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "BHARTIARTL.NS", "SBIN.NS", "LTIM.NS", "ITC.NS", "HINDUNILVR.NS",
    "LARSEN.NS", "TATAMOTORS.NS", "AXISBANK.NS", "KOTAKBANK.NS", "M&M.NS",
    "TATASTEEL.NS", "NTPC.NS", "POWERGRID.NS", "ADANIENT.NS", "SUNPHARMA.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "BAJFINANCE.NS", "HCLTECH.NS", "ONGC.NS",
    "MARUTI.NS", "ADANIPORTS.NS", "COALINDIA.NS", "BAJAJFINSV.NS", "NESTLEIND.NS",
    "JSWSTEEL.NS", "GRASIM.NS", "TECHM.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "WIPRO.NS", "SBILIFE.NS", "DRREDDY.NS", "CIPLA.NS",
    "BPCL.NS", "TATACONSUM.NS", "BRITANNIA.NS", "APOLLOHOSP.NS", "INDUSINDBK.NS",
    "DIVISLAB.NS", "HINDALCO.NS", "SHRIRAMFIN.NS", "BEL.NS", "TRENT.NS"
]

# ==========================================
# 2. PURE OI & VCP ENGINE LOGIC
# ==========================================
def calculate_pure_oi_vcp(df):
    """
    Pure OI-VCP Calculation Engine:
    - VCP Contraction: High-Low Range Tightening (T1 > T2 > T3)
    - Volume Dynamics: Volume Dry-Up during base, Heavy Spike on Breakout
    - CE/PE Option Sentiment: Price-Volume Action mapping for CE Bullish / PE Bearish Buildup
    """
    df = df.copy()

    # 1. Volume Averages & Volatility Spikes
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Spike'] = df['Volume'] > (1.5 * df['Vol_SMA_20'])
    df['Vol_DryUp'] = df['Volume'] < (0.6 * df['Vol_SMA_20'])

    # 2. VCP Contraction Ratio (T1: 20 Days -> T2: 10 Days -> T3: 5 Days)
    df['Range_20'] = (df['High'].rolling(20).max() - df['Low'].rolling(20).min()) / df['Close']
    df['Range_10'] = (df['High'].rolling(10).max() - df['Low'].rolling(10).min()) / df['Close']
    df['Range_5']  = (df['High'].rolling(5).max()  - df['Low'].rolling(5).min())  / df['Close']

    # VCP Contraction Condition: True Volatility Shrinkage
    df['Is_VCP'] = (df['Range_20'] > df['Range_10']) & (df['Range_10'] > df['Range_5'])

    # 3. CE / PE Option Sentiment Buildup
    df['Price_Change'] = df['Close'].pct_change()
    
    # Resistance & Support Levels for Breakout Check
    df['Resistance_20'] = df['High'].rolling(20).max().shift(1)
    df['Support_20']    = df['Low'].rolling(20).min().shift(1)

    return df

def get_google_sheet():
    """Authenticates with GCP Credentials and opens the Google Sheet."""
    gcp_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    sheet_id = os.environ.get("SHEET_ID")

    if not gcp_json_str or not sheet_id:
        raise ValueError("❌ Missing GCP_CREDENTIALS_JSON or SHEET_ID environment variables!")

    creds_dict = json.loads(gcp_json_str)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(sheet_id).sheet1
    return sheet

# ==========================================
# 3. MAIN EXECUTION RUNNER
# ==========================================
def main():
    print("🚀 Starting Pure OI-VCP Scanner Engine...")

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")
    print(f"🕒 Timestamp: {now_ist}")

    print("📥 Batch Downloading F&O Market Data...")
    data = yf.download(
        tickers=TICKERS,
        period="1y",
        interval="1d",
        group_by="ticker",
        threads=True,
        progress=False
    )

    output_rows = []

    for symbol in TICKERS:
        try:
            df = data[symbol].dropna() if len(TICKERS) > 1 else data.dropna()

            if df.empty or len(df) < 50:
                continue

            df = calculate_pure_oi_vcp(df)

            latest = df.iloc[-1]
            prev = df.iloc[-2]

            close_price = round(float(latest['Close']), 2)
            pct_change = round(float(((latest['Close'] - prev['Close']) / prev['Close']) * 100), 2)

            is_vcp = "YES 🔥" if latest['Is_VCP'] else "NO"
            
            # Volume Condition
            if latest['Vol_Spike']:
                vol_status = "SPIKE ⚡"
            elif latest['Vol_DryUp']:
                vol_status = "DRY-UP 💧"
            else:
                vol_status = "NORMAL"

            # Options CE / PE Sentiment Determination
            if latest['Price_Change'] > 0 and latest['Vol_Spike']:
                option_sentiment = "CE LONG BUILDUP 🔥"
            elif latest['Price_Change'] < 0 and latest['Vol_Spike']:
                option_sentiment = "PE LONG BUILDUP 📉"
            elif latest['Price_Change'] > 0 and latest['Vol_DryUp']:
                option_sentiment = "CE SHORT COVERING ⚡"
            elif latest['Price_Change'] < 0 and latest['Vol_DryUp']:
                option_sentiment = "PE UNWINDING 💧"
            else:
                option_sentiment = "NEUTRAL ↔️"

            # Breakout Detection against 20-day High/Low
            is_resistance_break = close_price >= latest['Resistance_20']
            is_support_break    = close_price <= latest['Support_20']

            # --- PURE OI-VCP MASTER SIGNAL LOGIC ---
            if latest['Is_VCP'] and is_resistance_break and latest['Vol_Spike']:
                master_signal = "ALPHA VCP CE B/O 🚀🔥"
            elif latest['Is_VCP'] and is_support_break and latest['Vol_Spike']:
                master_signal = "ALPHA VCP PE B/O 📉💥"
            elif latest['Is_VCP'] and latest['Vol_DryUp']:
                master_signal = "VCP SQUEEZE (READY) 💥"
            elif is_resistance_break and latest['Vol_Spike']:
                master_signal = "CE BREAKOUT 🚀"
            elif is_support_break and latest['Vol_Spike']:
                master_signal = "PE BREAKDOWN 📉"
            else:
                master_signal = "WATCHLIST 👁️"

            clean_symbol = symbol.replace(".NS", "")

            output_rows.append([
                clean_symbol,
                close_price,
                f"{pct_change}%",
                is_vcp,
                vol_status,
                option_sentiment,
                master_signal,
                now_ist
            ])

        except Exception as e:
            print(f"⚠️ Error processing {symbol}: {e}")
            continue

    if not output_rows:
        print("❌ No rows processed. Exiting...")
        return

    # Sort Output: Top Alpha VCP Signals First, followed by Highest Gainers
    output_rows.sort(key=lambda x: ("ALPHA" in x[6] or "B/O" in x[6], float(x[2].replace('%', ''))), reverse=True)

    print(f"✅ Processed {len(output_rows)} Stocks Successfully.")

    # ==========================================
    # 4. UPDATE GOOGLE SHEET
    # ==========================================
    print("📊 Updating Google Sheet with Pure OI-VCP Data...")
    sheet = get_google_sheet()

    headers = [
        "Stock Symbol", "LTP", "% Change", 
        "VCP Contraction", "Volume Status", "CE/PE Option Buildup", 
        "Master OI-VCP Signal", "Last Updated"
    ]

    sheet.clear()
    sheet.append_row(headers)
    sheet.append_rows(output_rows)

    print("🎉 Google Sheet Updated with Pure OI-VCP Signals! Boss, Mission Accomplished! 🔥🎯")

if __name__ == "__main__":
    main()
