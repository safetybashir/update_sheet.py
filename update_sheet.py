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
# 1. TICKERS CONFIGURATION
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

STOCKS_TICKERS = [f"{stock}.NS" for stock in RAW_FNO_STOCKS]
ALL_TICKERS = [INDEX_TICKER] + STOCKS_TICKERS

# ==========================================
# 2. GOOGLE SHEETS CONNECTION
# ==========================================
def get_google_sheet():
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

# ==========================================
# 3. LIVE NSE OPEN INTEREST FETCH ENGINE
# ==========================================
def fetch_nse_oi_data_bulk():
    print("📡 Fetching Live OI % Change from NSE India...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/get-quotes/derivatives?symbol=RELIANCE'
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        session.get("https://www.nseindia.com", timeout=5)
    except Exception:
        pass

    oi_dict = {}

    def fetch_single_oi(symbol):
        url = f"https://www.nseindia.com/api/quote-derivative?symbol={symbol}"
        try:
            resp = session.get(url, timeout=4)
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

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(fetch_single_oi, RAW_FNO_STOCKS)
        for symbol, oi_pct in results:
            oi_dict[symbol] = oi_pct

    return oi_dict

# ==========================================
# 4. YFINANCE PARALLEL FETCHING ENGINE
# ==========================================
def fetch_single_ticker(ticker):
    try:
        df_daily = yf.Ticker(ticker).history(period="60d", interval="1d")
        df_15m = yf.Ticker(ticker).history(period="2d", interval="15m")
        
        if df_daily is not None and len(df_daily) >= 20:
            return ticker, df_daily, df_15m
    except Exception:
        pass
    return ticker, None, None

def fetch_data_parallel(tickers):
    all_data = {}
    print(f"⚡ Parallel fetching {len(tickers)} FnO tickers...")
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(fetch_single_ticker, tickers)
        for ticker, df_daily, df_15m in results:
            if df_daily is not None and not df_daily.empty:
                all_data[ticker] = {"daily": df_daily, "intraday": df_15m}
    return all_data

# ==========================================
# 5. DATA PROCESSING & SIGNAL GENERATION
# ==========================================
def process_symbol_data(data, symbol, time_only_ist, live_oi_pct):
    df = data["daily"].dropna()
    df_15m = data["intraday"]

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

    # 3. Moving Averages & Pivot Points
    prev_close = float(df['Close'].iloc[-2])
    prev_high = float(df['High'].iloc[-2])
    prev_low = float(df['Low'].iloc[-2])
    pct_change = ((c_price - prev_close) / prev_close) * 100

    pivot_point = (prev_high + prev_low + prev_close) / 3.0

    res_20 = df['High'].tail(21).iloc[:-1].max()
    sup_20 = df['Low'].tail(21).iloc[:-1].min()

    is_res_break = c_price >= res_20
    is_sup_break = c_price <= sup_20

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    ema20_val = round(float(df['EMA20'].iloc[-1]), 2)
    ema21_val = float(df['EMA21'].iloc[-1])

    # 4. Intraday VWAP Engine
    vwap_val = c_price
    if df_15m is not None and not df_15m.empty:
        today_date = df_15m.index[-1].date()
        today_candles = df_15m[df_15m.index.date == today_date].copy()
        if not today_candles.empty:
            typical_price = (today_candles['High'] + today_candles['Low'] + today_candles['Close']) / 3
            cum_tp_vol = (typical_price * today_candles['Volume']).cumsum()
            cum_vol = today_candles['Volume'].cumsum()
            vwap_series = cum_tp_vol / cum_vol
            vwap_val = float(vwap_series.iloc[-1])

    # 5. OI Change Logic (STRICT CHECK - NO FAKE ESTIMATE)
    if live_oi_pct is not None:
        oi_change_str = f"{'+' if live_oi_pct > 0 else ''}{live_oi_pct}%"
        oi_val_for_buildup = live_oi_pct
    else:
        oi_change_str = "0.0%"
        oi_val_for_buildup = 0.0

    # 6. Option Buildup Logic
    if oi_val_for_buildup != 0.0:
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
    else:
        option_buildup = "VOLUME BASED (NO OI) ⚠️"

    # 7. 15-Minute Confirmation
    is_15m_high_broken = False
    is_15m_low_broken = False

    if df_15m is not None and not df_15m.empty:
        today_date = df_15m.index[-1].date()
        today_candles = df_15m[df_15m.index.date == today_date]
        
        if len(today_candles) >= 1:
            first_15m_high = today_candles['High'].iloc[0]
            first_15m_low = today_candles['Low'].iloc[0]

            if c_price > first_15m_high:
                is_15m_high_broken = True
            elif c_price < first_15m_low:
                is_15m_low_broken = True

    # 8. Breakout Status & Priority Group Separation
    # Group 1 = Bullish Breakout, Group 2 = Bearish Breakdown, Group 3 = VCP Ready, Group 4 = Neutral
    if symbol == INDEX_TICKER:
        vcp_str = "N/A"
        clean_symbol = "NIFTY 50 🎯"
        bo_status = "INDEX TREND"
        action_entry = "MARKET REGIME: " + ("BULLISH 📈" if pct_change > 0 else "BEARISH 📉")
        support_level = "N/A"
        priority_group = 0
        option_buildup = "N/A"
        oi_change_str = "N/A"
    else:
        clean_symbol = symbol.replace(".NS", "")
        support_level = f"EMA20: ₹{ema20_val}"
        
        if is_vcp and is_res_break and is_vol_spike:
            bo_status = "ALPHA CE B/O 🚀🔥"
            priority_group = 1
            action_entry = "BUY CE (15M CONFIRMED) 🟢" if is_15m_high_broken else "WAIT FOR 15M BREAKOUT ⏳"

        elif is_vcp and is_sup_break and is_vol_spike:
            bo_status = "ALPHA PE B/O 📉💥"
            priority_group = 2  # Separated Bearish Rank
            action_entry = "BUY PE (15M CONFIRMED) 🔴" if is_15m_low_broken else "WAIT FOR 15M BREAKDOWN ⏳"

        elif is_res_break and is_vol_spike:
            bo_status = "CE BREAKOUT 🚀"
            priority_group = 1
            action_entry = "BUY CE ON REVERSAL 🟢"

        elif is_sup_break and is_vol_spike:
            bo_status = "PE BREAKDOWN 📉"
            priority_group = 2  # Separated Bearish Rank
            action_entry = "BUY PE ON REVERSAL 🔴"

        elif is_vcp and is_vol_dryup:
            bo_status = "VCP SQUEEZE 💥"
            action_entry = "READY FOR B/O (WATCH) 👁️"
            priority_group = 3
        else:
            bo_status = "NONE"
            action_entry = "NO ENTRY (WAIT) ⏳"
            support_level = "-"
            priority_group = 4

    # Trend calculation for strictly locked Column N & O
    if c_price > ema21_val:
        trend_str = "📈 BULLISH"
    elif c_price < ema21_val:
        trend_str = "📉 BEARISH"
    else:
        trend_str = "↔️ SIDEWAYS"

    # Strictly Lock Col M, N, O logic per row
    bo_stock_m_val = clean_symbol if (c_price >= pivot_point and is_vol_spike) else ""
    trend_n_val = trend_str if bo_stock_m_val != "" else ""
    high_mom_o_val = clean_symbol if (bo_stock_m_val != "" and c_price > ema21_val and c_price > vwap_val and trend_str == "📈 BULLISH") else ""

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
        "time_only_ist": time_only_ist,
        "bo_stock_m_val": bo_stock_m_val,
        "trend_n_val": trend_n_val,
        "high_mom_o_val": high_mom_o_val
    }

