import os
import json
import time
import pytz
import requests
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 1. CONFIGURATION & TICKER LIST
# ==========================================
TARGET_SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg"

INDEX_TICKER = "^NSEI"
RAW_FNO_STOCKS = [
    "TORNTPHARM", "ASHOKLEY", "KAYNES", "INOXWIND", "GAIL", "KEI", "PREMIERENE", 
    "CGPOWER", "M&M", "BSE", "DIVISLAB", "MOTHERSON", "POWERINDIA", "GLENMARK", 
    "MAZDOCK", "DELHIVERY", "GVT&D", "TVSMOTOR", "POLYCAB", "TIINDIA", "SIEMENS", 
    "CUMMINSIND", "JSWENERGY", "ANGELONE", "COCHINSHIP", "WAAREEENER", "LAURUSLABS", 
    "MOTILALOFS", "BHARATFORG", "TMPV", "INDIAMART", "TATASTEEL", "LTF", "FORCEMOT", 
    "PRESTIGE", "BPCL", "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", "NBCC", "DMART", 
    "HEROMOTOCO", "KPITTECH", "RVNL", "RELIANCE", "PNB", "ZYDUSLIFE", "BHEL", 
    "NATIONALUM", "NHPC", "SRF", "JINDALSTEL", "BAJAJ-AUTO", "BEL", "TITAN", 
    "SONACOMS", "HINDZINC", "UNOMINDA", "OBEROIRLTY", "BHARTIARTL", "OFSS", "BDL", 
    "SUPREMEIND", "OIL", "SHREECEM", "NTPC", "TATAELXSI", "HINDALCO", "PETRONET", 
    "CIPLA", "MARUTI", "PAYTM", "PERSISTENT", "AMBER", "DLF", "DALBHARAT", 
    "ULTRACEMCO", "ONGC", "PHOENIXLTD", "HINDPETRO", "CAMS", "AUROPHARMA", "BIOCON", 
    "TRENT", "DRREDDY", "JSWSTEEL", "NMDC", "IOC", "UPL", "NYKAA", "LT", 
    "CROMPTON", "INDUSTOWER", "HAVELLS", "CONCOR", "SAIL", "JUBLFOOD", "GRASIM", 
    "PFC", "ASIANPAINT", "LUPIN", "CDSL", "IREDA", "HINDUNILVR", "GODREJPROP", 
    "KFINTECH", "AMBUJACEM", "APOLLOHOSP", "HCLTECH", "POWERGRID", "RECLTD", 
    "GODREJCP", "FORTIS", "PGHL", "COALINDIA", "SUNPHARMA", "MPHASIS", 
    "PIIND", "COLPAL", "BLUESTARCO", "VOLTAS", "TECHM", "EICHERMOT", 
    "INDIGO", "DABUR", "NESTLEIND", "TATACONSUM", "BOSCHLTD", "VEDL", "PIDILITIND", 
    "NAUKRI", "WIPRO", "ALKEM", "ITC", "COFORGE", "MARICO", "PAGEIND", 
    "MAXHEALTH", "BRITANNIA", "INFY", "TCS", "KALYANKJIL", "LODHA", 
    "SWIGGY", "MANKIND", "DIXON", "APLAPOLLO", "ASTRAL"
]
RAW_FNO_STOCKS = list(dict.fromkeys(RAW_FNO_STOCKS))
STOCKS_TICKERS = [f"{stock}.NS" for stock in RAW_FNO_STOCKS]
ALL_TICKERS = [INDEX_TICKER] + STOCKS_TICKERS

# ==========================================
# GOOGLE SHEET CONNECTOR
# ==========================================
def get_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    gcp_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    sheet_id = os.environ.get("SHEET_ID") or TARGET_SHEET_ID

    if gcp_json_str:
        creds_dict = json.loads(gcp_json_str)
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client.open_by_key(sheet_id).sheet1
    elif os.path.exists("credentials.json"):
        credentials = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        client = gspread.authorize(credentials)
        return client.open_by_key(sheet_id).sheet1
    else:
        raise ValueError("❌ Neither GCP_CREDENTIALS_JSON secret nor credentials.json file found!")

