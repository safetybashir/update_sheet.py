import os
import json
import time
import pytz
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 1. TICKERS CONFIGURATION
# ==========================================
INDEX_TICKER = "^NSEI"

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
    return client.open_by_key(sheet_id).sheet1

def fetch_single_ticker(ticker):
    """Fast single ticker download with error handling."""
    try:
        df = yf.Ticker(ticker).history(period="60d", interval="1d")
        if df is not None and len(df) >= 20:
            return ticker, df
    except Exception:
        pass
    return ticker, None

def fetch_data_parallel(tickers):
    """Downloads all tickers in parallel using threads for maximum speed (10-15s)."""
    all_dfs = {}
    print(f"⚡ Downloading {len(tickers)} tickers in parallel...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_single_ticker, tickers)
        for ticker, df in results:
            if df is not None and not df.empty:
                all_dfs[ticker] = df
    return all_dfs

def process_symbol_data(df, symbol, now_ist):
    """Calculates indicators and prepares clean array for columns A to H."""
    df = df.dropna()
    if len(df) < 25:
        return None

    # 1. Volume Metrics
    df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
    vol_latest = float(df['Volume'].iloc[-1])
    vol_sma = float(df['Vol_SMA20'].iloc[-1])
    
    is_vol_spike = vol_latest > (1.5 * vol_sma)
    is_vol_dryup = vol_latest < (0.6 * vol_sma)

    vol_status = "SPIKE ⚡" if is_vol_spike else ("DRY-UP 💧" if is_vol_dryup else "NORMAL")

    # 2. VCP Shrinkage Engine
    c_price = float(df['Close'].iloc[-1])
    r20 = (df['High'].tail(20).max() - df['Low'].tail(20).min()) / c_price
    r10 = (df['High'].tail(10).max() - df['Low'].tail(10).min()) / c_price
    r5  = (df['High'].tail(5).max()  - df['Low'].tail(5).min())  / c_price

    is_vcp = (r20 > r10) and (r10 > r5)
    vcp_str = "YES 🔥" if is_vcp else "NO"

    # 3. Price Actions & Breakouts
    prev_close = float(df['Close'].iloc[-2])
    pct_change = ((c_price - prev_close) / prev_close) * 100

    res_20 = df['High'].tail(21).iloc[:-1].max()
    sup_20 = df['Low'].tail(21).iloc[:-1].min()

    is_res_break = c_price >= res_20
    is_sup_break = c_price <= sup_20

    # 4. CE/PE Option Buildup
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

    # 8 Elements for Columns A, B, C, D, E, F, G, H
    return [
        str(clean_symbol),
        round(c_price, 2),
        f"{round(pct_change, 2)}%",
        str(vcp_str),
        str(vol_status),
        str(option_buildup),
        str(master_signal),
        str(now_ist)
    ]

# ==========================================
# 2. MAIN EXECUTION
# ==========================================
def main():
    start_time = time.time()
    print("🚀 Starting Fast Scanner Engine...")

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")

    # Fast Multi-threaded Data Download
    data_dict = fetch_data_parallel(ALL_TICKERS)

    nifty_row = None
    stock_rows = []

    for symbol, df in data_dict.items():
        try:
            row = process_symbol_data(df, symbol, now_ist)
            if not row:
                continue

            if symbol == INDEX_TICKER:
                nifty_row = row
            else:
                stock_rows.append(row)

        except Exception as e:
            continue

    # Priority Sorting for Stocks
    stock_rows.sort(key=lambda x: ("ALPHA" in x[6] or "B/O" in x[6], float(x[2].replace('%', ''))), reverse=True)

    # 📌 EXACT HEADERS FOR ROW 1 (A1 to H1)
    headers = [
        "Stock Symbol", 
        "LTP", 
        "% Change", 
        "VCP Contraction", 
        "Volume Status", 
        "CE/PE Option Buildup", 
        "Master OI-VCP Signal", 
        "Last Updated"
    ]

    # Combine Matrix: Row 1 = Headers, Row 2 = Nifty 50, Row 3+ = Stocks
    final_matrix = [headers]
    if nifty_row:
        final_matrix.append(nifty_row)
    final_matrix.extend(stock_rows)

    # Update Sheet explicitly by cell range A1 to H{N}
    print("📊 Updating Google Sheet with 2D Columns...")
    sheet = get_google_sheet()
    
    # 1. Clear old content
    sheet.clear()

    # 2. Update with exact user_entered format so columns split properly
    end_row = len(final_matrix)
    range_to_update = f"A1:H{end_row}"
    
    sheet.update(
        range_name=range_to_update, 
        values=final_matrix, 
        value_input_option='USER_ENTERED'
    )

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 SUCCESS! Google Sheet updated in {elapsed} Seconds! 🔥🚀")

if __name__ == "__main__":
    main()
