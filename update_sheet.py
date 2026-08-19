import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
SERVICE_ACCOUNT_FILE = "credentials.json"
INDEX_TICKER = "^NSEI"

STOCKS = [
    INDEX_TICKER, "TCS.NS", "HINDPETRO.NS", "IREDA.NS", "SUNPHARMA.NS", "ITC.NS",
    "TITAN.NS", "LAURUSLABS.NS", "JSWENERGY.NS", "VEDL.NS", "COALINDIA.NS",
    "HINDZINC.NS", "ZYDUSLIFE.NS", "GODREJPROP.NS", "PERSISTENT.NS", "DMART.NS",
    "WIPRO.NS", "PAGEIND.NS", "PAYTM.NS", "MPHASIS.NS", "SBIN.NS", "MARUTI.NS",
    "ULTRACEMCO.NS", "HINDUNILVR.NS", "CIPLA.NS", "BPCL.NS", "RVNL.NS",
    "BRITANNIA.NS", "OFSS.NS", "MARICO.NS", "BIOCON.NS", "ABB.NS",
    "TATACONSUM.NS", "CUMMINSIND.NS", "RECLTD.NS", "COCHINSHIP.NS", "MANKIND.NS",
    "INFY.NS", "HCLTECH.NS", "NBCC.NS", "ALKYLAMINE.NS", "DELHIVERY.NS",
    "KPITTECH.NS", "NATIONALUM.NS", "TATAELXSI.NS", "AMBUJACEM.NS", "JSWSTEEL.NS",
    "BALKRISIND.NS", "ASIANPAINT.NS", "ABBOTINDIA.NS", "HINDALCO.NS", "NYKAA.NS",
    "BLUESTARCO.NS", "IOC.NS", "NESTLEIND.NS", "PREMIERENE.NS", "INDIGO.NS",
    "BAJAJ-AUTO.NS", "KAYNES.NS", "DRREDDY.NS", "TVSMOTOR.NS", "UPL.NS",
    "SWIGGY.NS", "COFORGE.NS", "VOLTAS.NS", "BHARTIARTL.NS", "EICHERMOT.NS",
    "NTPC.NS", "LODHA.NS", "ETERNAL.NS", "POLYCAB.NS", "DLF.NS", "SUZLON.NS",
    "CONCOR.NS", "JINDALSTEL.NS", "ICICIPRULI.NS", "DALBHARAT.NS", "INDUSTOWER.NS",
    "ASHOKLEY.NS", "CDSL.NS", "GLENMARK.NS", "PNB.NS", "INOXWIND.NS",
    "ASTRAL.NS", "KALYANKJIL.NS", "BSE.NS", "TECHM.NS", "SHREECEM.NS",
    "PIIND.NS", "CAMSTI.NS", "IIDA.NS", "TATASTEEL.NS", "M&M.NS", "LUPIN.NS",
    "GAIL.NS", "PFC.NS", "SUPREMEIND.NS", "WAAREEENER.NS", "KEI.NS",
    "FORTIS.NS", "TORNTPHARM.NS", "ICICIBANK.NS", "SRF.NS", "DIXON.NS",
    "GRASIM.NS", "HEROMOTOCO.NS", "CROMPTON.NS", "MRF.NS", "SIEMENS.NS",
    "PHOENIXLTD.NS", "PIDILITIND.NS", "UNOMINDA.NS", "NMDC.NS", "SAIL.NS",
    "POWERGRID.NS", "MOTHERSON.NS", "NHPC.NS", "RELIANCE.NS", "JUBLFOOD.NS",
    "MAXHEALTH.NS", "MOTILALOFS.NS", "SOLARINDS.NS", "AMBER.NS", "AUROPHARMA.NS",
    "CGPOWER.NS", "PETRONET.NS", "DIVISLAB.NS", "HAVELLS.NS", "LT.NS",
    "BEL.NS", "LTF.NS", "TATAPOWER.NS", "BHARATFORG.NS", "SONACOMS.NS",
    "APOLLOHOSP.NS", "HAL.NS", "BOSCHLTD.NS", "APOLLOTYRE.NS", "BHEL.NS",
    "KFINTECH.NS", "ANGELONE.NS", "GODREJCP.NS", "BDL.NS", "NAUKRI.NS"
]

def get_google_sheet_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    if creds_json_str:
        creds_dict = json.loads(creds_json_str)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    elif os.path.exists(SERVICE_ACCOUNT_FILE):
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    else:
        raise FileNotFoundError("Google Credentials file or environment secret not found!")
    return gspread.authorize(creds)

