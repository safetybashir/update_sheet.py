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
# 1. SELECTED FNO TICKERS CONFIGURATION
# ==========================================
INDEX_TICKER = "^NSEI"

RAW_FNO_STOCKS = [
    "TORNTPHARM", "ASHOKLEY", "KAYNES", "INOXWIND", "GAIL", "KEI", "PREMIERENE", 
    "CGPOWER", "M&M", "BSE", "DIVISLAB", "MOTHERSON", "POWERINDIA", "GLENMARK", 
    "MAZDOCK", "DELHIVERY", "GVT&D", "TVSMOTOR", "POLYCAB", "TIINDIA", "SIEMENS", 
    "CUMMINSIND", "JSWENERGY", "ANGELONE", "COCHINSHIP", "WAAREEENER", "LAURUSLABS", 
    "MOTILALOFS", "BHARATFORG", "TMPVSOLAR", "IND", "TATASTEEL", "LTF", "FORCEMOT", 
    "PRESTIGE", "BPCL", "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", "NBCC", "DMART", 
    "HEROMOTOCO", "KPITTECH", "RVNL", "RELIANCE", "PNB", "ZYDUSLIFE", "BHEL", 
    "NATIONALUM", "NHPC", "SRF", "JINDALSTEL", "BAJAJ-AUTO", "BEL", "TITAN", 
    "SONACOMS", "HINDZINC", "UNOMINDA", "OBEROIRLTY", "BHARTIARTL", "OFSS", "BDL", 
    "SUPREMEIND", "OIL", "SHREECEM", "NTPC", "TATAELXSI", "HINDALCO", "PETRONET", 
    "CIPLA", "MARUTI", "PAYTM", "PERSISTENT", "AMBER", "DLF", "DALBHARAT", 
    "ULTRACEMCO", "ONGC", "PHOENIXLTD", "HINDPETRO", "CAMS", "AUROPHARMA", "BIOCON", 
    "TRENT", "DRREDDY", "JSWSTEEL", "NMDC", "IOC", "UPL", "NYKAA", "LTC", 
    "CROMPTON", "INDUSTOWER", "HAVELLS", "CONCOR", "SAIL", "JUBLFOOD", "GRASIM", 
    "PFC", "ASIANPAINT", "LUPIN", "CDSL", "IREDA", "HINDUNILVR", "GODREJPROP", 
    "KFINTECH", "AMBUJACEM", "APOLLOHOSP", "HCLTECH", "POWERGRID", "RECLTD", 
    "GODREJCP", "FORTIS", "PGELAB", "BCOALINDIA", "SUNPHARMA", "MPHASIS", 
    "PIIND", "COLPAL", "BLUESTARCO", "VMM", "VOLTAS", "TECHM", "EICHERMOT", 
    "INDIGO", "DABUR", "NESTLEIND", "TATACONSUM", "BOSCHLTD", "VEDL", "PIDILITIND", 
    "NAUKRI", "WIPRO", "ALKEM", "ITC", "COFORGE", "ASTRALLTM", "MARICO", "PAGEIND", 
    "MAXHEALTH", "BRITANNIA", "INFY", "ETERNAL", "TCS", "KALYANKJIL", "LODHA", 
    "SWIGGY", "MANKIND", "DIXON", "APLAPOLLO"
]

# Generate NSE compatible tickers (.NS suffix)
STOCKS_TICKERS = [f"{stock}.NS" for stock in RAW_FNO_STOCKS]
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
    """Downloads all tickers in parallel using 15 worker threads."""
    all_dfs = {}
    print(f"⚡ Parallel fetching {len(tickers)} FnO tickers...")
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(fetch_single_ticker, tickers)
        for ticker, df in results:
            if df is not None and not df.empty:
                all_dfs[ticker] = df
    return all_dfs

def process_symbol_data(df, symbol, time_only_ist):
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
            priority_group = 1
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
            priority_group = 2
        else:
            bo_status = "NONE"
            action_entry = "NO ENTRY (WAIT) ⏳"
            priority_group = 3

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
        "time_only_ist": time_only_ist
    }

# ==========================================
# 2. MAIN EXECUTION
# ==========================================
def main():
    start_time = time.time()
    print("🚀 Starting FnO Fast Scanner Engine...")

    ist = pytz.timezone('Asia/Kolkata')
    # ONLY TIME FORMAT (HH:MM:SS) - No Date, No IST text
    time_only_ist = datetime.now(ist).strftime("%H:%M:%S")

    data_dict = fetch_data_parallel(ALL_TICKERS)

    nifty_row = None
    stock_data_list = []

    for symbol, df in data_dict.items():
        try:
            pdata = process_symbol_data(df, symbol, time_only_ist)
            if not pdata:
                continue

            if symbol == INDEX_TICKER:
                nifty_row = [
                    pdata["clean_symbol"], pdata["c_price"], pdata["pct_change_str"],
                    pdata["vcp_str"], pdata["vol_status"], pdata["option_buildup"],
                    pdata["bo_status"], pdata["action_entry"], "BENCHMARK", pdata["time_only_ist"]
                ]
            else:
                stock_data_list.append(pdata)

        except Exception as e:
            continue

    # 🔥 AUTO-SORTING LOGIC
    stock_data_list.sort(key=lambda x: (x["priority_group"], -x["pct_change_num"]))

    # Clean Signal Rank Formatting for Column I
    stock_rows = []
    bo_rank = 1
    ready_rank = 1

    for item in stock_data_list:
        if item["priority_group"] == 1:
            rank_tag = f"B/O #{bo_rank}"
            bo_rank += 1
        elif item["priority_group"] == 2:
            rank_tag = f"READY #{ready_rank}"
            ready_rank += 1
        else:
            rank_tag = "WAIT"

        stock_rows.append([
            item["clean_symbol"],        # Col A
            item["c_price"],             # Col B
            item["pct_change_str"],      # Col C
            item["vcp_str"],             # Col D
            item["vol_status"],          # Col E
            item["option_buildup"],      # Col F
            item["bo_status"],           # Col G
            item["action_entry"],        # Col H
            rank_tag,                    # Col I (B/O #1, READY #1, WAIT)
            item["time_only_ist"]        # Col J (Only HH:MM:SS)
        ])

    # 📌 HEADERS FOR COLUMNS A TO J
    headers = [
        "Stock Symbol", 
        "LTP", 
        "% Change", 
        "VCP Contraction", 
        "Volume Status", 
        "CE/PE Option Buildup", 
        "Breakout Status",
        "Action / Entry Trigger",
        "Priority Rank",
        "Last Updated"
    ]

    final_matrix = [headers]
    if nifty_row:
        final_matrix.append(nifty_row)
    final_matrix.extend(stock_rows)

    # Update Sheet Matrix
    print("📊 Updating Google Sheet Matrix...")
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
    print(f"🎉 SUCCESS! Google Sheet updated in {elapsed} Seconds! 🔥🚀")

if __name__ == "__main__":
    main()
