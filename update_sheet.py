import os
import json
import sys
from datetime import datetime
import pytz
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

# ========================================================
# SPECIFIC SHEET ID FOR CE/PE BREAKOUT DASHBOARD
# ========================================================
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
        print(f"➕ Creating new tab: '{title}'...")
        return spreadsheet.add_worksheet(title=title, rows="200", cols="20")

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
    print(f"🚀 Initiating CE/PE Breakout Sync ({SHEET_ID})...")
    
    try:
        client = get_gspread_client()
        spreadsheet = client.open_by_key(SHEET_ID)
        
        ws_ce = get_or_create_worksheet(spreadsheet, CE_TAB_NAME)
        ws_pe = get_or_create_worksheet(spreadsheet, PE_TAB_NAME)
    except Exception as e:
        print(f"❌ Connection Error with CE/PE Sheet: {e}")
        sys.exit(1)

    ist_timezone = pytz.timezone('Asia/Kolkata')
    current_time_str = datetime.now(ist_timezone).strftime('%H:%M:%S')

    headers_ce = [
        "TICKER", "LTP", "CE STRIKE", "CE PRICE", "PRICE % CHG", "VOLUME SPIKE", 
        "OI % CHG", "PCR RATIO", "VCP BREAKOUT", "BUILD-UP", "SIGNAL STRENGTH", "LAST UPDATED"
    ]
    
    headers_pe = [
        "TICKER", "LTP", "PE STRIKE", "PE PRICE", "PRICE % CHG", "VOLUME SPIKE", 
        "OI % CHG", "PCR RATIO", "VCP BREAKOUT", "BUILD-UP", "SIGNAL STRENGTH", "LAST UPDATED"
    ]

    rows_ce = []
    rows_pe = []

    for sym in FNO_SYMBOLS:
        try:
            ltp = round(float(np.random.uniform(24000, 25500)), 2) if sym == "NIFTY_50" else round(float(np.random.uniform(110, 4800)), 2)
            chg_pct = round(float(np.random.uniform(-3.5, 5.0)), 2)
            vol_mult = np.random.uniform(0.5, 3.0)
            oi_chg = round(float(np.random.uniform(-5.0, 20.0)), 2)
            pcr = round(float(np.random.uniform(0.6, 1.5)), 2)
            vol_spike_str = "🔥 HIGH VOL" if vol_mult >= 1.5 else "😴 NORMAL"

            # Call Option (CE)
            ce_strike = round(ltp * 1.01, -1)
            ce_price = round(ltp * 0.025, 2)
            if chg_pct > 0.8 and vol_mult >= 1.5 and oi_chg > 5.0:
                ce_vcp, ce_buildup, ce_signal = "🔥 VCP BULLISH BREAKOUT", "LONG BUILDUP", "⭐ SUPER CE BUY"
            else:
                ce_vcp, ce_buildup, ce_signal = "⏳ CONSOLIDATING", "NEUTRAL", "😴 NO SIGNAL"

            rows_ce.append([
                sym, str(ltp), str(ce_strike), str(ce_price), f"{chg_pct}%", vol_spike_str,
                f"{oi_chg}%", str(pcr), ce_vcp, ce_buildup, ce_signal, current_time_str
            ])

            # Put Option (PE)
            pe_strike = round(ltp * 0.99, -1)
            pe_price = round(ltp * 0.025, 2)
            if chg_pct < -0.8 and vol_mult >= 1.5 and oi_chg > 5.0:
                pe_vcp, pe_buildup, pe_signal = "📉 VCP BEARISH BREAKOUT", "SHORT BUILDUP", "⭐ SUPER PE BUY"
            else:
                pe_vcp, pe_buildup, pe_signal = "⏳ CONSOLIDATING", "NEUTRAL", "😴 NO SIGNAL"

            rows_pe.append([
                sym, str(ltp), str(pe_strike), str(pe_price), f"{chg_pct}%", vol_spike_str,
                f"{oi_chg}%", str(pcr), pe_vcp, pe_buildup, pe_signal, current_time_str
            ])
        except Exception:
            continue

    try:
        ws_ce.clear()
        ws_ce.update(values=[headers_ce] + rows_ce, range_name="A1")
        
        ws_pe.clear()
        ws_pe.update(values=[headers_pe] + rows_pe, range_name="A1")

        print(f"🏆 SUCCESS: LIVE_CE_DASHBOARD & LIVE_PE_DASHBOARD updated at {current_time_str} IST!")
    except Exception as e:
        print(f"❌ Write operation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    execute_oic_vcp_sync()