# ==========================================
# 6. MAIN EXECUTION
# ==========================================
def main():
    start_time = time.time()
    print("🚀 Starting Audited FnO Scanner Engine (Col A to O)...")

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
                    "", "", ""
                ]
            else:
                stock_data_list.append(pdata)

        except Exception:
            continue

    # Sorting logic: Group 1 (Bullish), Group 2 (Bearish), Group 3 (VCP Ready), Group 4 (Rest)
    stock_data_list.sort(key=lambda x: (x["priority_group"], -x["pct_change_num"]))

    final_matrix = []

    # Headers Generation
    headers = [
        "Stock Symbol", "LTP", "Price % Change", "OI % Change 📊", 
        "VCP Contraction", "Volume Status", "CE/PE Option Buildup", 
        "Breakout Status", "Action / Entry Trigger", "Priority Rank", 
        "Reversal Support Level", "Last Updated",
        "B/O STOCKS", "TREND (STOCKS)", "MOMENTUM (EMA21+VWAP)"
    ]
    final_matrix.append(headers)

    if nifty_row:
        final_matrix.append(nifty_row)

    bo_rank = 1
    bd_rank = 1
    ready_rank = 1

    for item in stock_data_list:
        # Corrected Ranks Strategy
        if item["priority_group"] == 1:
            rank_tag = f"B/O #{bo_rank}"
            bo_rank += 1
        elif item["priority_group"] == 2:
            rank_tag = f"B/D #{bd_rank}"
            bd_rank += 1
        elif item["priority_group"] == 3:
            rank_tag = f"READY #{ready_rank}"
            ready_rank += 1
        else:
            rank_tag = "WAIT"

        row = [
            item["clean_symbol"],        # Col A
            item["c_price"],             # Col B
            item["pct_change_str"],      # Col C
            item["oi_change_str"],       # Col D
            item["vcp_str"],             # Col E
            item["vol_status"],          # Col F
            item["option_buildup"],      # Col G
            item["bo_status"],           # Col H
            item["action_entry"],        # Col I
            rank_tag,                    # Col J
            item["support_level"],       # Col K
            item["time_only_ist"],       # Col L
            item["bo_stock_m_val"],      # Col M (Strictly Linked)
            item["trend_n_val"],         # Col N (Strictly Linked)
            item["high_mom_o_val"]       # Col O (Strictly Linked)
        ]
        final_matrix.append(row)

    # Google Sheets Push
    print("📊 Updating Google Sheet Matrix A1:O...")
    sheet = get_google_sheet()
    sheet.clear()

    end_row = len(final_matrix)
    range_to_update = f"A1:O{end_row}"
    
    sheet.update(
        range_name=range_to_update, 
        values=final_matrix, 
        value_input_option='USER_ENTERED'
    )

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 SUCCESS! Sheet fully updated with ZERO Misalignment in {elapsed} Seconds! 🔥🚀")

if __name__ == "__main__":
    main()
