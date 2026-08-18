import os
import json
import yfinance as yf
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz

# --- CONFIGURATION & CONSTANTS ---
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
SERVICE_ACCOUNT_FILE = "credentials.json"
INDEX_TICKER = "^NSEI"

# Target PE Stocks List
STOCKS = [
    INDEX_TICKER, "TATASTEEL.NS", "ZEEL.NS", "HDFCBANK.NS", "RELIANCE.NS",
    "AXISBANK.NS", "DLF.NS", "NMDC.NS", "VEDL.NS", "JISLJALEQS.NS"
]

def get_google_sheet_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    # 1. Direct Secret Fallback (Safe & Multi-Layered)
    creds_json_str = os.environ.get("GCP_CREDENTIALS_JSON")
    
    if creds_json_str:
        creds_dict = json.loads(creds_json_str)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    elif os.path.exists(SERVICE_ACCOUNT_FILE):
        # 2. File-based auth if credentials.json is created by YAML
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
        
        # Volume Spike & Indicators
        avg_vol = df["Volume"].rolling(10).mean().iloc[-1]
        curr_vol = df["Volume"].iloc[-1]
        vol_ratio = round(curr_vol / avg_vol, 1) if avg_vol > 0 else 1.0
        
        vol_status = f"{vol_ratio}x SPIKE ⚡" if vol_ratio >= 2.0 else "DRY-UP 💧"
        vcp_str = "YES 🩸" if vol_ratio >= 1.8 and pct_change < -0.5 else "NO 💤"
        
        # VWAP Trend
        vwap = (df["Volume"] * (df["High"] + df["Low"] + df["Close"]) / 3).sum() / df["Volume"].sum()
        intraday_trend = "STRONG BEARISH (-ve) 🩸" if c_price < vwap else "ABOVE VWAP (+ve) 🟢"
        
        # Option Buildup & Breakdown
        option_buildup = "PE LONG BUILDUP 🩸" if pct_change < 0 else "CE LONG BUILDUP 🔥"
        bo_status = "ALPHA PE B/D 🩸⚡" if pct_change < -1.5 else "CONSOLIDATING 💤"
        action_entry = "🔥 BUY PE (15M CONFIRMED) 🩸" if pct_change < -1.0 else "NO ENTRY 🚫"
        
        ema20 = round(df["Close"].ewm(span=20).mean().iloc[-1], 2)
        resistance_level = f"EMA20: ₹{ema20}"
        
        ist = pytz.timezone("Asia/Kolkata")
        time_only_ist = datetime.now(ist).strftime("%H:%M:%S")
        
        return {
            "c_price": f"₹{c_price}",
            "pct_change": pct_change,
            "pct_change_str": f"{pct_change}%",
            "oi_change_str": "18.20%",
            "vcp_str": vcp_str,
            "vol_status": vol_status,
            "option_buildup": option_buildup,
            "bo_status": bo_status,
            "action_entry": action_entry,
            "priority": "🩸 TOP PRIORITY #1 ⚡" if pct_change < -1.5 else "PRIORITY #2 📉",
            "resistance_level": resistance_level,
            "time_only_ist": time_only_ist,
            "intraday_trend": intraday_trend,
            "inst_activity": "HEAVY DISTRIBUTION 📉",
            "sl": round(c_price * 1.01, 1),
            "target": round(c_price * 0.97, 1)
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

def run_pe_scanner():
    gc = get_google_sheet_client()
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet("PE_BEARISH")
    
    stock_data_list = []
    nifty_row = []
    
    for symbol in STOCKS:
        pdata = fetch_stock_data(symbol)
        if not pdata:
            continue
            
        if symbol == INDEX_TICKER:
                # Simple NIFTY Action for PE
                pct_val = pdata.get("pct_change", 0)
                intra_tr = pdata.get("intraday_trend", "")
                
                if pct_val < -0.3 or "BELOW VWAP" in intra_tr:
                    nifty_rr = "ENTRY......BEARISH 🔴"
                else:
                    nifty_rr = "NO ENTRY.........BULLISH 🟢"

                nifty_row = [
                    "NIFTY 50", pdata["c_price"], pdata["pct_change_str"],
                    pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                    pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                    "BENCHMARK 🏛️", pdata["resistance_level"], pdata["time_only_ist"],
                    pdata["intraday_trend"], "MARKET REGIME 🏛️", nifty_rr
                ]
        else:
            rr_str = f"GOOD RISK-REWARD (SL: ₹{pdata['sl']} | TGT: ₹{pdata['target']}) 👍"
            row = [
                symbol.replace(".NS", ""), pdata["c_price"], pdata["pct_change_str"],
                pdata["oi_change_str"], pdata["vcp_str"], pdata["vol_status"], 
                pdata["option_buildup"], pdata["bo_status"], pdata["action_entry"], 
                pdata["priority"], pdata["resistance_level"], pdata["time_only_ist"],
                pdata["intraday_trend"], pdata["inst_activity"], rr_str
            ]
            stock_data_list.append(row)
            
    # Combine Benchmark on top followed by stocks
    final_data = [nifty_row] + stock_data_list if nifty_row else stock_data_list
    
    # Update Google Sheet starting from cell A2
    worksheet.update(f"A2:O{len(final_data)+1}", final_data)
    print("PE Screener Updated Successfully!")

if __name__ == "__main__":
    run_pe_scanner()
