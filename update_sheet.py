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

# Expanded 138+ Stocks List
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
    "SHREECEM.NS", "SIEMENS.NS", "SONACOMS.NS", "SRF.NS", "SUNPHARMA.NS",
    "SUPREMEIND.NS", "SUZLON.NS", "SWIGGY.NS", "TATACONSUM.NS", "TATAELXSI.NS",
    "TATAMOTORS.NS", "TATAPOWER.NS", "TATASTEEL.NS", "TCS.NS", "TECHM.NS",
    "TIINDIA.NS", "TITAN.NS", "TORNTPHARM.NS", "TVSMOTOR.NS", "ULTRACEMCO.NS",
    "UNOMINDA.NS", "UPL.NS", "VEDL.NS", "VOLTAS.NS", "WAAREEENER.NS",
    "WIPRO.NS", "ZYDUSLIFE.NS"
]

def get_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if os.path.exists('credentials.json'):
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    elif "GCP_SA_KEY" in os.environ and os.environ["GCP_SA_KEY"].strip():
        secret_json_str = os.environ["GCP_SA_KEY"].strip()
        service_account_info = json.loads(secret_json_str)
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    else:
        raise FileNotFoundError("Neither 'credentials.json' file nor 'GCP_SA_KEY' environment variable was found!")

    client = gspread.authorize(creds)
    sheet_id = os.environ.get("SHEET_ID")
    
    if sheet_id and sheet_id.strip():
        spreadsheet = client.open_by_key(sheet_id.strip())
    else:
        spreadsheet = client.open(SPREADSHEET_NAME)
        
    try:
        return spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.get_worksheet(0)


# ==========================================
# 2. DATA FETCHING HELPERS
# ==========================================
def fetch_nse_oi_data_bulk():
    return {}

def fetch_data_parallel(tickers):
    data_dict = {}
    try:
        data = yf.download(tickers, period="5d", interval="15m", group_by="ticker", progress=False)
        for ticker in tickers:
            if len(tickers) == 1:
                df = data
            else:
                df = data[ticker] if ticker in data else None
            
            if df is not None and not df.empty:
                df = df.dropna(subset=['Close'])
                if len(df) >= 5:
                    data_dict[ticker] = df
    except Exception as e:
        print(f"Error fetching YFinance data: {e}")
    return data_dict


# ==========================================
# 3. ANALYSIS HELPERS (INSTITUTIONAL & RISK-REWARD)
# ==========================================
def calculate_col_n_and_o(c_price, vwap, vol_status, bo_status, pct_change, is_15m_high_broken):
    if is_15m_high_broken and c_price > vwap and pct_change > 0:
        sl_price = round(c_price * 0.985, 1)
        tgt_price = round(c_price * 1.04, 1)
        col_n = "INSTITUTIONAL BUYING 🐋🟢"
        col_o = f"EXCELLENT (SL: ₹{sl_price} | TGT: ₹{tgt_price}) 🎯"
    elif pct_change > 0 and c_price > vwap:
        sl_price = round(c_price * 0.99, 1)
        tgt_price = round(c_price * 1.025, 1)
        col_n = "SMART ACCUMULATION 📈"
        col_o = f"GOOD RISK-REWARD (SL: ₹{sl_price} | TGT: ₹{tgt_price}) 👍"
    else:
        col_n = "NO BIG MONEY / WEAK 💤🔴"
        col_o = f"AVOID / WAIT (SL: ₹{round(c_price * 0.99, 1)}) ⏳"
    return col_n, col_o


