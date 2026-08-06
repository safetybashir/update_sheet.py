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
# 1. TICKERS LIST (NIFTY 50 FIRST + STOCKS)
# ==========================================
INDEX_TICKER = "^NSEI"  # Nifty 50 Index Symbol

STOCKS_TICKERS = [
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

ALL_TICKERS = [INDEX_TICKER] + STOCKS_TICKERS

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

def process_symbol_data(df, symbol, now_ist):
    """Processes DataFrame for a single symbol and returns formatted row."""
    if len(df) < 25:
        return None

    # 1. Volume Metrics
    df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
    vol_latest = df['Volume'].iloc[-1]
    vol_sma = df['Vol_SMA20'].iloc[-1]
    
    is_vol_spike = vol_latest > (1.5 * vol_sma)
    is_vol_dryup = vol_latest < (0.6 * vol_sma)

    vol_status = "SPIKE ⚡" if is_vol_spike else ("DRY-UP 💧" if is_vol_dryup else "NORMAL")

    # 2. VCP Contraction Check
    r20 = (df['High'].tail(20).max() - df['Low'].tail(20).min()) / df['Close'].iloc[-1]
    r10 = (df['High'].tail(10).max() - df['Low'].tail(10).min()) / df['Close'].iloc[-1]
    r5  = (df['High'].tail(5).max()  - df['Low'].tail(5).min())  / df['Close'].iloc[-1]

    is_vcp = (r20 > r10) and (r10 > r5)
    vcp_str = "YES 🔥" if is_vcp else "NO"

    # 3. Price & Breakout Checks
    close_price = float(df['Close'].iloc[-1])
    prev_close  = float(df['Close'].iloc[-2])
    pct_change  = ((close_price - prev_close) / prev_close) * 100

    res_20 = df['High'].tail(21).iloc[:-1].max()
    sup_20 = df['Low'].tail(21).iloc[:-1].min()

    is_res_break = close_price >= res_20
    is_sup_break = close_price <= sup_20

    # 4. CE/PE Option Buildup Mapping
    if pct_change > 0 and is_vol_spike:
        option_buildup = "CE LONG BUILDUP 🔥"
    elif pct_change < 0 and is_vol_spike:
        option_buildup = "PE LONG BUILDUP 📉"
    elif pct_change > 0 and is_vol_dryup:
        option_buildup = "CE SHORT COVERING ⚡"
    elif pct_change < 0 and is_vol_dryup:
        option_buildup = "PE UNWINDING 💧"
    else:
        option_buildup = "NEUTRAL ↔️"

    # 5. Master Signal Logic
    if symbol == INDEX_TICKER:
        vcp_str = "N/A"
        master_signal = "BULLISH TREND 📈" if pct_change > 0 else "BEARISH TREND 📉"
        clean_symbol = "NIFTY 50 🎯"
    else:
        clean_symbol = symbol.replace(".NS", "")
        if is_vcp and is_res_break and is_vol_spike:
            master_signal = "ALPHA VCP CE B/O 🚀🔥"
        elif is_vcp and is_sup_break and is_vol_spike:
            master_signal = "ALPHA VCP PE B/O 📉💥"
        elif is_vcp and is_vol_dryup:
            master_signal = "VCP SQUEEZE (READY) 💥"
        elif is_res_break and is_vol_spike:
            master_signal = "CE BREAKOUT 🚀"
        elif is_sup_break and is_vol_spike:
            master_signal = "PE BREAKDOWN 📉"
        else:
            master_signal = "WATCHLIST 👁️"

    return [
        clean_symbol,
        round(close_price, 2),
        f"{round(pct_change, 2)}%",
        vcp_str,
        vol_status,
        option_buildup,
        master_signal,
        now_ist
    ]

# ==========================================
# 2. MAIN EXECUTION
# ==========================================
def main():
    print("🚀 Starting Fast Scanner with NIFTY 50 Top Row Fix...")

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")

    # Fast Batch Download
    df_raw = yf.download(
        tickers=ALL_TICKERS,
        period="60d",
        interval="1d",
        threads=True,
        progress=False
    )

    nifty_row = None
    stock_rows = []

    for symbol in ALL_TICKERS:
        try:
            if isinstance(df_raw.columns, pd.MultiIndex):
                df = pd.DataFrame({
                    'Open': df_raw['Open'][symbol],
                    'High': df_raw['High'][symbol],
                    'Low': df_raw['Low'][symbol],
                    'Close': df_raw['Close'][symbol],
                    'Volume': df_raw['Volume'][symbol]
                }).dropna()
            else:
                df = df_raw.dropna()

            row = process_symbol_data(df, symbol, now_ist)
            if not row:
                continue

            if symbol == INDEX_TICKER:
                nifty_row = row
            else:
                stock_rows.append(row)

        except Exception as e:
            continue

    # Priority Sort Stocks (Alpha Signals First)
    stock_rows.sort(key=lambda x: ("ALPHA" in x[6] or "B/O" in x[6], float(x[2].replace('%', ''))), reverse=True)

    # Headers definition
    headers = [
        "Stock Symbol", "LTP", "% Change", 
        "VCP Contraction", "Volume Status", "CE/PE Option Buildup", 
        "Master OI-VCP Signal", "Last Updated"
    ]

    # Combine: Headers -> NIFTY 50 (Row 1) -> All Stocks (Row 2 onwards)
    final_matrix = [headers]
    if nifty_row:
        final_matrix.append(nifty_row)
    final_matrix.extend(stock_rows)

    # Bulk Update Sheet
    sheet = get_google_sheet()
    sheet.clear()
    sheet.update('A1', final_matrix)

    print("🎉 Done! NIFTY 50 is at the top with Headers in proper columns! 🔥🚀")

if __name__ == "__main__":
    main()
