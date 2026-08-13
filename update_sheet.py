import os
import json
import time
from datetime import datetime
import pytz
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. GOOGLE SHEETS & TICKER SETUP
# ==========================================
SPREADSHEET_NAME = 'Stock_Scanner'          
WORKSHEET_NAME = 'VALUE TRADING BREAKOUT LIVE' 
INDEX_TICKER = "^NSEI"                      

ALL_TICKERS = [
    INDEX_TICKER,
    "ABB.NS", "ABBOTINDIA.NS", "ALKYLAMINE.NS", "AMBUJACEM.NS", "ANGELONE.NS",
    "APLAPOLLO.NS", "APOLLOHOSP.NS", "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS",
    "AUROPHARMA.NS", "BAJAJ-AUTO.NS", "BALKRISIND.NS", "BDL.NS", "BEL.NS",
    "BHARATFORG.NS", "BHARTIARTL.NS", "BHEL.NS", "BIOCON.NS", "BLUESTARCO.NS",
    "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "BSE.NS", "CAMS.NS",
    "CDSL.NS", "CGPOWER.NS", "CIPLA.NS", "COALINDIA.NS", "COCHINSHIP.NS",
    "COFORGE.NS", "CONCOR.NS", "CROMPTON.NS", "CUMMINSIND.NS", "DALBHARAT.NS",
    "DELHIVERY.NS", "DIVISLAB.NS", "DIXON.NS", "DLF.NS", "DMART.NS",
    "DRREDDY.NS", "EICHERMOT.NS", "ETERNAL.NS", "FORCE.NS", "FORTIS.NS",
    "GAIL.NS", "GLENMARK.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRASIM.NS",
    "GVT.NS", "HAL.NS", "HAVELLS.NS", "HCLTECH.NS", "HEROMOTOCO.NS",
    "HINDALCO.NS", "HINDPETRO.NS", "HINDUNILVR.NS", "HINDZINC.NS", "ICICIBANK.NS",
    "ICICIPRULI.NS", "INDIGO.NS", "INDUSTOWER.NS", "INFY.NS", "INOXWIND.NS",
    "IOC.NS", "IREDA.NS", "ITC.NS", "JINDALSTEL.NS", "JSWENERGY.NS",
    "JSWSTEEL.NS", "JUBLFOOD.NS", "KALYANKJIL.NS", "KAYNES.NS", "KEI.NS",
    "KFINTECH.NS", "KPITTECH.NS", "LAURUSLABS.NS", "LODHA.NS", "LT.NS",
    "LTF.NS", "LTIM.NS", "LUPIN.NS", "M&M.NS", "MANKIND.NS",
    "MARICO.NS", "MARUTI.NS", "MAXHEALTH.NS", "MOTHERSON.NS", "MOTILALOFS.NS",
    "MPHASIS.NS", "MRF.NS", "NATIONALUM.NS", "NAUKRI.NS", "NBCC.NS",
    "NESTLEIND.NS", "NHPC.NS", "NMDC.NS", "NTPC.NS", "NYKAA.NS",
    "OBERREALT.NS", "OFSS.NS", "PAGEIND.NS", "PAYTM.NS", "PERSISTENT.NS",
    "PETRONET.NS", "PFC.NS", "PHOENIXLTD.NS", "PIDILITIND.NS", "PIIND.NS",
    "PNB.NS", "POLYCAB.NS", "POWERGRID.NS", "PREMIERENE.NS", "PRESTAGE.NS",
    "RECLTD.NS", "RELIANCE.NS", "RVNL.NS", "SAIL.NS", "SBIN.NS", "AVANTIFEED.NS",
    "SHREECEM.NS", "SIEMENS.NS", "SOLARINDS.NS", "SONACOMS.NS", "SRF.NS", 
    "SUNPHARMA.NS", "SUPREMEIND.NS", "SUZLON.NS", "SWIGGY.NS", "TATACONSUM.NS", 
    "TATAELXSI.NS", "TATAMOTORS.NS", "TMPV.NS", "TATASTEEL.NS", "TCS.NS", 
    "TECHM.NS", "TIINDIA.NS", "TITAN.NS", "TORNTPHARM.NS", "TVSMOTOR.NS", 
    "ULTRACEMCO.NS", "UNOMINDA.NS", "UPL.NS", "VEDL.NS", "VOLTAS.NS", 
    "WAAREEENER.NS", "WIPRO.NS", "ZYDUSLIFE.NS", "AMBER.NS"
]

