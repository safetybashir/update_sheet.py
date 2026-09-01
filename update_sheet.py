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
# SECTION 1: GOOGLE SHEETS AUTH & TAB UPDATER
# ==========================================
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
        raise FileNotFoundError("Neither 'GOOGLE_CREDS' env var nor 'credentials.json' was found!")

def update_ce_tab(spreadsheet, df):
    tab_name = "NEW OI_VCP B/O DASHBOARD"
    headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "CE Action", "Trigger CE", "Change %", "Last Updated"]
    
    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="10")
            
        worksheet.clear()
        
        if not df.empty:
            df_ce = df.copy()
            df_ce["CE Action"] = "BUY CE 🚀"
            df_ce["Trigger CE"] = df_ce["LTP"].apply(lambda x: f"BUY>{round(float(x) * 1.002, 2)}")
            
            df_clean = df_ce[headers].copy().fillna("").replace([np.inf, -np.inf], "")
            for col in headers:
                df_clean[col] = df_clean[col].astype(str)

            data_to_write = [headers] + df_clean.values.tolist()
            worksheet.update(range_name='A1', values=data_to_write, value_input_option='RAW')
            print(f"✅ CE Tab Updated: {tab_name} ({len(df_clean)} rows written)")
        else:
            ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
            default_row = [["NONE", "NO_BREAKOUT", "0.0", "0.0", "0.0", "NO TRADE 🚫", "N/A", "0.0", str(ist_time)]]
            worksheet.update(range_name='A1', values=[headers] + default_row, value_input_option='RAW')
            print(f"⚠️ CE Tab Updated with Default State.")
            
    except Exception as e:
        print(f"❌ Failed to update CE Tab ({tab_name}): {e}")

def update_pe_tab(spreadsheet, df):
    tab_name = "LIVE_PE_DASHBOARD"
    headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "PE Action", "Trigger PE", "Change %", "Last Updated"]
    
    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="10")
            
        worksheet.clear()
        
        if not df.empty:
            df_pe = df.copy()
            df_pe["PE Action"] = "BUY PE 🚨"
            df_pe["Trigger PE"] = df_pe["LTP"].apply(lambda x: f"SELL<{round(float(x) * 0.998, 2)}")
            
            df_clean = df_pe[headers].copy().fillna("").replace([np.inf, -np.inf], "")
            for col in headers:
                df_clean[col] = df_clean[col].astype(str)

            data_to_write = [headers] + df_clean.values.tolist()
            worksheet.update(range_name='A1', values=data_to_write, value_input_option='RAW')
            print(f"✅ PE Tab Updated: {tab_name} ({len(df_clean)} rows written)")
        else:
            ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
            default_row = [["NONE", "NO_BREAKOUT", "0.0", "0.0", "0.0", "NO TRADE 🚫", "N/A", "0.0", str(ist_time)]]
            worksheet.update(range_name='A1', values=[headers] + default_row, value_input_option='RAW')
            print(f"⚠️ PE Tab Updated with Default State.")
            
    except Exception as e:
        print(f"❌ Failed to update PE Tab ({tab_name}): {e}")

# ==========================================
# SECTION 2: HEAVYWEIGHTS & FNO SYMBOLS
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
# SECTION 3: 7-POINT DATA ENGINE
# ==========================================
def fetch_and_process_data():
    raw_stocks_data = []
    ist = pytz.timezone('Asia/Kolkata')
    current_time_str = datetime.now(ist).strftime('%H:%M:%S')

    for sym in FNO_SYMBOLS:
        try:
            yf_ticker = "^NSEI" if sym == "NIFTY" else f"{sym}.NS"
            data = yf.download(yf_ticker, period="1d", interval="5m", progress=False)
            
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
            
            price_up = change_pct > 0.2
            vol_up = vol_spike > 1.2
            
            score_points = 0
            if price_up: score_points += 20
            if vol_up: score_points += 20
            if ltp > latest['VWAP']: score_points += 15
            
            max_20 = data['High'].tail(20).iloc[:-1].max() if len(data) >= 20 else data['High'].max()
            if ltp > max_20: score_points += 15
            
            if price_up and vol_up: score_points += 15
            if sym in HEAVYWEIGHTS or sym == "NIFTY": score_points += 15

            hw_weight = 1.25 if (sym in HEAVYWEIGHTS or sym == "NIFTY") else 1.0
            final_score = min(100.0, round(score_points * hw_weight, 1))

            if final_score >= 60 and change_pct > 0:
                trend = 'UPTREND'
            elif final_score <= 30 or change_pct < -0.3:
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
    
    if df_all.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_ce = df_all[df_all['Trend'] == 'UPTREND'].sort_values(by=['Score', 'Change %'], ascending=[False, False])
    df_pe = df_all[df_all['Trend'] == 'DOWNTREND'].sort_values(by=['Score', 'Change %'], ascending=[False, True])

    if df_ce.empty:
        df_ce = df_all.sort_values(by='Change %', ascending=False).head(15)
    if df_pe.empty:
        df_pe = df_all.sort_values(by='Change %', ascending=True).head(15)

    return df_ce, df_pe

# ==========================================
# SECTION 4: MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("🚀 7-Point Options F&O Engine Active - Processing Data...")
    
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        print(f"[⏱️ Execution Time: {now.strftime('%H:%M:%S IST')}] Fetching Market Data...")

        df_ce, df_pe = fetch_and_process_data()
        
        print(f"📊 Processed Signals - CE Rows: {len(df_ce)} | PE Rows: {len(df_pe)}")

        sheet_id = os.environ.get("SHEET_ID")
        if not sheet_id:
            # Fallback check if env var is missing
            print("⚠️ SHEET_ID env var missing. Searching for SHEET_ID...")
            
        if sheet_id:
            gc = get_gspread_client()
            sh = gc.open_by_key(sheet_id)

            update_ce_tab(sh, df_ce)
            update_pe_tab(sh, df_pe)
            
            print("🎉 Sheet update process completed!")
        else:
            print("❌ CRITICAL ERROR: SHEET_ID environment variable is missing in terminal session!")

    except Exception as err:
        print(f"❌ Execution Error: {err}")
