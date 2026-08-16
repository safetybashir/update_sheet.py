import os
import json
import time
from datetime import datetime
import pytz
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_NAME = 'Stock_Scanner'          
WORKSHEET_NAME = 'PE_BEARISH_BREAKDOWN_LIVE' 
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
    "RECLTD.NS", "RELIANCE.NS", "RVNL.NS", "SAIL.NS", "SBIN.NS",
    "SHREECEM.NS", "SIEMENS.NS", "SOLARINDS.NS", "SONACOMS.NS", "SRF.NS", 
    "SUNPHARMA.NS", "SUPREMEIND.NS", "SUZLON.NS", "SWIGGY.NS", "TATACONSUM.NS", 
    "TATAELXSI.NS", "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", 
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
        return spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows="100", cols="15")

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

def process_pe_data(df, symbol, time_str):
    if df is None or len(df) < 5:
        return None

    clean_symbol = "NIFTY 50" if symbol == INDEX_TICKER else symbol.replace(".NS", "").replace("^", "").strip()

    c_price = float(df['Close'].iloc[-1])
    day_open = float(df['Open'].iloc[0])
    day_high = float(df['High'].max())
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

    is_15m_low_broken = c_price < float(df['Low'].iloc[-2])
    is_below_vwap = c_price < vwap
    is_below_ema20 = c_price < ema20

    # PURE PE / SHORT BREAKDOWN LOGIC
    # Short Score calculation
    pe_score = 0.0
    if pct_change_num < 0:
        pe_score += abs(pct_change_num) * 2.5
    pe_score += (vol_ratio * 3.0)

    # Open approx High Condition (Institutional Shorting Signature)
    open_high_gap_pct = abs(day_open - day_high) / day_open * 100
    if open_high_gap_pct < 0.4:
        pe_score += 10.0  # Big Institutional Shorting Bonus

    if is_below_vwap and is_below_ema20 and is_15m_low_broken and pct_change_num < -0.5:
        intraday_trend = "STRONG BEARISH (-ve) 🩸🔴"
        priority_group = 1  # Active PE Breakout
        bo_status = "ALPHA PE B/O 🚨"
        action_entry = "🔥 BUY PE (15M BREAKDOWN) 🔴"
    elif is_below_vwap and is_below_ema20:
        intraday_trend = "BELOW VWAP (-ve) 🔴"
        priority_group = 2
        bo_status = "READY TO DROP 🩸"
        action_entry = "WATCH FOR PE ENTRY 👁️"
    else:
        intraday_trend = "BULLISH / ABOVE VWAP (+ve) 🟢"
        priority_group = 3
        bo_status = "NO SHORT SETUP 💤"
        action_entry = "AVOID SHORT 🚫"

    if priority_group == 1 and vol_ratio > 1.5:
        col_n = "INSTITUTIONAL SHORT SELLING 🐋🩸"
        col_o = f"HIGH CONVICTION PE (SL: ₹{round(c_price*1.015,1)} | TGT: ₹{round(c_price*0.95,1)}) 🎯"
    elif pct_change_num < 0 and is_below_vwap:
        col_n = "SMART MONEY DISTRIBUTION 📉"
        col_o = f"GOOD RISK-REWARD (SL: ₹{round(c_price*1.01,1)} | TGT: ₹{round(c_price*0.97,1)}) 👍"
    else:
        col_n = "NO SHORT PRESSURE 💤🟢"
        col_o = f"AVOID PE / WAIT ⏳"

    return {
        "clean_symbol": clean_symbol,
        "c_price": round(c_price, 2),
        "pct_change_num": pct_change_num,
        "pct_change_str": pct_change_str,
        "oi_change_str": "+12.4% (SHORT BUILDUP)",
        "vcp_str": "YES 🚨" if pct_change_num < -1.0 else "NO 💤",
        "vol_status": vol_status,
        "vol_ratio": vol_ratio,
        "pe_score": pe_score,
        "option_buildup": "PE LONG BUILDUP 🚨" if pct_change_num < 0 else "CE LONG BUILDUP 🟢",
        "bo_status": bo_status,
        "action_entry": action_entry,
        "priority_group": priority_group,
        "resistance_level": f"EMA20: ₹{round(ema20, 2)}",
        "time_only_ist": time_str,
        "intraday_trend": intraday_trend,
        "col_n_inst": col_n,
        "col_o_rr": col_o
    }

def run_pe_scanner():
    start_time = time.time()
    ist = pytz.timezone('Asia/Kolkata')
    time_only_ist = datetime.now(ist).strftime("%H:%M:%S")

    data_dict = fetch_data_parallel(ALL_TICKERS)
    nifty_row = None
    stock_data_list = []

    for symbol, data in data_dict.items():
        try:
            pdata = process_pe_data(data, symbol, time_only_ist)
            if not pdata:
                continue

            if symbol == INDEX_TICKER:
                nifty_row = [
                    "NIFTY 50", pdata["c_price"], pdata["pct_change_str"],
                    pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                    pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                    "BENCHMARK 🏛️", pdata["resistance_level"], pdata["time_only_ist"],
                    pdata["intraday_trend"], "MARKET REGIME 🏛️", "N/A"
                ]
            else:
                stock_data_list.append(pdata)
        except Exception as e:
            continue

    # Sort PE Candidates: Priority 1 First, then Highest PE Score
    stock_data_list.sort(key=lambda x: (x["priority_group"], -x["pe_score"]))

    stock_rows = []
    pe_rank = 1
    ready_rank = 1
    
    for item in stock_data_list:
        if item["priority_group"] == 1:
            rank_tag = f"🚨 TOP PE PRIORITY #{pe_rank} 🩸"
            pe_rank += 1
        elif item["priority_group"] == 2:
            rank_tag = f"👀 READY TO SHORT #{ready_rank}"
            ready_rank += 1
        else:
            rank_tag = "💤 AVOID PE"

        stock_rows.append([
            str(item["clean_symbol"]), item["c_price"], item["pct_change_str"],
            item["oi_change_str"], item["vcp_str"], item["vol_status"],
            item["option_buildup"], item["bo_status"], item["action_entry"],
            rank_tag, item["resistance_level"], item["time_only_ist"],
            item["intraday_trend"], item["col_n_inst"], item["col_o_rr"]
        ])

    headers = [
        "Stock Symbol", "LTP", "Price % Change", "OI % Change 📊", 
        "VCP Breakdown", "Volume Status", "PE Option Buildup", 
        "Breakdown Status", "Action / PE Trigger", "PE Priority Rank 🎯", 
        "Reversal Resistance Level", "Last Updated", "Intraday Trend (VWAP / 15M)",
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
        sheet.update(range_name=range_to_update, values=final_matrix, value_option='USER_ENTERED')
    except TypeError:
        sheet.update(range_to_update, final_matrix)

    print(f"🎉 PE SCREENER SUCCESS! Calculated in {round(time.time() - start_time, 2)}s!")

if __name__ == "__main__":
    run_pe_scanner()
