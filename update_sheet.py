import os
import json
import time
import sys
import requests
from datetime import datetime
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# SECTION 1: GOOGLE SHEETS AUTH & DATA WRITER
# ==========================================
SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg" 

def get_gspread_client():
    creds_json = os.environ.get("GOOGLE_CREDS") or os.environ.get("GCP_CREDENTIALS_JSON")
    
    if creds_json:
        creds_dict = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json")
    else:
        raise FileNotFoundError("❌ 'credentials.json' file nahi mili! File check karein.")

def write_data_safely(worksheet, headers, rows_data):
    """Guarantees physical sheet override and updates timestamps without gspread silent-skip"""
    full_matrix = [headers] + rows_data
    worksheet.clear()
    
    num_rows = len(full_matrix)
    num_cols = len(headers)
    
    # Convert column index to sheet range letter (e.g., A1:I15)
    col_letter = chr(64 + num_cols)
    cell_range = f"A1:{col_letter}{num_rows}"
    
    worksheet.update(values=full_matrix, range_name=cell_range)

# ==========================================
# SECTION 2: CE & PE TAB UPDATERS (CORRECTED LOGIC)
# ==========================================
def update_ce_tab(spreadsheet, df_all):
    tab_name = "NEW OI_VCP B/O DASHBOARD"
    headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "CE Action", "Trigger CE", "Change %", "Last Updated"]
    ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')

    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="9")
            
        # STRICT FILTER: Only UPTREND stocks belong in CE Dashboard
        if not df_all.empty:
            df_ce = df_all[df_all['Trend'] == 'UPTREND'].sort_values(by=['Score', 'Change %'], ascending=[False, False]).copy()
        else:
            df_ce = pd.DataFrame()

        if not df_ce.empty:
            df_ce["CE Action"] = "BUY CE 🚀"
            df_ce["Trigger CE"] = df_ce["LTP"].apply(lambda x: f"BUY>{round(float(x) * 1.002, 2)}")
            
            df_clean = df_ce[headers].copy().fillna("").replace([np.inf, -np.inf], "")
            for col in headers:
                df_clean[col] = df_clean[col].astype(str)

            rows_to_write = df_clean.values.tolist()
            write_data_safely(worksheet, headers, rows_to_write)
            print(f"✅ CE Tab Updated: {len(rows_to_write)} UPTREND stocks written at {ist_time}")
        else:
            # Fallback output so Sheet time changes even if no stock is in pure UPTREND
            fallback = [["N/A", "NO_UPTREND", "0.0", "0.0", "0.0", "NO TRADE 🚫", "N/A", "0.0", str(ist_time)]]
            write_data_safely(worksheet, headers, fallback)
            print(f"⚠️ CE Tab Updated: No UPTREND stocks found at {ist_time}")
            
    except Exception as e:
        print(f"❌ CE Tab Update Error: {e}")

def update_pe_tab(spreadsheet, df_all):
    tab_name = "LIVE_PE_DASHBOARD"
    headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "PE Action", "Trigger PE", "Change %", "Last Updated"]
    ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')

    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="9")
            
        # STRICT FILTER: Only DOWNTREND stocks belong in PE Dashboard
        if not df_all.empty:
            df_pe = df_all[df_all['Trend'] == 'DOWNTREND'].sort_values(by=['Score', 'Change %'], ascending=[True, True]).copy()
        else:
            df_pe = pd.DataFrame()

        if not df_pe.empty:
            df_pe["PE Action"] = "BUY PE 🚨"
            df_pe["Trigger PE"] = df_pe["LTP"].apply(lambda x: f"SELL<{round(float(x) * 0.998, 2)}")
            
            df_clean = df_pe[headers].copy().fillna("").replace([np.inf, -np.inf], "")
            for col in headers:
                df_clean[col] = df_clean[col].astype(str)

            rows_to_write = df_clean.values.tolist()
            write_data_safely(worksheet, headers, rows_to_write)
            print(f"✅ PE Tab Updated: {len(rows_to_write)} DOWNTREND stocks written at {ist_time}")
        else:
            # Fallback output so Sheet time changes even if no stock is in pure DOWNTREND
            fallback = [["N/A", "NO_DOWNTREND", "0.0", "0.0", "0.0", "NO TRADE 🚫", "N/A", "0.0", str(ist_time)]]
            write_data_safely(worksheet, headers, fallback)
            print(f"⚠️ PE Tab Updated: No DOWNTREND stocks found at {ist_time}")
            
    except Exception as e:
        print(f"❌ PE Tab Update Error: {e}")

# ==========================================
# SECTION 3: SYMBOL LISTS
# ==========================================
HEAVYWEIGHTS = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "LT", "AXISBANK", "SBIN", "BHARTIARTL", "ITC"]

