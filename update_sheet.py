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
    """Fast single ticker download."""
    try:
        df = yf.Ticker(ticker).history(period="60d", interval="1d")
        if df is not None and len(df) >= 20:
            return ticker, df
    except Exception:
        pass
    return ticker, None

def fetch_data_parallel(tickers):
    """Downloads all tickers in parallel using 10 worker threads."""
    all_dfs = {}
    print(f"⚡ Parallel fetching {len(tickers)} tickers...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_single_ticker, tickers)
        for ticker, df in results:
            if df is not None and not df.empty:
                all_dfs[ticker] = df
    return all_dfs

def process_symbol_data(df, symbol, now_ist):
    """Calculates indicators and prepares stock metrics."""
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

    # 5. Breakout Status & Action Entry Condition
    if symbol == INDEX_TICKER:
        vcp_str = "N/A"
        clean_symbol = "NIFTY 50 🎯"
        bo_status = "INDEX TREND"
        action_entry = "MARKET REGIME: " + ("BULLISH 📈" if pct_change > 0 else "BEARISH 📉")
        priority_group = 0
    else:
        clean_symbol = symbol.replace(".NS", "")
        
        if is_vcp and is_res_break and is_vol_spike:
            bo_status = "ALPHA CE B/O 🚀🔥"
            action_entry = "BUY CE ABOVE 15M HIGH 🟢"
            priority_group = 1 # Top Priority Breakout
        elif is_vcp and is_sup_break and is_vol_spike:
            bo_status = "ALPHA PE B/O 📉💥"
            action_entry = "BUY PE BELOW 15M LOW 🔴"
            priority_group = 1
        elif is_res_break and is_vol_spike:
            bo_status = "CE BREAKOUT 🚀"
            action_entry = "BUY CE ON PULLBACK 🟢"
            priority_group = 1
        elif is_sup_break and is_vol_spike:
            bo_status = "PE BREAKDOWN 📉"
            action_entry = "BUY PE ON PULLBACK 🔴"
            priority_group = 1
        elif is_vcp and is_vol_dryup:
            bo_status = "VCP SQUEEZE 💥"
            action_entry = "READY FOR B/O (WATCH) 👁️"
            priority_group = 2 # High Probability Watchlist
        else:
            bo_status = "NONE"
            action_entry = "NO ENTRY (WAIT) ⏳"
            priority_group = 3 # Normal / Wait List

    return {
        "clean_symbol": clean_symbol,
        "c_price": round(c_price, 2),
        "pct_change_num": pct_change,
        "pct_change_str": f"{round(pct_change, 2)}%",
        "vcp_str": vcp_str,
        "vol_status": vol_status,
        "option_buildup": option_buildup,
        "bo_status": bo_status,
        "action_entry": action_entry,
        "priority_group": priority_group,
        "now_ist": now_ist
    }

# ==========================================
# 2. MAIN EXECUTION
# ==========================================
def main():
    start_time = time.time()
    print("🚀 Starting Fast Scanner Engine (Clean Alignment)...")

    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")

    data_dict = fetch_data_parallel(ALL_TICKERS)

    nifty_row = None
    stock_data_list = []

    for symbol, df in data_dict.items():
        try:
            pdata = process_symbol_data(df, symbol, now_ist)
            if not pdata:
                continue

            if symbol == INDEX_TICKER:
                nifty_row = [
                    pdata["clean_symbol"], pdata["c_price"], pdata["pct_change_str"],
                    pdata["vcp_str"], pdata["vol_status"], pdata["option_buildup"],
                    pdata["bo_status"], pdata["action_entry"], "BENCHMARK INDEX", pdata["now_ist"]
                ]
            else:
                stock_data_list.append(pdata)

        except Exception as e:
            continue

    # 🔥 AUTO-SORTING LOGIC:
    # 1. Breakouts First (priority_group = 1)
    # 2. High Probability / Squeeze Second (priority_group = 2)
    # 3. Normal / Wait List Third (priority_group = 3)
    # Within each group, sort by % Change (Highest Momentum)
    stock_data_list.sort(key=lambda x: (x["priority_group"], -x["pct_change_num"]))

    # Add Rank/Category Tag at Column I (End of row before timestamp)
    stock_rows = []
    bo_rank = 1
    watch_rank = 1

    for item in stock_data_list:
        if item["priority_group"] == 1:
            rank_tag = f"B/O Rank #{bo_rank} 🔥"
            bo_rank += 1
        elif item["priority_group"] == 2:
            rank_tag = f"Ready Rank #{watch_rank} 👁️"
            watch_rank += 1
        else:
            rank_tag = "Watchlist ⏳"

        stock_rows.append([
            item["clean_symbol"],        # Col A
            item["c_price"],             # Col B (LTP Fix)
            item["pct_change_str"],      # Col C (% Change)
            item["vcp_str"],             # Col D
            item["vol_status"],          # Col E
            item["option_buildup"],      # Col F
            item["bo_status"],           # Col G
            item["action_entry"],        # Col H
            rank_tag,                    # Col I (Rank Tag Added Here!)
            item["now_ist"]              # Col J (Timestamp)
        ])

    # 📌 CLEAN HEADERS (Columns A to J)
    headers = [
        "Stock Symbol", 
        "LTP", 
        "% Change", 
        "VCP Contraction", 
        "Volume Status", 
        "CE/PE Option Buildup", 
        "Breakout Status",
        "Action / Entry Trigger",
        "Priority Tag",
        "Last Updated"
    ]

    final_matrix = [headers]
    if nifty_row:
        final_matrix.append(nifty_row)
    final_matrix.extend(stock_rows)

    # Update Sheet Matrix
    print("📊 Updating Google Sheet Matrix with Clean Columns...")
    sheet = get_google_sheet()
    sheet.clear()

    end_row = len(final_matrix)
    range_to_update = f"A1:J{end_row}"
    
    sheet.update(
        range_name=range_to_update, 
        values=final_matrix, 
        value_input_option='USER_ENTERED'
    )

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 SUCCESS! Google Sheet updated with perfect column alignment in {elapsed} Seconds! 🔥🚀")

if __name__ == "__main__":
    main()
