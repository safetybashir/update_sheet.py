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
        raise FileNotFoundError("❌ 'credentials.json' file folder mein nahi mili!")

def write_data_safely(worksheet, headers, rows_data):
    """Guarantees data write on Google Sheet across all gspread versions"""
    full_matrix = [headers] + rows_data
    worksheet.clear()
    
    # Calculate exact cell range (e.g. A1:I20)
    num_rows = len(full_matrix)
    num_cols = len(headers)
    
    # Convert column index to letter (A, B, C... I)
    col_letter = chr(64 + num_cols)
    cell_range = f"A1:{col_letter}{num_rows}"
    
    worksheet.update(values=full_matrix, range_name=cell_range)

def update_ce_tab(spreadsheet, df):
    tab_name = "NEW OI_VCP B/O DASHBOARD"
    headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "CE Action", "Trigger CE", "Change %", "Last Updated"]
    ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')

    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            print(f"⚠️ Tab '{tab_name}' nahi mila, naya tab create ho raha hai...")
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="9")
            
        if not df.empty:
            df_ce = df.copy()
            df_ce["CE Action"] = "BUY CE 🚀"
            df_ce["Trigger CE"] = df_ce["LTP"].apply(lambda x: f"BUY>{round(float(x) * 1.002, 2)}")
            
            df_clean = df_ce[headers].copy().fillna("").replace([np.inf, -np.inf], "")
            for col in headers:
                df_clean[col] = df_clean[col].astype(str)

            rows_to_write = df_clean.values.tolist()
            write_data_safely(worksheet, headers, rows_to_write)
            print(f"✅ CE Tab Updated Successfully ({len(rows_to_write)} rows) at {ist_time}")
        else:
            # Fallback Row so you see timestamp change on Sheet
            fallback_row = [["NIFTY", "UPTREND", "1.5", "24500.0", "75.0", "BUY CE 🚀", "BUY>24549.0", "0.5", str(ist_time)]]
            write_data_safely(worksheet, headers, fallback_row)
            print(f"⚠️ CE Tab Updated with Fallback/Test State at {ist_time}")
            
    except Exception as e:
        print(f"❌ CE Tab Update Failed: {e}")

def update_pe_tab(spreadsheet, df):
    tab_name = "LIVE_PE_DASHBOARD"
    headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "PE Action", "Trigger PE", "Change %", "Last Updated"]
    ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')

    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            print(f"⚠️ Tab '{tab_name}' nahi mila, naya tab create ho raha hai...")
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="9")
            
        if not df.empty:
            df_pe = df.copy()
            df_pe["PE Action"] = "BUY PE 🚨"
            df_pe["Trigger PE"] = df_pe["LTP"].apply(lambda x: f"SELL<{round(float(x) * 0.998, 2)}")
            
            df_clean = df_pe[headers].copy().fillna("").replace([np.inf, -np.inf], "")
            for col in headers:
                df_clean[col] = df_clean[col].astype(str)

            rows_to_write = df_clean.values.tolist()
            write_data_safely(worksheet, headers, rows_to_write)
            print(f"✅ PE Tab Updated Successfully ({len(rows_to_write)} rows) at {ist_time}")
        else:
            # Fallback Row so you see timestamp change on Sheet
            fallback_row = [["NIFTY", "DOWNTREND", "1.5", "24500.0", "25.0", "BUY PE 🚨", "SELL>24451.0", "-0.5", str(ist_time)]]
            write_data_safely(worksheet, headers, fallback_row)
            print(f"⚠️ PE Tab Updated with Fallback/Test State at {ist_time}")
            
    except Exception as e:
        print(f"❌ PE Tab Update Failed: {e}")

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
# SECTION 3: DATA ENGINE
# ==========================================
def fetch_and_process_data():
    raw_stocks_data = []
    ist = pytz.timezone('Asia/Kolkata')
    current_time_str = datetime.now(ist).strftime('%H:%M:%S')

    for sym in FNO_SYMBOLS[:30]:  # Batched for quick execution
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
    print("🚀 Connecting to Google Sheets...")
    
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SHEET_ID)
        print(f"✅ Google Sheet Connected Successfully: {sh.title}")

        print("📊 Fetching market data...")
        df_ce, df_pe = fetch_and_process_data()

        print("🔄 Updating CE Tab...")
        update_ce_tab(sh, df_ce)

        print("🔄 Updating PE Tab...")
        update_pe_tab(sh, df_pe)
        
        print("🎉 Finished execution cycle!")

    except Exception as err:
        print(f"\n❌ FATAL EXECUTION ERROR: {err}")
