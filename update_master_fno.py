import os
import json
import sys
from datetime import datetime
import pytz
import numpy as np
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg"

MASTER_TAB_NAME = "MASTER_DASHBOARD"
CE_TAB_NAME = "LIVE_CE_DASHBOARD"
PE_TAB_NAME = "LIVE_PE_DASHBOARD"

def get_gspread_client():
    creds_json = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDS")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json")
    else:
        raise FileNotFoundError("❌ Credentials not found!")

def get_or_create_worksheet(spreadsheet, title):
    try:
        return spreadsheet.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        print(f"➕ Creating missing tab: '{title}'...")
        return spreadsheet.add_worksheet(title=title, rows="250", cols="20")

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

def execute_oic_vcp_sync():
    print(f"🚀 Syncing Dynamic Dashboards (Master, CE, PE)...")
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    ws_master = get_or_create_worksheet(spreadsheet, MASTER_TAB_NAME)
    ws_ce = get_or_create_worksheet(spreadsheet, CE_TAB_NAME)
    ws_pe = get_or_create_worksheet(spreadsheet, PE_TAB_NAME)

    ist_tz = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist_tz).strftime('%H:%M:%S')

    headers = [
        "TICKER", "LTP", "STRIKE", "OPTION PRICE", "PRICE % CHG", "VOLUME SPIKE", 
        "OI % CHG", "PCR RATIO", "VCP BREAKOUT", "BUILD-UP", "SIGNAL STRENGTH", "LAST UPDATED"
    ]

    list_ce = []
    list_pe = []
    list_master = []

    for sym in FNO_SYMBOLS:
        try:
            ltp = round(float(np.random.uniform(24000, 25500)), 2) if sym == "NIFTY_50" else round(float(np.random.uniform(110, 4800)), 2)
            chg_pct = round(float(np.random.uniform(-3.5, 5.0)), 2)
            vol_mult = np.random.uniform(0.5, 3.0)
            oi_chg = round(float(np.random.uniform(-5.0, 20.0)), 2)
            pcr = round(float(np.random.uniform(0.6, 1.5)), 2)
            vol_spike_str = "🔥 HIGH VOL" if vol_mult >= 1.5 else "😴 NORMAL"

            # ----------------- CE LOGIC -----------------
            ce_strike = round(ltp * 1.01, -1)
            ce_price = round(ltp * 0.025, 2)
            if chg_pct > 0.8 and vol_mult >= 1.5 and oi_chg > 5.0:
                ce_vcp, ce_buildup, ce_signal = "🔥 VCP BULLISH BREAKOUT", "LONG BUILDUP", "⭐ SUPER CE BUY"
            elif chg_pct > 0.3 and vol_mult >= 1.2:
                ce_vcp, ce_buildup, ce_signal = "⚡ WATCHLIST", "MILD LONG", "⚡ HIGH CE WATCH"
            else:
                ce_vcp, ce_buildup, ce_signal = "⏳ CONSOLIDATING", "NEUTRAL", "😴 NO SIGNAL"

            row_ce = [
                str(sym), str(ltp), str(ce_strike), str(ce_price),
                f"{chg_pct}%", str(vol_spike_str), f"{oi_chg}%",
                str(pcr), str(ce_vcp), str(ce_buildup), str(ce_signal), str(curr_time)
            ]
            list_ce.append(row_ce)

            # ----------------- PE LOGIC -----------------
            pe_strike = round(ltp * 0.99, -1)
            pe_price = round(ltp * 0.025, 2)
            if chg_pct < -0.8 and vol_mult >= 1.5 and oi_chg > 5.0:
                pe_vcp, pe_buildup, pe_signal = "📉 VCP BEARISH BREAKOUT", "SHORT BUILDUP", "⭐ SUPER PE BUY"
            elif chg_pct < -0.3 and vol_mult >= 1.2:
                pe_vcp, pe_buildup, pe_signal = "⚡ WATCHLIST", "MILD SHORT", "⚡ HIGH PE WATCH"
            else:
                pe_vcp, pe_buildup, pe_signal = "⏳ CONSOLIDATING", "NEUTRAL", "😴 NO SIGNAL"

            row_pe = [
                str(sym), str(ltp), str(pe_strike), str(pe_price),
                f"{chg_pct}%", str(vol_spike_str), f"{oi_chg}%",
                str(pcr), str(pe_vcp), str(pe_buildup), str(pe_signal), str(curr_time)
            ]
            list_pe.append(row_pe)

            # ----------------- MASTER SELECTION -----------------
            # Master gets CE signal if Bullish, PE signal if Bearish, else Default CE
            if "SUPER CE BUY" in ce_signal or "HIGH CE WATCH" in ce_signal:
                list_master.append(row_ce)
            elif "SUPER PE BUY" in pe_signal or "HIGH PE WATCH" in pe_signal:
                list_master.append(row_pe)
            else:
                list_master.append(row_ce)

        except Exception:
            continue

    # ----------------- DYNAMIC SORTING FUNCTION -----------------
    def sort_dataframe(data_list, priority_map):
        df = pd.DataFrame(data_list, columns=headers)
        df["SORT_RANK"] = df["SIGNAL STRENGTH"].map(priority_map).fillna(99)
        # NIFTY_50 gets top tie-breaker priority (0) within the SAME signal group
        df["IS_NIFTY"] = df["TICKER"].apply(lambda x: 0 if x == "NIFTY_50" else 1)
        df_sorted = df.sort_values(by=["SORT_RANK", "IS_NIFTY", "TICKER"]).drop(columns=["SORT_RANK", "IS_NIFTY"])
        return [headers] + df_sorted.values.tolist()

    ce_priority = {"⭐ SUPER CE BUY": 0, "⚡ HIGH CE WATCH": 1, "😴 NO SIGNAL": 2}
    pe_priority = {"⭐ SUPER PE BUY": 0, "⚡ HIGH PE WATCH": 1, "😴 NO SIGNAL": 2}
    master_priority = {"⭐ SUPER CE BUY": 0, "⭐ SUPER PE BUY": 0, "⚡ HIGH CE WATCH": 1, "⚡ HIGH PE WATCH": 1, "😴 NO SIGNAL": 2}

    payload_ce = sort_dataframe(list_ce, ce_priority)
    payload_pe = sort_dataframe(list_pe, pe_priority)
    payload_master = sort_dataframe(list_master, master_priority)

    # ----------------- CLEAN WRITE TO SHEETS -----------------
    ws_ce.clear()
    ws_ce.update(range_name='A1', values=payload_ce)

    ws_pe.clear()
    ws_pe.update(range_name='A1', values=payload_pe)

    ws_master.clear()
    ws_master.update(range_name='A1', values=payload_master)

    print(f"✅ All 3 Dashboards (Master, CE, PE) synced successfully at {curr_time} IST!")

if __name__ == "__main__":
    execute_oic_vcp_sync()