# ==========================================
# 2. LIVE NSE OPEN INTEREST (OI) FETCH ENGINE
# ==========================================
def fetch_nse_oi_data_bulk():
    print("📡 Fetching Live OI Data from NSE...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://www.nseindia.com/'
    }
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        session.get("https://www.nseindia.com", timeout=3)
    except Exception:
        pass

    oi_dict = {}
    def fetch_single_oi(symbol):
        url = f"https://www.nseindia.com/api/quote-derivative?symbol={symbol}"
        try:
            resp = session.get(url, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                stocks_data = data.get('stocks', [])
                if stocks_data:
                    fut_info = stocks_data[0]['marketDeptOrderBook']['tradeInfo']
                    p_change_oi = float(fut_info.get('pchangeinOpenInterest', 0.0))
                    return symbol, round(p_change_oi, 2)
        except Exception:
            pass
        return symbol, None

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(fetch_single_oi, RAW_FNO_STOCKS)
        for symbol, oi_pct in results:
            oi_dict[symbol] = oi_pct
    return oi_dict

# ==========================================
# 3. PARALLEL YFINANCE FETCHING
# ==========================================
def fetch_single_ticker(ticker):
    try:
        t = yf.Ticker(ticker)
        df_daily = t.history(period="60d", interval="1d")
        df_15m = t.history(period="2d", interval="15m")
        if df_daily is not None and not df_daily.empty and len(df_daily) >= 20:
            return ticker, df_daily, df_15m
    except Exception:
        pass
    return ticker, None, None

def fetch_data_parallel(tickers):
    all_data = {}
    print(f"⚡ Parallel fetching {len(tickers)} FnO tickers...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_single_ticker, tickers)
        for ticker, df_daily, df_15m in results:
            if df_daily is not None and not df_daily.empty:
                all_data[ticker] = {"daily": df_daily, "intraday": df_15m}
    return all_data

# ==========================================
# 4. PROCESS SYMBOL DATA
# ==========================================
def process_symbol_data(data, symbol, time_only_ist, live_oi_pct):
    df = data["daily"].dropna().copy()
    df_15m = data["intraday"]
    if len(df) < 20:
        return None

    # Volume Metrics
    df.loc[:, 'Vol_SMA20'] = df['Volume'].rolling(20).mean()
    vol_latest = float(df['Volume'].iloc[-1])
    vol_sma_val = float(df['Vol_SMA20'].iloc[-1])
    vol_sma = vol_sma_val if vol_sma_val > 0 else 1.0
    
    is_vol_spike = vol_latest > (1.5 * vol_sma)
    is_vol_dryup = vol_latest < (0.6 * vol_sma)
    vol_status = "SPIKE ⚡" if is_vol_spike else ("DRY-UP 💧" if is_vol_dryup else "NORMAL")

    # VCP Shrinkage Engine
    c_price = float(df['Close'].iloc[-1])
    r20 = (df['High'].tail(20).max() - df['Low'].tail(20).min()) / c_price
    r10 = (df['High'].tail(10).max() - df['Low'].tail(10).min()) / c_price
    r5  = (df['High'].tail(5).max()  - df['Low'].tail(5).min())  / c_price
    is_vcp = (r20 > r10) and (r10 > r5)
    vcp_str = "YES 🔥" if is_vcp else "NO"

    # Price Actions & Support Calculations
    prev_close = float(df['Close'].iloc[-2]) if len(df) >= 2 else c_price
    pct_change = ((c_price - prev_close) / prev_close) * 100
    res_20 = df['High'].tail(21).iloc[:-1].max()
    sup_20 = df['Low'].tail(21).iloc[:-1].min()
    is_res_break = c_price >= res_20
    is_sup_break = c_price <= sup_20
    df.loc[:, 'EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    ema20_val = round(float(df['EMA20'].iloc[-1]), 2)

    # OI Change Logic
    if live_oi_pct is not None and live_oi_pct != 0.0:
        oi_change_str = f"{'+' if live_oi_pct > 0 else ''}{live_oi_pct}%"
        oi_val_for_buildup = live_oi_pct
    else:
        vol_ratio = vol_latest / vol_sma
        est_oi = round(pct_change * vol_ratio * 1.2, 2)
        oi_change_str = f"{'+' if est_oi > 0 else ''}{est_oi}%"
        oi_val_for_buildup = est_oi

    # CE/PE Buildup Signal Logic
    if pct_change > 0 and oi_val_for_buildup > 0:
        option_buildup = "CE LONG BUILDUP 🔥"
    elif pct_change < 0 and oi_val_for_buildup > 0:
        option_buildup = "PE LONG BUILDUP 📉"
    elif pct_change > 0 and oi_val_for_buildup < 0:
        option_buildup = "CE SHORT COVERING ⚡"
    elif pct_change < 0 and oi_val_for_buildup < 0:
        option_buildup = "PE UNWINDING 💧"
    else:
        option_buildup = "NEUTRAL ↔️"

    # 15-Minute & Intraday VWAP Calculation Engine
    is_15m_high_broken = False
    is_15m_low_broken = False
    intraday_trend = "NEUTRAL ↔️"

    if df_15m is not None and not df_15m.empty:
        today_date = df_15m.index[-1].date()
        today_candles = df_15m[df_15m.index.date == today_date].copy()
        
        if len(today_candles) >= 1:
            first_15m_high = today_candles['High'].iloc[0]
            first_15m_low = today_candles['Low'].iloc[0]
            
            if c_price > first_15m_high:
                is_15m_high_broken = True
            elif c_price < first_15m_low:
                is_15m_low_broken = True

            # VWAP Calculation: Cumulative (Typical Price * Volume) / Cumulative Volume
            today_candles['TP'] = (today_candles['High'] + today_candles['Low'] + today_candles['Close']) / 3.0
            today_candles['TPV'] = today_candles['TP'] * today_candles['Volume']
            cum_tpv = today_candles['TPV'].sum()
            cum_vol = today_candles['Volume'].sum()
            
            vwap = cum_tpv / cum_vol if cum_vol > 0 else c_price

            # Trend determination (+ve vs -ve)
            if c_price > vwap and is_15m_high_broken:
                intraday_trend = "STRONG BULLISH (+ve) 🚀🟢"
            elif c_price > vwap:
                intraday_trend = "ABOVE VWAP (+ve) 🟢"
            elif c_price < vwap and is_15m_low_broken:
                intraday_trend = "STRONG BEARISH (-ve) 💥🔴"
            else:
                intraday_trend = "BELOW VWAP (-ve) 🔴"

    # Breakout Status & Entry Triggers
    if symbol == INDEX_TICKER:
        vcp_str = "N/A"
        clean_symbol = "NIFTY 50 🎯"
        bo_status = "INDEX TREND"
        action_entry = "MARKET REGIME: " + ("BULLISH 📈" if pct_change > 0 else "BEARISH 📉")
        support_level = "N/A"
        priority_group = 0
        option_buildup = "N/A"
        oi_change_str = "N/A"
        intraday_trend = "INDEX REGIME"
    else:
        clean_symbol = symbol.replace(".NS", "")
        support_level = f"EMA20: ₹{ema20_val}"
        
        if is_vcp and is_res_break and is_vol_spike:
            bo_status = "ALPHA CE B/O 🚀🔥"
            priority_group = 1
            action_entry = "BUY CE (15M CONFIRMED) 🟢" if is_15m_high_broken else "WAIT FOR 15M BREAKOUT ⏳"
        elif is_vcp and is_sup_break and is_vol_spike:
            bo_status = "ALPHA PE B/O 📉💥"
            priority_group = 1
            action_entry = "BUY PE (15M CONFIRMED) 🔴" if is_15m_low_broken else "WAIT FOR 15M BREAKDOWN ⏳"
        elif is_res_break and is_vol_spike:
            bo_status = "CE BREAKOUT 🚀"
            priority_group = 1
            action_entry = "BUY CE ON REVERSAL 🟢"
        elif is_sup_break and is_vol_spike:
            bo_status = "PE BREAKDOWN 📉"
            priority_group = 1
            action_entry = "BUY PE ON REVERSAL 🔴"
        elif is_vcp and is_vol_dryup:
            bo_status = "VCP SQUEEZE 💥"
            action_entry = "READY FOR B/O (WATCH) 👁️"
            priority_group = 2
        else:
            bo_status = "NONE"
            action_entry = "NO ENTRY (WAIT) ⏳"
            support_level = "-"
            priority_group = 3

    return {
        "clean_symbol": clean_symbol,
        "c_price": round(c_price, 2),
        "pct_change_num": pct_change,
        "pct_change_str": f"{round(pct_change, 2)}%",
        "oi_change_str": oi_change_str,
        "vcp_str": vcp_str,
        "vol_status": vol_status,
        "option_buildup": option_buildup,
        "bo_status": bo_status,
        "action_entry": action_entry,
        "support_level": support_level,
        "priority_group": priority_group,
        "intraday_trend": intraday_trend,
        "time_only_ist": time_only_ist
    }

# ==========================================
# 5. MAIN EXECUTION ROUTINE
# ==========================================
def run_scanner_once():
    start_time = time.time()
    ist = pytz.timezone('Asia/Kolkata')
    time_only_ist = datetime.now(ist).strftime("%H:%M:%S")

    nse_oi_dict = fetch_nse_oi_data_bulk()
    data_dict = fetch_data_parallel(ALL_TICKERS)

    nifty_row = None
    stock_data_list = []

    for symbol, data in data_dict.items():
        try:
            clean_sym = symbol.replace(".NS", "")
            live_oi_pct = nse_oi_dict.get(clean_sym, None)
            pdata = process_symbol_data(data, symbol, time_only_ist, live_oi_pct)
            if not pdata:
                continue
            if symbol == INDEX_TICKER:
                nifty_row = [
                    pdata["clean_symbol"], pdata["c_price"], pdata["pct_change_str"],
                    pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                    pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                    "BENCHMARK", pdata["support_level"], pdata["time_only_ist"],
                    pdata["intraday_trend"]
                ]
            else:
                stock_data_list.append(pdata)
        except Exception:
            continue

    stock_data_list.sort(key=lambda x: (x["priority_group"], -x["pct_change_num"]))

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
            item["clean_symbol"],
            item["c_price"],
            item["pct_change_str"],
            item["oi_change_str"],
            item["vcp_str"],
            item["vol_status"],
            item["option_buildup"],
            item["bo_status"],
            item["action_entry"],
            rank_tag,
            item["support_level"],
            item["time_only_ist"],
            item["intraday_trend"]
        ])

    headers = [
        "Stock Symbol", "LTP", "Price % Change", "OI % Change 📊", 
        "VCP Contraction", "Volume Status", "CE/PE Option Buildup", 
        "Breakout Status", "Action / Entry Trigger", "Priority Rank", 
        "Reversal Support Level", "Last Updated", "Intraday Trend (VWAP / 15M)"
    ]

    final_matrix = [headers]
    if nifty_row:
        final_matrix.append(nifty_row)
    final_matrix.extend(stock_rows)

    sheet = get_google_sheet()
    end_row = len(final_matrix)
    range_to_update = f"A1:M{end_row}"

    try:
        sheet.update(range_name=range_to_update, values=final_matrix, value_input_option='USER_ENTERED')
    except TypeError:
        sheet.update(range_to_update, final_matrix)

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 SUCCESS! Sheet updated successfully at {time_only_ist} IST in {elapsed}s!")

if __name__ == "__main__":
    run_scanner_once()