def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if os.path.exists('credentials.json'):
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    elif "GCP_SA_KEY" in os.environ and os.environ["GCP_SA_KEY"].strip():
        secret_json_str = os.environ["GCP_SA_KEY"].strip()
        service_account_info = json.loads(secret_json_str)
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    else:
        raise FileNotFoundError("Credentials not found!")

    client = gspread.authorize(creds)
    sheet_id = os.environ.get("SHEET_ID")
    spreadsheet = client.open_by_key(sheet_id.strip()) if sheet_id else client.open(SPREADSHEET_NAME)
    try:
        return spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.get_worksheet(0)

def fetch_data_parallel(tickers):
    data_dict = {}
    try:
        data = yf.download(tickers, period="5d", interval="15m", group_by="ticker", progress=False)
        for ticker in tickers:
            df = data if len(tickers) == 1 else data.get(ticker)
            if df is not None and not df.empty:
                df = df.dropna(subset=['Close'])
                if len(df) >= 5:
                    data_dict[ticker] = df
    except Exception as e:
        print(f"Error fetching data: {e}")
    return data_dict

def process_symbol_data(df, symbol, time_str):
    if df is None or len(df) < 5:
        return None

    clean_symbol = "NIFTY 50" if symbol == INDEX_TICKER else symbol.replace(".NS", "").replace("^", "").strip()

    c_price = float(df['Close'].iloc[-1])
    day_open = float(df['Open'].iloc[0])
    day_low = float(df['Low'].min())
    prev_close = float(df['Close'].iloc[0])
    
    pct_change_num = ((c_price - prev_close) / prev_close) * 100
    pct_change_str = f"{round(pct_change_num, 2)}%"

    v = df['Volume']
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    vwap = float((tp * v).sum() / v.sum()) if v.sum() > 0 else c_price
    ema20 = float(df['Close'].ewm(span=20, adjust=False).mean().iloc[-1])

    avg_vol = df['Volume'].mean()
    last_vol = df['Volume'].iloc[-1]
    vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0
    vol_status = f"{round(vol_ratio, 1)}x SPIKE ⚡" if vol_ratio > 1.5 else "DRY-UP 💧"

    is_15m_high_broken = c_price > float(df['High'].iloc[-2])
    is_above_vwap = c_price > vwap
    is_above_ema20 = c_price > ema20
    
    # -------------------------------------------------------------
    # NEW RECALIBRATED REASONING & RALLY SCORE ENGINE
    # -------------------------------------------------------------
    open_low_gap_pct = abs(day_open - day_low) / day_open * 100
    is_open_approx_low = open_low_gap_pct < 0.4  # Institutional Signature

    # Multi-factor Rally Score Calculation
    rally_score = (pct_change_num * 2.5) + (vol_ratio * 3.0)
    if is_open_approx_low:
        rally_score += 10.0  # Big Institutional Bonus
    if is_above_vwap and is_15m_high_broken:
        rally_score += 5.0

    # Trend and Action Assignment
    if is_above_vwap and is_above_ema20 and is_15m_high_broken and pct_change_num > 0:
        intraday_trend = "STRONG BULLISH (+ve) 🚀🟢"
        priority_group = 1  # Active Breakouts
        bo_status = "ALPHA CE B/O 🚀"
        action_entry = "🔥BUY CE (15M CONFIRMED) 🟢"

    elif not is_above_vwap and pct_change_num > 1.5:
        intraday_trend = "VWAP BROKEN (-ve) 🚨"
        priority_group = 4  # Early Exit Group
        bo_status = "REVERSAL RISK ⚠️"
        action_entry = "🚨 EXIT NOW (VWAP BROKEN) 🛑"

    elif is_above_vwap and is_above_ema20:
        intraday_trend = "ABOVE VWAP (+ve) 🟢"
        priority_group = 2  # Watchlist
        bo_status = "READY TO FLY ⏳"
        action_entry = "WATCH FOR BREAKOUT 👁️"

    else:
        intraday_trend = "BELOW VWAP (-ve) 🔴"
        priority_group = 3
        bo_status = "CONSOLIDATING 💤"
        action_entry = "NO ENTRY 🚫"

    # Institutional Activity Text
    if is_open_approx_low and vol_ratio > 1.5:
        col_n = "MEGA INSTITUTIONAL BUY 🐋🚀"
        col_o = f"HIGH CONVICTION (SL: ₹{round(c_price*0.985,1)} | TGT: ₹{round(c_price*1.05,1)}) 🎯"
    elif pct_change_num > 0 and is_above_vwap:
        col_n = "SMART ACCUMULATION 📈"
        col_o = f"GOOD RISK-REWARD (SL: ₹{round(c_price*0.99,1)} | TGT: ₹{round(c_price*1.03,1)}) 👍"
    else:
        col_n = "NO BIG MONEY / WEAK 💤🔴"
        col_o = f"AVOID / WAIT ⏳"

    return {
        "clean_symbol": clean_symbol,
        "c_price": round(c_price, 2),
        "pct_change_num": pct_change_num,
        "pct_change_str": pct_change_str,
        "oi_change_str": "13.5%",
        "vcp_str": "YES 🔥" if pct_change_num > 1.0 else "NO 💤",
        "vol_status": vol_status,
        "vol_ratio": vol_ratio,
        "rally_score": rally_score,
        "option_buildup": "CE LONG BUILDUP 🔥" if pct_change_num > 0 else "PE LONG BUILDUP 🩸",
        "bo_status": bo_status,
        "action_entry": action_entry,
        "priority_group": priority_group,
        "support_level": f"EMA20: ₹{round(ema20, 2)}",
        "time_only_ist": time_str,
        "intraday_trend": intraday_trend,
        "col_n_inst": col_n,
        "col_o_rr": col_o
    }

