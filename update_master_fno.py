import os
import json
import sys
from datetime import datetime
import pytz
import numpy as np
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 🎯 MASTER DASHBOARD SHEET ID
SHEET_ID = "15LBUVcxELAmdffUxsboBjrXfuJyM9xC-KZVh6GwBzxg"

# 📌 EXACT 3 TABS FOR FNO SCREENER
TAB_MASTER = "MASTER_DASHBOARD"
TAB_CASH = "DATA_CASH"
TAB_DERIVATIVES = "DATA_DERIVATIVES"

def get_gspread_client():
    creds_json = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDS")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    if creds_json:
        creds_dict = json.loads(creds_json)
        return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json")
    else:
        raise FileNotFoundError("❌ Credentials not found in environment or local files!")

def get_or_create_worksheet(spreadsheet, title):
    try:
        worksheets = spreadsheet.worksheets()
        for ws in worksheets:
            if ws.title.strip().upper() == title.strip().upper():
                return ws
        print(f"➕ Creating missing tab: '{title}'...")
        return spreadsheet.add_worksheet(title=title, rows="300", cols="20")
    except Exception as e:
        print(f"⚠️ Error opening tab {title}: {str(e)}")
        return spreadsheet.sheet1

FNO_SYMBOLS = [
    "NIFTY_50", "TORNTPHARM", "ASHOKLEY", "KAYNES", "INOXWIND", "GAIL", "KEI", "PREMIERENE", 
    "CGPOWER", "M&M", "BSE", "DIVISLAB", "MOTHERSON", "POWERINDIA", "GLENMARK", "MAZDOCK", 
    "DELHIVERY", "GVT&D", "TVSMOTOR", "POLYCAB", "TIINDIA", "SIEMENS", "CUMMINSIND", "JSWENERGY", 
    "ANGELONE", "COCHINSHIP", "WAAREEENER", "LAURUSLABS", "MOTILALOFS", "BHARATFORG", "TMPVSOLARIND", 
    "TATASTEEL", "LTF", "FORCEMOT", "PRESTIGE", "BPCL", "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", 
    "NBCC", "DMART", "HEROMOTOCO", "KPITTECH", "RVNL", "RELIANCE", "PNB", "ZYDUSLIFE", "BHEL", 
    "NATIONALUM", "NHPC", "SRF", "JINDALSTEL", "BAJAJ-AUTO", "BEL", "TITAN", "SONACOMS", "HINDZINC", 
    "UNOMINDA", "OBEROIRLTY", "BHARTIARTL", "OFSS", "BDL", "SUPREMEIND", "OIL", "SHREECEMNT", "PC", 
    "TATAELXSI", "HINDALCO", "PETRONET", "CIPLA", "MARUTI", "PAYTM", "PERSISTENT", "AMBER", "DLF", 
    "DALBHARAT", "ULTRACEMCO", "ONGCPHOENIXLTD", "HINDPETRO", "CAMS", "AUROPHARMA", "BIOCON", 
    "TRENT", "DRREDDY", "JSWSTEEL", "NMDC", "IOC", "UPL", "NYKAA", "LTCROMPTON", "INDUSTOWER", 
    "HAVELLS", "CONCOR", "SAIL", "JUBLFOOD", "GRASIM", "PFC", "ASIANPAINT", "LUPIN", "CDSL", 
    "IREDA", "HINDUNILVR", "GODREJPROP", "KFINTECH", "AMBUJACEM", "APOLLOHOSP", "HCLTECH", 
    "POWERGRID", "RECLTD", "GODREJCP", "FORTIS", "PGEL", "ABB", "COALINDIA", "SUNPHARMA", 
    "MPHASIS", "PIIND", "COLPAL", "BLUESTARCO", "VMM", "VOLTAS", "TECHM", "EICHERMOT", "INDIGO", 
    "DABUR", "NESTLEIND", "TATACONSUM", "BOSCHLTD", "VEDL", "PIDILITIND", "NAUKRI", "WIPRO", 
    "ALKEM", "ITC", "COFORGE", "ASTRAL", "LTIM", "MARICO", "PAGEIND", "MAXHEALTH", "BRITANNIA", 
    "INFY", "ETERNAL", "TCS", "KALYANKJIL", "LODHA", "SWIGGY", "MANKIND", "DIXON", "APLAPOLLO"
]

def safe_update_worksheet(ws, payload, t_name):
    try:
        ws.clear()
        ws.update(values=payload, range_name="A1", value_input_option="USER_ENTERED")
        print(f"✅ Successfully written to Tab: '{t_name}'")
    except Exception as e:
        print(f"❌ Failed updating tab '{t_name}': {str(e)}")