FNO_SYMBOLS = [
    "NIFTY", "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC", "ADANIENT", "ADANIPORTS",
    "ALKEM", "AMBUJACEM", "APOLLOHOSP", "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL",
    "ATUL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE",
    "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA", "BATAINDIA", "BEL", "BERGEPAINT",
    "BHARATFORG", "BHARTIARTL", "BHEL", "BIOCON", "BSOFT", "BPCL", "BRITANNIA", "CANBK",
    "CANFINHOME", "CHAMBLFERT", "CHOLAFIN", "CIPLA", "COALINDIA", "COFORGE", "COLPAL",
    "CONCOR", "COROMANDEL", "CROMPTON", "CUB", "CUMMINSIND", "DABUR", "DALBHARAT", "DEEPAKNTR",
    "DIVISLAB", "DIXON", "DLF", "DRREDDY", "EICHERMOT", "ESCORTS", "EXIDEIND", "FEDERALBNK",
    "GAIL", "GLENMARK", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES", "GRASIM",
    "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "ICICIBANK", "ICICIGI", "ICICIPRULI",
    "IDEA", "IDFCFIRSTB", "IEX", "IGL", "INDHOTEL", "INDIACEM", "INDIAMART",
    "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFY", "IOC", "IPCALAB", "IRCTC", "ITC",
    "JINDALSTEL", "JKCEMENT", "JSWSTEEL", "JUBLFOOD", "KOTAKBANK", "LALPATHLAB", "LAURUSLABS",
    "LICHSGFIN", "LT", "LUPIN", "M&M", "M&MFIN", "MANAPPURAM", "MARICO",
    "MARUTI", "MCX", "METROPOLIS", "MFSL", "MGL", "MOTHERSON", "MPHASIS",
    "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI", "NAVINFLUOR", "NESTLEIND", "NMDC", "NTPC",
    "OBEROIRLTY", "OFSS", "ONGC", "PAGEIND", "PERSISTENT", "PETRONET", "PFC", "PIDILITIND",
    "PIIND", "PNB", "POLYCAB", "POWERGRID", "PVRINOX", "RAMCOCEM", "RBLBANK", "RECLTD",
    "RELIANCE", "SAIL", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS",
    "SRF", "SUNPHARMA", "SUNTV", "SYNGENE", "TATACHEM", "TATACONSUM", "TATAELXSI",
    "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM",
    "TRENT", "TVSMOTOR", "UBL", "ULTRACEMCO", "UPL", "VEDL", "VOLTAS", "WIPRO", "ZEEL"
]

# ==========================================
# SECTION 4: DATA PROCESSING ENGINE
# ==========================================
def fetch_and_process_data():
    raw_stocks_data = []
    ist = pytz.timezone('Asia/Kolkata')
    current_time_str = datetime.now(ist).strftime('%H:%M:%S')

    print(f"🔍 Fetching live quotes for target symbols...")
    
    # Batch download processing
    for sym in FNO_SYMBOLS[:40]:  # Adjust slice size if needed
        try:
            yf_ticker = "^NSEI" if sym == "NIFTY" else f"{sym}.NS"
            data = yf.download(yf_ticker, period="5d", interval="5m", progress=False)
            
            if data.empty or len(data) < 2:
                continue
                
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0] for col in data.columns]
                
            data['VWAP'] = (data['Volume'] * (data['High'] + data['Low'] + data['Close']) / 3).cumsum() / data['Volume'].cumsum()
            
            latest = data.iloc[-1]
            prev = data.iloc[-2]
            
            ltp = float(latest['Close'])
            prev_close = float(prev['Close'])
            change_pct = ((ltp - prev_close) / prev_close) * 100
            
            avg_vol = data['Volume'].tail(20).mean()
            curr_vol = float(latest['Volume'])
            vol_spike = curr_vol / avg_vol if avg_vol > 0 else 1.0
            
            price_up = change_pct > 0.15
            vol_up = vol_spike > 1.2
            
            score_points = 0
            if price_up: score_points += 25
            if vol_up: score_points += 25
            if ltp > latest['VWAP']: score_points += 15
            
            max_20 = data['High'].tail(20).iloc[:-1].max() if len(data) >= 20 else data['High'].max()
            if ltp > max_20: score_points += 15
            
            if price_up and vol_up: score_points += 10
            if sym in HEAVYWEIGHTS or sym == "NIFTY": score_points += 10

            hw_weight = 1.2 if (sym in HEAVYWEIGHTS or sym == "NIFTY") else 1.0
            final_score = min(100.0, round(score_points * hw_weight, 1))

            # ACCURATE TREND ASSIGNMENT
            if final_score >= 55 and change_pct > 0.1:
                trend = 'UPTREND'
            elif final_score <= 35 or change_pct < -0.1:
                trend = 'DOWNTREND'
            else:
                trend = 'SIDEWAYS'

            raw_stocks_data.append({
                'Symbol': str(sym),
                'Trend': str(trend),
                'Vol Spike': round(float(vol_spike), 2),
                'LTP': round(float(ltp), 2),
                'Score': float(final_score),
                'Change %': round(float(change_pct), 2),
                'Last Updated': current_time_str
            })

        except Exception:
            continue

    df_all = pd.DataFrame(raw_stocks_data)
    return df_all

# ==========================================
# SECTION 5: MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("🚀 Connecting to Google Sheets...")
    
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        print(f"✅ Connected to Sheet: {sh.title}")

        print("📊 Processing Stock Market Feed...")
        df_all = fetch_and_process_data()

        print("🔄 Writing CE Dashboard...")
        update_ce_tab(sh, df_all)

        print("🔄 Writing PE Dashboard...")
        update_pe_tab(sh, df_all)
        
        print("🎉 Live Sheet Update Completed Successfully!")

    except Exception as err:
        print(f"\n❌ SCRIPT ERROR: {err}")