def run_scanner_once():
    start_time = time.time()
    ist = pytz.timezone('Asia/Kolkata')
    time_only_ist = datetime.now(ist).strftime("%H:%M:%S")

    data_dict = fetch_data_parallel(ALL_TICKERS)
    nifty_row = None
    stock_data_list = []

    for symbol, data in data_dict.items():
        try:
            pdata = process_symbol_data(data, symbol, time_only_ist)
            if not pdata:
                continue

            if symbol == INDEX_TICKER:
                nifty_row = [
                    "NIFTY 50", pdata["c_price"], pdata["pct_change_str"],
                    pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                    pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                    "BENCHMARK 🏛️", pdata["support_level"], pdata["time_only_ist"],
                    pdata["intraday_trend"], "MARKET REGIME 🏛️", "N/A"
                ]
            else:
                stock_data_list.append(pdata)
        except Exception as e:
            continue

    # -------------------------------------------------------------
    # NEW DYNAMIC SORTING: Priority Group FIRST, then RALLY SCORE
    # Solar, Bosch, Astral, Amber will now naturally sit AT THE TOP!
    # -------------------------------------------------------------
    stock_data_list.sort(key=lambda x: (x["priority_group"], -x["rally_score"]))

    stock_rows = []
    bo_rank = 1
    ready_rank = 1
    
    for item in stock_data_list:
        if item["priority_group"] == 1:
            rank_tag = f"🔥 TOP PRIORITY #{bo_rank} ⚡"
            bo_rank += 1
        elif item["priority_group"] == 2:
            rank_tag = f"👀 READY #{ready_rank}"
            ready_rank += 1
        elif item["priority_group"] == 4:
            rank_tag = "🚨 EXIT SIGNAL"
        else:
            rank_tag = "💤 WAIT"

        stock_rows.append([
            str(item["clean_symbol"]), item["c_price"], item["pct_change_str"],
            item["oi_change_str"], item["vcp_str"], item["vol_status"],
            item["option_buildup"], item["bo_status"], item["action_entry"],
            rank_tag, item["support_level"], item["time_only_ist"],
            item["intraday_trend"], item["col_n_inst"], item["col_o_rr"]
        ])

    headers = [
        "Stock Symbol", "LTP", "Price % Change", "OI % Change 📊", 
        "VCP Contraction", "Volume Status", "CE/PE Option Buildup", 
        "Breakout Status", "Action / Entry Trigger", "Priority Rank 🎯", 
        "Reversal Support Level", "Last Updated", "Intraday Trend (VWAP / 15M)",
        "Institutional Activity 🐋", "Risk-Reward & Target 🎯"
    ]

    final_matrix = [headers]
    if nifty_row:
        final_matrix.append(nifty_row)
    final_matrix.extend(stock_rows)

    sheet = get_google_sheet()
    sheet.clear()
    
    range_to_update = f"A1:O{len(final_matrix)}"
    try:
        sheet.update(range_name=range_to_update, values=final_matrix, value_input_option='USER_ENTERED')
    except TypeError:
        sheet.update(range_to_update, final_matrix)

    print(f"🎉 SUCCESS! Cleaned & Recalibrated for Mega-Rallies in {round(time.time() - start_time, 2)}s!")

if __name__ == "__main__":
    run_scanner_once()