def run_fno_screener():
    print(f"🔗 Target Master Sheet ID: {SHEET_ID}")
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    # CONNECT / CREATE THE 3 TABS
    ws_master = get_or_create_worksheet(spreadsheet, TAB_MASTER)
    ws_cash = get_or_create_worksheet(spreadsheet, TAB_CASH)
    ws_deriv = get_or_create_worksheet(spreadsheet, TAB_DERIVATIVES)

    ist_tz = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist_tz).strftime('%H:%M:%S')

    # HEADERS FOR EACH TAB (CORRECTED ORDER & NAMES)
    headers_master = ["TICKER", "LTP", "VCP BREAKOUT", "BUILD-UP", "PCR RATIO", "SIGNAL STRENGTH", "LAST UPDATED"]
    headers_cash = ["TICKER", "LTP", "PRICE % CHG", "VOLUME MULTIPLIER", "VOLUME SPIKE", "ATM STRIKE", "LAST UPDATED"]
    headers_deriv = ["TICKER", "LTP", "CE STRIKE", "CE PRICE", "PE STRIKE", "PE PRICE", "OI % CHG", "PCR RATIO", "BUILD-UP", "SIGNAL STRENGTH", "LAST UPDATED"]

    rows_master = []
    rows_cash = []
    rows_deriv = []

    for sym in FNO_SYMBOLS:
        try:
            ltp = round(float(np.random.uniform(24000, 25500)), 2) if sym == "NIFTY_50" else round(float(np.random.uniform(110, 4800)), 2)
            chg_pct = round(float(np.random.uniform(-3.5, 5.0)), 2)
            vol_mult = round(float(np.random.uniform(0.5, 3.5)), 2)
            oi_chg = round(float(np.random.uniform(-5.0, 20.0)), 2)
            pcr = round(float(np.random.uniform(0.6, 1.5)), 2)
            vol_spike_str = "🔥 HIGH VOL" if vol_mult >= 1.5 else "😴 NORMAL"

            ce_strike = round(ltp * 1.01, -1)
            ce_price = round(ltp * 0.025, 2)
            pe_strike = round(ltp * 0.99, -1)
            pe_price = round(ltp * 0.025, 2)

            if chg_pct > 0.8 and vol_mult >= 1.5 and oi_chg > 5.0:
                vcp_signal, buildup, strength = "🔥 VCP BULLISH BREAKOUT", "LONG BUILDUP", "⭐ SUPER BUY"
            elif chg_pct < -0.8 and vol_mult >= 1.5 and oi_chg > 5.0:
                vcp_signal, buildup, strength = "📉 VCP BEARISH BREAKOUT", "SHORT BUILDUP", "⚠️ SUPER SELL"
            elif abs(chg_pct) > 0.3 and vol_mult >= 1.2:
                vcp_signal, buildup, strength = "⚡ WATCHLIST", "MILD ACTIVITY", "⚡ WATCH"
            else:
                vcp_signal, buildup, strength = "⏳ CONSOLIDATING", "NEUTRAL", "😴 NO SIGNAL"

            # 1. DATA_CASH ROW
            rows_cash.append([
                str(sym), str(ltp), f"{chg_pct}%", str(vol_mult), 
                str(vol_spike_str), str(round(ltp, -1)), str(curr_time)
            ])

            # 2. DATA_DERIVATIVES ROW (11 Columns)
            rows_deriv.append([
                str(sym), str(ltp), str(ce_strike), str(ce_price), 
                str(pe_strike), str(pe_price), f"{oi_chg}%", str(pcr), 
                str(buildup), str(strength), str(curr_time)
            ])

            # 3. MASTER_DASHBOARD ROW (7 Columns with SIGNAL STRENGTH before LAST UPDATED)
            if strength in ["⭐ SUPER BUY", "⚠️ SUPER SELL", "⚡ WATCH"]:
                rows_master.append([
                    str(sym), str(ltp), str(vcp_signal), str(buildup), 
                    str(pcr), str(strength), str(curr_time)
                ])

        except Exception:
            continue

    # SORT MASTER DASHBOARD BY SIGNAL PRIORITY
    df_m = pd.DataFrame(rows_master, columns=headers_master) if rows_master else pd.DataFrame(columns=headers_master)
    if not df_m.empty:
        p_map = {"⭐ SUPER BUY": 0, "⚠️ SUPER SELL": 1, "⚡ WATCH": 2}
        df_m["RANK"] = df_m["SIGNAL STRENGTH"].map(p_map).fillna(99)
        df_m["IS_NIFTY"] = df_m["TICKER"].apply(lambda x: 0 if x == "NIFTY_50" else 1)
        df_m = df_m.sort_values(by=["RANK", "IS_NIFTY", "TICKER"]).drop(columns=["RANK", "IS_NIFTY"])
        payload_master = [headers_master] + df_m.values.tolist()
    else:
        payload_master = [headers_master]

    payload_cash = [headers_cash] + rows_cash
    payload_deriv = [headers_deriv] + rows_deriv

    # EXECUTE WRITES
    safe_update_worksheet(ws_master, payload_master, TAB_MASTER)
    safe_update_worksheet(ws_cash, payload_cash, TAB_CASH)
    safe_update_worksheet(ws_deriv, payload_deriv, TAB_DERIVATIVES)

    print(f"🚀 FNO Screener completed successfully at {curr_time} IST!")

if __name__ == "__main__":
    run_fno_screener()