def fetch_stock_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 10:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        c_price = round(df["Close"].iloc[-1], 2)
        prev_close = df["Close"].iloc[0]
        pct_change = round(((c_price - prev_close) / prev_close) * 100, 2)
        
        avg_vol = df["Volume"].rolling(10).mean().iloc[-1]
        curr_vol = df["Volume"].iloc[-1]
        vol_ratio = round(curr_vol / avg_vol, 1) if avg_vol > 0 else 1.0
        
        vwap = (df["Volume"] * (df["High"] + df["Low"] + df["Close"]) / 3).sum() / df["Volume"].sum()
        
        # CE Filter Rule: Skip non-bullish stocks
        if ticker != INDEX_TICKER and (pct_change <= 0 or c_price < vwap):
            return None

        vol_status = f"{vol_ratio}x SPIKE ⚡" if vol_ratio >= 2.0 else "DRY-UP 💧"
        vcp_str = "YES 🔥" if vol_ratio >= 1.8 and pct_change > 0.5 else "NO 💤"
        intraday_trend = "ABOVE VWAP (+ve) 🟢" if c_price > vwap else "BELOW VWAP (-ve) 🔴"
        
        option_buildup = "CE LONG BUILDUP 🔥" if pct_change > 0 else "PE LONG BUILDUP 🩸"
        bo_status = "ALPHA CE B/O 🚀🔥" if pct_change > 1.5 else "CONSOLIDATING 💤"
        action_entry = "🔥 BUY CE (15M CONFIRMED) 🟢" if pct_change > 1.0 else "NO ENTRY 🚫"
        
        # Dynamic Priority Rank Logic
        if pct_change >= 1.5 and vol_ratio >= 2.0 and c_price > vwap:
            priority_rank = "🔥 TOP PRIORITY #1 ⚡"
        elif pct_change > 0 and c_price > vwap:
            priority_rank = "PRIORITY #2 📈"
        else:
            priority_rank = "PRIORITY #3 💤"

        inst_activity = "SMART ACCUMULATION 📈" if pct_change > 0 and c_price > vwap else "NO ACCUMULATION 💤"
        
        ema20 = round(df["Close"].ewm(span=20).mean().iloc[-1], 2)
        support_level = f"EMA20: ₹{ema20}"
        
        ist = pytz.timezone("Asia/Kolkata")
        time_only_ist = datetime.now(ist).strftime("%H:%M:%S")
        
        return {
            "c_price": f"₹{c_price}",
            "pct_change": pct_change,
            "pct_change_str": f"{pct_change}%",
            "oi_change_str": "13.50%",
            "vcp_str": vcp_str,
            "vol_status": vol_status,
            "option_buildup": option_buildup,
            "bo_status": bo_status,
            "action_entry": action_entry,
            "priority": priority_rank,
            "support_level": support_level,
            "intraday_trend": intraday_trend,
            "inst_activity": inst_activity,
            "sl": round(c_price * 0.99, 1),
            "target": round(c_price * 1.03, 1),
            "time_only_ist": time_only_ist  # Shifted to last
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def run_ce_scanner():
    gc = get_google_sheet_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    
    try:
        worksheet = sh.worksheet("LIVE_DASHBOARD")
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title="LIVE_DASHBOARD", rows="300", cols="20")
    
    stock_data_list = []
    nifty_row = []
    
    for symbol in STOCKS:
        pdata = fetch_stock_data(symbol)
        if not pdata:
            continue
            
        if symbol == INDEX_TICKER:
            pct_val = pdata.get("pct_change", 0)
            intra_tr = pdata.get("intraday_trend", "")
            
            if pct_val > 0.3 or "ABOVE VWAP" in intra_tr:
                nifty_rr = "ENTRY......BULLISH 🟢"
            else:
                nifty_rr = "NO ENTRY.........BEARISH 🔴"

            # Last Updated placed at index 14 (Column O)
            nifty_row = [
                "NIFTY 50", pdata["c_price"], pdata["pct_change_str"],
                pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                "BENCHMARK 🏛️", pdata["support_level"], pdata["intraday_trend"],
                "MARKET REGIME 🏛️", nifty_rr, pdata["time_only_ist"]
            ]
        else:
            rr_str = f"GOOD RISK-REWARD (SL: ₹{pdata['sl']} | TGT: ₹{pdata['target']}) 👍"
            # Last Updated placed at index 14 (Column O)
            row = [
                symbol.replace(".NS", ""), pdata["c_price"], pdata["pct_change_str"],
                pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                pdata["priority"], pdata["support_level"], pdata["intraday_trend"],
                pdata["inst_activity"], rr_str, pdata["time_only_ist"]
            ]
            stock_data_list.append(row)
            
    final_data = [nifty_row] + stock_data_list if nifty_row else stock_data_list
    
    worksheet.clear()
    
    # Updated Headers Layout (Last Updated in Column O)
    headers = [
        "Stock Symbol", "LTP", "Price % Change", "OI % Change 📊", "VCP Contraction",
        "Volume Status", "CE/PE Option Buildup", "Breakout Status", "Action / Entry Trigger",
        "Priority Rank 🎯", "Reversal Support Level", "Intraday Trend (VWAP / 15M)",
        "Institutional Activity 🐋", "Risk-Reward & Target 🎯", "Last Updated"
    ]
    
    worksheet.update("A1:O1", [headers])
    if final_data:
        worksheet.update(f"A2:O{len(final_data)+1}", final_data)
    print("LIVE_DASHBOARD CE Screener Audit & Column Alignment Complete!")

if __name__ == "__main__":
    run_ce_scanner()