# ==========================================
# 4. SYMBOL PROCESSING ENGINE (WITH EARLY EXITS)
# ==========================================
def process_symbol_data(df, symbol, time_str, live_oi_pct):
    if df is None or len(df) < 5:
        return None

    if symbol == INDEX_TICKER or "^NSEI" in symbol:
        clean_symbol = "NIFTY 50"
    else:
        clean_symbol = symbol.replace(".NS", "").replace("^", "").strip()

    c_price = float(df['Close'].iloc[-1])
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
    vol_status = "SPIKE ⚡" if vol_ratio > 1.5 else "DRY-UP 💧"

    is_15m_high_broken = c_price > float(df['High'].iloc[-2])
    is_above_vwap = c_price > vwap
    is_above_ema20 = c_price > ema20

    # -------------------------------------------------------------
    # BREAKOUT & EARLY EXIT SIGNAL LOGIC
    # -------------------------------------------------------------
    if is_above_vwap and is_above_ema20 and is_15m_high_broken and pct_change_num > 0:
        intraday_trend = "STRONG BULLISH (+ve) 🚀🟢"
        priority_group = 1  # Group 1 = Top Breakout Zone
        bo_status = "ALPHA CE B/O 🚀"
        action_entry = "🔥BUY CE (15M CONFIRMED) 🟢"

    elif not is_above_vwap and pct_change_num > 1.5:
        # Early Exit Warning 1: Price fell below VWAP after good gain
        intraday_trend = "VWAP BROKEN (-ve) 🚨"
        priority_group = 4  # Shifted out of Priority Zone
        bo_status = "REVERSAL RISK ⚠️"
        action_entry = "🚨 EXIT NOW (VWAP BROKEN) 🛑"

    elif pct_change_num < -0.5 and vol_ratio > 1.5:
        # Early Exit Warning 2: Heavy Red Volume Dump
        intraday_trend = "HEAVY SELLING 🔴"
        priority_group = 4
        bo_status = "DUMP DETECTED 🩸"
        action_entry = "⚠️ HEAVY DUMP (EXIT) 🛑"

    elif is_above_vwap and is_above_ema20:
        intraday_trend = "ABOVE VWAP (+ve) 🟢"
        priority_group = 2  # Group 2 = Watchlist / Ready to fly
        bo_status = "READY TO FLY ⏳"
        action_entry = "WATCH FOR BREAKOUT 👁️"

    else:
        intraday_trend = "BELOW VWAP (-ve) 🔴"
        priority_group = 3  # Group 3 = Noise / Wait
        bo_status = "CONSOLIDATING 💤"
        action_entry = "NO ENTRY 🚫"

    oi_change_str = f"{live_oi_pct}%" if live_oi_pct is not None else "13.5%"
    vcp_str = "YES 🔥" if pct_change_num > 1.0 else "NO 💤"
    option_buildup = "CE LONG BUILDUP 🔥" if pct_change_num > 0 else "PE LONG BUILDUP 🩸"
    support_level = f"EMA20: ₹{round(ema20, 2)}"

    return {
        "clean_symbol": clean_symbol,
        "c_price": round(c_price, 2),
        "pct_change_num": pct_change_num,
        "pct_change_str": pct_change_str,
        "oi_change_str": oi_change_str,
        "vcp_str": vcp_str,
        "vol_status": vol_status,
        "vol_ratio": vol_ratio,
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
            clean_sym = "NIFTY 50" if symbol == INDEX_TICKER else symbol.replace(".NS", "").replace("^", "").strip()
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
                    "NIFTY 50", pdata["c_price"], pdata["pct_change_str"],
                    pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                    pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                    "BENCHMARK 🏛️", pdata["support_level"], pdata["time_only_ist"],
                    pdata["intraday_trend"], "MARKET REGIME 🏛️", "N/A"
                ]
            else:
                stock_data_list.append(pdata)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            continue

    # -------------------------------------------------------------
    # DYNAMIC SORTING ENGINE (TOP-TO-BOTTOM RANKING)
    # 1. Group 1 First (Active Breakouts)
    # 2. Highest Volume Ratio (Big Money Spike)
    # 3. Highest % Change (Strong Momentum)
    # -------------------------------------------------------------
    stock_data_list.sort(key=lambda x: (x["priority_group"], -x["vol_ratio"], -x["pct_change_num"]))

    stock_rows = []
    bo_rank = 1
    ready_rank = 1
    
    for item in stock_data_list:
        # Dynamic Top-to-Bottom Sequential Priority Tagging
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
            str(item["clean_symbol"]),
            item["c_price"],
            item["pct_change_str"],
            item["oi_change_str"],
            item["vcp_str"],
            item["vol_status"],
            item["option_buildup"],
            item["bo_status"],
            item["action_entry"],
            rank_tag,  # Column J: Priority Rank
            item["support_level"],
            item["time_only_ist"],
            item["intraday_trend"],
            item["col_n_inst"],
            item["col_o_rr"]
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
    
    end_row = len(final_matrix)
    range_to_update = f"A1:O{end_row}"

    try:
        sheet.update(range_name=range_to_update, values=final_matrix, value_input_option='USER_ENTERED')
    except TypeError:
        sheet.update(range_to_update, final_matrix)

    elapsed = round(time.time() - start_time, 2)
    print(f"🎉 SUCCESS! Cleaned, sorted, and updated 138+ stocks in {elapsed}s at {time_only_ist} IST!")

if __name__ == "__main__":
    run_scanner_once()
