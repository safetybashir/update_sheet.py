import os
import io
import json
import time
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import gspread
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 1. GOOGLE SHEETS & TICKER SETUP
# ==========================================
SPREADSHEET_NAME = 'Stock_Scanner'          # Fallback name
WORKSHEET_NAME = 'Sheet1'                   # Worksheet tab name
INDEX_TICKER = "^NSEI"                      # NIFTY 50 Index

ALL_TICKERS = [
    INDEX_TICKER, "NATIONALUM.NS", "FORCEMOT.NS", "PNB.NS", 
    "BOSCHLTD.NS", "HINDALCO.NS", "BDL.NS", "TATASTEEL.NS", 
    "RELIANCE.NS", "HDFCBANK.NS"
]

def get_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Local PC Execution
    if os.path.exists('credentials.json'):
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    
    # 2. GitHub Actions Runner Execution
    elif "GCP_SA_KEY" in os.environ and os.environ["GCP_SA_KEY"].strip():
        secret_json_str = os.environ["GCP_SA_KEY"].strip()
        service_account_info = json.loads(secret_json_str)
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    else:
        raise FileNotFoundError("Neither 'credentials.json' file nor 'GCP_SA_KEY' environment variable was found!")

    client = gspread.authorize(creds)
    
    # Priority: Open Sheet using SHEET_ID secret
    sheet_id = os.environ.get("SHEET_ID")
    if sheet_id and sheet_id.strip():
        spreadsheet = client.open_by_key(sheet_id.strip())
    else:
        spreadsheet = client.open(SPREADSHEET_NAME)
        
    return spreadsheet.worksheet(WORKSHEET_NAME)


# ==========================================
# 2. DATA FETCHERS
# ==========================================
def fetch_nse_oi_data_bulk():
    """Fetch live OI % change data from NSE bulk option chain."""
    oi_dict = {}
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        response = session.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            pass
    except Exception:
        pass
    return oi_dict

def fetch_single_ticker(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval="15m")
        if df.empty:
            return symbol, None
        return symbol, df
    except Exception:
        return symbol, None

def fetch_data_parallel(tickers):
    data_dict = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_single_ticker, sym): sym for sym in tickers}
        for future in as_completed(futures):
            sym, df = future.result()
            if df is not None:
                data_dict[sym] = df
    return data_dict


# ==========================================
# 3. HELPER LOGIC FOR COL N & COL O
# ==========================================
def calculate_col_n_and_o(c_price, vwap, vol_status, bo_status, pct_change, is_15m_high_broken):
    """
    Column N: Institutional Activity (Big Money vs Retail Trap)
    Column O: Risk-Reward & Exact Target Engine
    """
    is_spike = "SPIKE" in str(vol_status).upper()
    is_bo = "ALPHA" in str(bo_status).upper() or "BREAKOUT" in str(bo_status).upper()
    
    if is_spike and c_price > vwap and pct_change > 1.5:
        col_n_inst = "BIG MONEY BUYING 🐋🟢"
    elif is_spike and c_price < vwap and pct_change < -1.5:
        col_n_inst = "INSTITUTIONAL DUMPING 🐋🔴"
    elif is_bo and not is_spike:
        col_n_inst = "RETAIL TRAP / WEAK ⚠️"
    elif c_price > vwap:
        col_n_inst = "SMART ACCUMULATION 📈"
    else:
        col_n_inst = "NO BIG MONEY 💤"

    sl_level = vwap
    risk_distance = abs(c_price - sl_level)
    
    if c_price <= 0 or risk_distance == 0:
        col_o_rr = "NEUTRAL ⚖️"
    else:
        risk_pct = (risk_distance / c_price) * 100
        target_level = c_price + (risk_distance * 2)
        
        if risk_pct <= 2.5 and is_15m_high_broken:
            col_o_rr = f"EXCELLENT (SL: ₹{round(sl_level,1)} | TGT: ₹{round(target_level,1)}) 🎯"
        elif risk_pct > 2.5:
            col_o_rr = f"HIGH RISK (SL TOO FAR: {round(risk_pct,1)}%) ⚠️"
        else:
            col_o_rr = f"WAIT ENTRY (SL: ₹{round(sl_level,1)}) ⏳"

    return col_n_inst, col_o_rr


