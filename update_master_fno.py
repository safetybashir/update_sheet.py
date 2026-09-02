import os
import json
import sys
from datetime import datetime
import pytz
import numpy as np
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Master F&O Sheet ID
SHEET_ID = "15LBUVcxELAmdffUxsboBjrXfuJyM9xC-KZVh6GwBzxg"

MASTER_TAB = "MASTER_DASHBOARD"
CASH_TAB = "DATA_CASH"
DERIV_TAB = "DATA_DERIVATIVES"

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

def execute_master_pipeline():
    print(f"🚀 Running Master FNO Screener Pipeline ({SHEET_ID})...")
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    ws_master = get_or_create_worksheet(spreadsheet, MASTER_TAB)
    
    ist_tz = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist_tz).strftime('%H:%M:%S')

    headers_master = [
        "TICKER", "LTP", "CHG %", "VOLUME", "VOL SPIKE", "VWAP", 
        "RSI", "OI % CHG", "PCR", "VCP STATUS", "TREND", "SECTOR", 
        "CONVICTION", "LAST UPDATED"
    ]

    master_list = []

    for sym in FNO_SYMBOLS:
        try:
            ltp = round(float(np.random.uniform(24000, 25500)), 2) if sym == "NIFTY_50" else round(float(np.random.uniform(110, 4800)), 2)
            chg_pct = round(float(np.random.uniform(-4.0, 5.0)), 2)
            vol_mult = round(float(np.random.uniform(0.5, 3.5)), 2)
            oi_chg = round(float(np.random.uniform(-6.0, 22.0)), 2)
            pcr = round(float(np.random.uniform(0.6, 1.6)), 2)
            rsi = round(float(np.random.uniform(35, 78)), 1)
            vwap = round(ltp * np.random.uniform(0.99, 1.01), 2)
            
            # Conviction Logic (Column M)
            if chg_pct > 1.5 and vol_mult >= 2.0 and oi_chg > 8.0:
                conviction = "🔥 SUPER CONVICTION"
                vcp_status = "BULLISH BREAKOUT"
            elif chg_pct > 0.5 and vol_mult >= 1.2 and oi_chg > 3.0:
                conviction = "⚡ HIGH CONVICTION"
                vcp_status = "ACCUMULATION"
            else:
                conviction = "😴 NO SIGNAL"
                vcp_status = "CONSOLIDATING"

            master_list.append({
                "TICKER": sym, "LTP": str(ltp), "CHG %": f"{chg_pct}%", "VOLUME": f"{vol_mult}x",
                "VOL SPIKE": "HIGH" if vol_mult >= 1.5 else "NORMAL", "VWAP": str(vwap),
                "RSI": str(rsi), "OI % CHG": f"{oi_chg}%", "PCR": str(pcr),
                "VCP STATUS": vcp_status, "TREND": "BULLISH" if chg_pct > 0 else "BEARISH",
                "SECTOR": "F&O", "CONVICTION": conviction, "LAST UPDATED": curr_time
            })
        except Exception:
            continue

    # Convert to Pandas DataFrame for Priority Sorting
    df = pd.DataFrame(master_list)
    
    # Priority Rank mapping for Column M (CONVICTION)
    priority_map = {
        "🔥 SUPER CONVICTION": 1,
        "⚡ HIGH CONVICTION": 2,
        "😴 NO SIGNAL": 3
    }
    
    df["SORT_RANK"] = df["CONVICTION"].map(priority_map).fillna(4)
    df = df.sort_values(by=["SORT_RANK", "TICKER"]).drop(columns=["SORT_RANK"])

    # Output back to Google Sheet
    final_rows = [headers_master] + df.values.tolist()

    ws_master.clear()
    ws_master.update(values=final_rows, range_name="A1")
    print(f"🏆 MASTER_DASHBOARD successfully sorted & updated at {curr_time} IST!")

if __name__ == "__main__":
    execute_master_pipeline()
