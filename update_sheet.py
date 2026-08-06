import os
import json
import pytz
import requests
import numpy as np
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ==========================================
# 1. LIQUID F&O & NIFTY 200 TICKERS
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
# 2. OI-VCP CORE CALCULATION ENGINE
# ==========================================
def calculate_oi_vcp_indicators(df):
    """
    OI-VCP Logic:
    - VCP Contraction: High-Low Range narrowing over 20, 10, and 5 periods.
    - Volume Dry-Up: Low volume during consolidation, Spike on Breakout.
    - Simulated Delivery / Institutional OI Build-up indicator via Price-Volume Multiplier.
    """
    df = df.copy()

    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()

    # Volume Averages & Spikes
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df['Vol_Spike'] = df['Volume'] > (1.5 * df['Vol_SMA_20'])
    df['Vol_DryUp'] = df['Volume'] < (0.6 * df['Vol_SMA_20'])

    # VCP Volatility Range Contraction (T1 -> T2 -> T3)
    df['Range_20'] = (df['High'].rolling(20).max() - df['Low'].rolling(20).min()) / df['Close']
    df['Range_10'] = (df['High'].rolling(10).max() - df['Low'].rolling(10).min()) / df['Close']
    df['Range_5']  = (df['High'].rolling(5).max()  - df['Low'].rolling(5).min())  / df['Close']

    # VCP Contraction Score: Tighter range over time means higher score
    df['VCP_Contraction'] = (df['Range_20'] > df['Range_10']) & (df['Range_10'] > df['Range_5'])

    # Simulated OI / Institutional Delivery Momentum Indicator
    df['Price_Change'] = df['Close'].pct_change()
    df['Vol_Change']   = df['Volume'].pct_change()
    
    # Long Buildup = Price Up + Volume Up
    df['OI_Buildup'] = np.where(
        (df['Price_Change'] > 0) & (df['Vol_Spike']), "Long Buildup 🚀",
        np.where((df['Price_Change'] < 0) & (df['Vol_Spike']), "Short Buildup 📉", "Neutral ↔️")
    )

    return df

def get_google_sheet():
    """Authenticates with GCP JSON Credentials and opens the Google Sheet."""
    gcp_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    sheet_id = os.environ.get("SHEET_ID")

    if not gcp_json_str or not sheet_id:
        raise ValueError("❌ Missing GCP_CREDENTIALS_JSON or SHEET_ID environment variable!")

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
# 3. MAIN RUNNER ENGINE
# ==========================================
def main():
    print("🚀 Starting AI-Bro OI-VCP Scanner V8 PRO MAX...")

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")
    print(f"🕒 Execution Timestamp: {now_ist}")

    # Parallel Downloading for High Speed Execution
    print("📥 Fetching Market Data with Parallel Multithreading...")
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

            df = calculate_oi_vcp_indicators(df)

            latest = df.iloc[-1]
            prev = df.iloc[-2]

            close_price = round(float(latest['Close']), 2)
            pct_change = round(float(((latest['Close'] - prev['Close']) / prev['Close']) * 100), 2)

            sma_20 = round(float(latest['SMA_20']), 2) if not np.isnan(latest['SMA_20']) else 0
            sma_50 = round(float(latest['SMA_50']), 2) if not np.isnan(latest['SMA_50']) else 0
            sma_200 = round(float(latest['SMA_200']), 2) if not np.isnan(latest['SMA_200']) else 0

            is_vcp = "YES 🔥" if latest['VCP_Contraction'] else "NO"
            vol_spike = "SPIKE ⚡" if latest['Vol_Spike'] else ("DRY-UP 💧" if latest['Vol_DryUp'] else "NORMAL")
            oi_status = str(latest['OI_Buildup'])

            # --- MASTER OI-VCP SIGNAL LOGIC ---
            signal = "WATCHLIST 👁️"
            if latest['VCP_Contraction'] and latest['Vol_Spike'] and close_price > sma_20 and oi_status == "Long Buildup 🚀":
                signal = "ALPHA VCP BUY 🚀🔥"
            elif latest['VCP_Contraction'] and latest['Vol_DryUp']:
                signal = "VCP SQUEEZE 💥"
            elif close_price > sma_20 and close_price > sma_50:
                signal = "BULLISH TREND 📈"
            elif close_price < sma_20 and close_price < sma_200:
                signal = "BEARISH TREND 📉"

            clean_symbol = symbol.replace(".NS", "")

            output_rows.append([
                clean_symbol,
                close_price,
                f"{pct_change}%",
                is_vcp,
                vol_spike,
                oi_status,
                signal,
                sma_20,
                sma_50,
                sma_200,
                now_ist
            ])

        except Exception as e:
            print(f"⚠️ Skipping {symbol} due to error: {e}")
            continue

    if not output_rows:
        print("❌ No stocks processed. Exiting...")
        return

    # Sort Output by Best VCP Signals First, then Highest Gainers
    output_rows.sort(key=lambda x: (x[6] == "ALPHA VCP BUY 🚀🔥", float(x[2].replace('%', ''))), reverse=True)

    print(f"✅ Successfully Processed {len(output_rows)} F&O / Nifty Stocks.")

    # ==========================================
    # 4. UPDATE GOOGLE SHEET
    # ==========================================
    print("📊 Updating Google Sheet with OI-VCP Data...")
    sheet = get_google_sheet()

    headers = [
        "Stock Symbol", "LTP", "% Change", 
        "VCP Pattern", "Volume Status", "OI Buildup", 
        "Master Signal", "20 DMA", "50 DMA", "200 DMA", "Last Updated"
    ]

    sheet.clear()
    sheet.append_row(headers)
    sheet.append_rows(output_rows)

    print("🎉 OI-VCP Scanner Execution Completed Successfully! 🔥🎯")

if __name__ == "__main__":
    main()
