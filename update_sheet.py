import os
import json
import sys
from datetime import datetime
import pytz
import numpy as np
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# CE / PE Breakout Sheet ID
SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg"

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
        print(f"➕ Creating tab: '{title}'...")
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
    print(f"🚀 Running CE/PE Breakout Sync ({SHEET_ID})...")
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    ws_ce = get_or_create_worksheet(spreadsheet, CE_TAB_NAME)
    ws_pe = get_or_create_worksheet(spreadsheet, PE_TAB_NAME)

    ist_tz = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist_tz).strftime('%H:%M:%S')

    headers_ce = [
        "TICKER", "LTP", "CE STRIKE", "CE PRICE", "PRICE % CHG", "VOLUME SPIKE", 
        "OI % CHG", "PCR RATIO", "VCP BREAKOUT", "BUILD-UP", "SIGNAL STRENGTH", "LAST UPDATED"
    ]
    
    headers_pe = [
        "TICKER", "LTP", "PE STRIKE", "PE PRICE", "PRICE % CHG", "VOLUME SPIKE", 
        "OI % CHG", "PCR RATIO", "VCP BREAKOUT", "BUILD-UP", "SIGNAL STRENGTH", "LAST UPDATED"
    ]

    list_ce = []
    list_pe = []

    for sym in FNO_SYMBOLS:
        try:
            ltp = round(float(np.random.uniform(24000, 25500)), 2) if sym == "NIFTY_50" else round(float(np.random.uniform(110, 4800)), 2)
            chg_pct = round(float(np.random.uniform(-3.5, 5.0)), 2)
            vol_mult = np.random.uniform(0.5, 3.0)
            oi_chg = round(float(np.random.uniform(-5.0, 20.0)), 2)
            pcr = round(float(np.random.uniform(0.6, 1.5)), 2)
            vol_spike_str = "🔥 HIGH VOL" if vol_mult >= 1.5 else "😴 NORMAL"

            # Call Option (CE) Logic
            ce_strike = round(ltp * 1.01, -1)
            ce_price = round(ltp * 0.025, 2)
            if chg_pct > 0.8 and vol_mult >= 1.5 and oi_chg > 5.0:
                ce_vcp, ce_buildup, ce_signal = "🔥 VCP BULLISH BREAKOUT", "LONG BUILDUP", "⭐ SUPER CE BUY"
            elif chg_pct > 0.3 and vol_mult >= 1.2:
                ce_vcp, ce_buildup, ce_signal = "⚡ WATCHLIST", "MILD LONG", "⚡ HIGH CE WATCH"
            else:
                ce_vcp, ce_buildup, ce_signal = "⏳ CONSOLIDATING", "NEUTRAL", "😴 NO SIGNAL"

            list_ce.append({
                "TICKER": sym, "LTP": str(ltp), "CE STRIKE": str(ce_strike), "CE PRICE": str(ce_price),
                "PRICE % CHG": f"{chg_pct}%", "VOLUME SPIKE": vol_spike_str, "OI % CHG": f"{oi_chg}%",
                "PCR RATIO": str(pcr), "VCP BREAKOUT": ce_vcp, "BUILD-UP": ce_buildup,
                "SIGNAL STRENGTH": ce_signal, "LAST UPDATED": curr_time
            })

            # Put Option (PE) Logic
            pe_strike = round(ltp * 0.99, -1)
            pe_price = round(ltp * 0.025, 2)
            if chg_pct < -0.8 and vol_mult >= 1.5 and oi_chg > 5.0:
                pe_vcp, pe_buildup, pe_signal = "📉 VCP BEARISH BREAKOUT", "SHORT BUILDUP", "⭐ SUPER PE BUY"
            elif chg_pct < -0.3 and vol_mult >= 1.2:
                pe_vcp, pe_buildup, pe_signal = "⚡ WATCHLIST", "MILD SHORT", "⚡ HIGH PE WATCH"
            else:
                pe_vcp, pe_buildup, pe_signal = "⏳ CONSOLIDATING", "NEUTRAL", "😴 NO SIGNAL"

            list_pe.append({
                "TICKER": sym, "LTP": str(ltp), "PE STRIKE": str(pe_strike), "PE PRICE": str(pe_price),
                "PRICE % CHG": f"{chg_pct}%", "VOLUME SPIKE": vol_spike_str, "OI % CHG": f"{oi_chg}%",
                "PCR RATIO": str(pcr), "VCP BREAKOUT": pe_vcp, "BUILD-UP": pe_buildup,
                "SIGNAL STRENGTH": pe_signal, "LAST UPDATED": curr_time
            })
        except Exception:
            continue

    # Priority Sorting for CE Dashboard (Column K: SIGNAL STRENGTH)
    df_ce = pd.DataFrame(list_ce)
    ce_priority = {"⭐ SUPER CE BUY": 1, "⚡ HIGH CE WATCH": 2, "😴 NO SIGNAL": 3}
    df_ce["SORT_RANK"] = df_ce["SIGNAL STRENGTH"].map(ce_priority).fillna(4)
    df_ce = df_ce.sort_values(by=["SORT_RANK", "TICKER"]).drop(columns=["SORT_RANK"])

    # Priority Sorting for PE Dashboard (Column K: SIGNAL STRENGTH)
    df_pe = pd.DataFrame(list_pe)
    pe_priority = {"⭐ SUPER PE BUY": 1, "⚡ HIGH PE WATCH": 2, "😴 NO SIGNAL": 3}
    df_pe["SORT_RANK"] = df_pe["SIGNAL STRENGTH"].map(pe_priority).fillna(4)
    df_pe = df_pe.sort_values(by=["SORT_RANK", "TICKER"]).drop(columns=["SORT_RANK"])

    # Push Sorted Data to Sheets
    ws_ce.clear()
    ws_ce.update(values=[headers_ce] + df_ce.values.tolist(), range_name="A1")

    ws_pe.clear()
    ws_pe.update(values=[headers_pe] + df_pe.values.tolist(), range_name="A1")

    print(f"🏆 CE & PE Dashboards sorted & updated at {curr_time} IST!")

if __name__ == "__main__":
    execute_oic_vcp_sync()
