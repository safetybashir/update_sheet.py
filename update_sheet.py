import os
import json
import time
import sys
from datetime import datetime
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# SECTION 1: GOOGLE SHEETS AUTH HELPER
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

def update_tab(spreadsheet, df, tab_name):
    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="20")
            
        # Complete clear to remove ghost columns
        worksheet.clear()
        
        headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "CE Action", "PE Action", "Trigger CE", "Trigger PE", "Change %", "Last Updated"]
        
        if not df.empty:
            # Re-index to ensure exact 11 columns in strict order
            df_clean = df.reindex(columns=headers).fillna("").replace([np.inf, -np.inf], "")
            data_to_write = [headers] + df_clean.values.tolist()
            
            # Write explicitly using user_entered to prevent string concatenation
            worksheet.update(range_name='A1', values=data_to_write, value_input_option='USER_ENTERED')
            print(f"✅ Successfully updated tab: {tab_name} ({len(df_clean)} rows)")
        else:
            default_row = [["NONE", "NO_BREAKOUT", 0, 0, 0, "NO TRADE 🚫", "NO TRADE 🚫", "VOL SPIKE", "VOL SPIKE", 0, datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')]]
            worksheet.update(range_name='A1', values=[headers] + default_row, value_input_option='USER_ENTERED')
            print(f"⚠️ Tab {tab_name} updated with default 'No Signals' state.")
            
    except Exception as e:
        print(f"❌ Failed to update tab {tab_name}: {e}")

# ==========================================
# SECTION 2: CLEANED FNO SYMBOLS
# ==========================================
FNO_SYMBOLS = [
    "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC", "ADANIENT", "ADANIPORTS",
    "ALKEM", "AMBUJACEM", "APOLLOHOSP", "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL",
    "ATUL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE",
    "BALKRISIND", "BALRAMCHIN", "BANDHANBNK", "BANKBARODA", "BATAINDIA", "BEL", "BERGEPAINT",
    "BHARATFORG", "BHARTIARTL", "BHEL", "BIOCON", "BSOFT", "BPCL", "BRITANNIA", "CANBK",
    "CANFINHOME", "CHAMBLFERT", "CHOLAFIN", "CIPLA", "COALINDIA", "COFORGE", "COLPAL",
    "CONCOR", "COROMANDEL", "CROMPTON", "CUB", "CUMMINSIND", "DABUR", "DALBHARAT", "DEEPAKNTR",
    "DIVISLAB", "DIXON", "DLF", "DRREDDY", "EICHERMOT", "ESCORTS", "EXIDEIND", "FEDERALBNK",
    "GAIL", "GLENMARK", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES", "GRASIM",
    "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "ICICIBANK", "ICICIGI", "ICICIPRULI",
    "IDEA", "IDFCFIRSTB", "IEX", "IGL", "INDHOTEL", "INDIACEM", "INDIAMART",
    "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFY", "IOC", "IPCALAB", "IRCTC", "ITC",
    "JINDALSTEL", "JKCEMENT", "JSWSTEEL", "JUBLFOOD", "KOTAKBANK", "LALPATHLAB", "LAURUSLABS",
    "LICHSGFIN", "LT", "LTIM", "LTF", "LUPIN", "M&M", "M&MFIN", "MANAPPURAM", "MARICO",
    "MARUTI", "UNITDSPR", "MCX", "METROPOLIS", "MFSL", "MGL", "MOTHERSON", "MPHASIS",
    "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI", "NAVINFLUOR", "NESTLEIND", "NMDC", "NTPC",
    "OBEROIRLTY", "OFSS", "ONGC", "PAGEIND", "PERSISTENT", "PETRONET", "PFC", "PIDILITIND",
    "PIIND", "PNB", "POLYCAB", "POWERGRID", "PVRINOX", "RAMCOCEM", "RBLBANK", "RECLTD",
    "RELIANCE", "SAIL", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS",
    "SRF", "SUNPHARMA", "SUNTV", "SYNGENE", "TATACHEM", "TATACONSUM", "TATAELXSI",
    "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM",
    "TRENT", "TVSMOTOR", "UBL", "ULTRACEMCO", "UPL", "VEDL", "VOLTAS", "WIPRO", "ZEEL"
]

# ==========================================
# SECTION 3: DATA FETCHING & ANALYSIS
# ==========================================
def fetch_and_process_data():
    raw_stocks_data = []
    ist = pytz.timezone('Asia/Kolkata')
    current_time_str = datetime.now(ist).strftime('%H:%M:%S')

    for sym in FNO_SYMBOLS:
        try:
            yf_ticker = f"{sym}.NS"
            data = yf.download(yf_ticker, period="2d", interval="5m", progress=False)
            
            if data.empty or len(data) < 2:
                continue
                
            # Flatten multi-index columns if present
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0] for col in data.columns]
                
            latest_row = data.iloc[-1]
            prev_row = data.iloc[-2]
            
            stock_ltp = float(latest_row['Close'])
            prev_price = float(prev_row['Close'])
            
            avg_vol = data['Volume'].tail(10).mean()
            curr_vol = float(latest_row['Volume'])
            vol_spike = curr_vol / avg_vol if avg_vol > 0 else 1.0
            
            price_change_pct = ((stock_ltp - prev_price) / prev_price) * 100
            
            # Trend Rules
            if price_change_pct > 0.3 and vol_spike > 1.1:
                trend = 'UPTREND'
            elif price_change_pct < -0.3 and vol_spike > 1.1:
                trend = 'DOWNTREND'
            else:
                trend = 'SIDEWAYS'

            score = min(100.0, max(10.0, (abs(price_change_pct) * 20) + (vol_spike * 15)))

            raw_stocks_data.append({
                'Symbol': sym,
                'Trend': trend,
                'Vol Spike': round(vol_spike, 2),
                'LTP': round(stock_ltp, 2),
                'Score': round(score, 1),
                'CE Action': 'BUY CE 🚀' if trend == 'UPTREND' else 'NO TRADE 🚫',
                'PE Action': 'BUY PE 🚨' if trend == 'DOWNTREND' else 'NO TRADE 🚫',
                'Trigger CE': f'BUY>{round(stock_ltp * 1.002, 2)}' if trend == 'UPTREND' else 'VOL SPIKE',
                'Trigger PE': f'SELL<{round(stock_ltp * 0.998, 2)}' if trend == 'DOWNTREND' else 'VOL SPIKE',
                'Change %': round(price_change_pct, 2),
                'Last Updated': current_time_str
            })

        except Exception as e:
            continue

    df_all = pd.DataFrame(raw_stocks_data)
    
    if df_all.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Filter breakout signals
    df_ce = df_all[df_all['Trend'] == 'UPTREND'].sort_values(by='Score', ascending=False)
    df_pe = df_all[df_all['Trend'] == 'DOWNTREND'].sort_values(by='Score', ascending=False)

    # Fallback to Top Gainers/Losers
    if df_ce.empty:
        df_ce = df_all.sort_values(by='Change %', ascending=False).head(15)
    if df_pe.empty:
        df_pe = df_all.sort_values(by='Change %', ascending=True).head(15)

    return df_ce, df_pe

# ==========================================
# SECTION 4: MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("🚀 OI_VCP Engine Active - Processing Data...")
    
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        print(f"[⏱️ Execution Time: {now.strftime('%H:%M:%S IST')}] Fetching Market Data...")

        df_ce, df_pe = fetch_and_process_data()

        sheet_id = os.environ.get("SHEET_ID")
        if sheet_id:
            gc = get_gspread_client()
            sh = gc.open_by_key(sheet_id)

            update_tab(sh, df_ce, "NEW OI_VCP B/O DASHBOARD")
            update_tab(sh, df_pe, "LIVE_PE_DASHBOARD")
            
            print("🎉 Sheet update process finished successfully!")
        else:
            print("❌ ERROR: SHEET_ID Environment Variable Missing!")

    except Exception as err:
        print(f"❌ Execution Failed: {err}")
        sys.exit(1)