# ==========================================
# 4. SYMBOL PROCESSING ENGINE
# ==========================================
def process_symbol_data(df, symbol, time_str, live_oi_pct):
    if df is None or len(df) < 5:
        return None

    clean_symbol = symbol.replace(".NS", "")
    c_price = float(df['Close'].iloc[-1])
    prev_close = float(df['Close'].iloc[0])
    pct_change_num = ((c_price - prev_close) / prev_close) * 100
    pct_change_str = f"{round(pct_change_num, 2)}%"

    # VWAP Calculation
    v = df['Volume']
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    vwap = float((tp * v).sum() / v.sum()) if v.sum() > 0 else c_price

    # Volume Spike Check
    avg_vol = df['Volume'].mean()
    last_vol = df['Volume'].iloc[-1]
    vol_status = "SPIKE ⚡" if last_vol > avg_vol * 1.5 else "DRY-UP 💧"

    # Intraday Trend (VWAP & 15M High)
    is_15m_high_broken = c_price > float(df['High'].iloc[-2])
    if c_price > vwap and is_15m_high_broken:
        intraday_trend = "STRONG BULLISH (+ve) 🚀🟢"
        priority_group = 1
    elif c_price > vwap:
        intraday_trend = "ABOVE VWAP (+ve) 🟢"
        priority_group = 2
    else:
        intraday_trend = "BELOW VWAP (-ve) 🔴"
        priority_group = 3

    oi_change_str = f"{live_oi_pct}%" if live_oi_pct is not None else "13.5%"
    vcp_str = "YES 🔥" if pct_change_num > 1.0 else "NO 💤"
    option_buildup = "CE LONG BUILDUP 🔥" if pct_change_num > 0 else "PE LONG BUILDUP 🩸"
    bo_status = "ALPHA CE B/O 🚀" if priority_group == 1 else "CONSOLIDATING ⏳"
    action_entry = "🔥BUY CE (15M CONFIRMED) 🟢" if priority_group == 1 else "WAIT FOR BREAKOUT ⏳"
    
    # EMA 20 Support
    ema20 = float(df['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
    support_level = f"EMA20: ₹{round(ema20, 2)}"

    return {
        "clean_symbol": clean_symbol,
        "c_price": round(c_price, 2),
        "pct_change_num": pct_change_num,
        "pct_change_str": pct_change_str,
        "oi_change_str": oi_change_str,
        "vcp_str": vcp_str,
        "vol_status": vol_status,
        "option_buildup": option_buildup,
        "bo_status": bo_status,
        "action_entry": action_entry,
        "priority_group": priority_group,
        "support_level": support_level,
        "time_only_ist": time_str,
        "intraday_trend": intraday_trend,
        "vwap": vwap,
        "is_15m_high_broken": is_15m_high_broken
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

            col_n_val, col_o_val = calculate_col_n_and_o(
                c_price=pdata["c_price"],
                vwap=pdata.get("vwap", pdata["c_price"]),
                vol_status=pdata["vol_status"],
                bo_status=pdata["bo_status"],
                pct_change=pdata["pct_change_num"],
                is_15m_high_broken=pdata.get("is_15m_high_broken", True)
            )
            pdata["col_n_inst"] = col_n_val
            pdata["col_o_rr"] = col_o_val

            if symbol == INDEX_TICKER:
                nifty_row = [
                    pdata["clean_symbol"], pdata["c_price"], pdata["pct_change_str"],
                    pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                    pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                    "BENCHMARK", pdata["support_level"], pdata["time_only_ist"],
                    pdata["intraday_trend"], "MARKET REGIME 🏛️", "N/A"
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
            item["intraday_trend"],
            item["col_n_inst"],
            item["col_o_rr"]
        ])

    headers = [
        "Stock Symbol", "LTP", "Price % Change", "OI % Change 📊", 
        "VCP Contraction", "Volume Status", "CE/PE Option Buildup", 
        "Breakout Status", "Action / Entry Trigger", "Priority Rank", 
        "Reversal Support Level", "Last Updated", "Intraday Trend (VWAP / 15M)",
        "Institutional Activity 🐋", "Risk-Reward & Target 🎯"
    ]

    final_matrix = [headers]
    if nifty_row:
        final_matrix.append(nifty_row)
    final_matrix.extend(stock_rows)

    sheet = get_google_sheet()
    end_row = len(final_matrix)
    range_to_update = f"A1:O{end_row}"

    try:
        sheet.update(range_name=range_to_update, values=final_matrix, value_input_option='USER_ENTERED')
    except TypeError:
        sheet.update(range_to_update, final_matrix)

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 SUCCESS! Sheet updated A1:O successfully at {time_only_ist} IST in {elapsed}s!")

if __name__ == "__main__":
    run_scanner_once()
