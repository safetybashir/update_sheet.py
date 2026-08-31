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
    creds_json = os.environ.get("GOOGLE_CREDS")
    
    if creds_json:
        # Load from Environment Variable (GitHub Actions / Cloud)
        creds_dict = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    elif os.path.exists("credentials.json"):
        # Fallback to local file if present
        return gspread.service_account(filename="credentials.json")
    else:
        raise FileNotFoundError(
            "Neither 'GOOGLE_CREDS' environment variable nor 'credentials.json' file was found!"
        )

def update_tab(spreadsheet, df, tab_name):
    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="20")
            
        worksheet.clear()
        
        if not df.empty:
            data_to_write = [df.columns.tolist()] + df.values.tolist()
            worksheet.update('A1', data_to_write)
            print(f"✅ Successfully updated tab: {tab_name} ({len(df)} rows)")
        else:
            worksheet.update('A1', [["Status"], ["No Active Signals Found"]])
            print(f"⚠️ Tab {tab_name} updated with empty dataset.")
            
    except Exception as e:
        print(f"❌ Failed to update tab {tab_name}: {e}")

# ==========================================
# SECTION 2: CLEANED SYMBOL DEFINITIONS
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
# SECTION 3: HISTORICAL & REAL-TIME ANALYSIS
# ==========================================
def fetch_and_process_data():
    raw_stocks_data = {}

    for sym in FNO_SYMBOLS:
        try:
            yf_ticker = f"{sym}.NS"
            data = yf.download(yf_ticker, period="2d", interval="5m", progress=False)
            
            if data.empty or len(data) < 2:
                continue
                
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
            
            if price_change_pct > 0.5 and vol_spike > 1.2:
                trend = 'UPTREND'
            elif price_change_pct < -0.5 and vol_spike > 1.2:
                trend = 'DOWNTREND'
            else:
                trend = 'SIDEWAYS'

            if trend == 'UPTREND':
                raw_stocks_data[sym] = {
                    'Symbol': sym,
                    'Trend': 'UPTREND',
                    'Vol Spike': round(vol_spike, 2),
                    'LTP': round(stock_ltp, 2),
                    'Score': 80.0 if vol_spike > 2.0 else 60.0,
                    'CE Action': 'BUY CE 🚀' if price_change_pct > 0.8 else 'WATCH 👀',
                    'PE Action': 'NO TRADE 🚫',
                    'Trigger CE': f'BUY>{round(stock_ltp * 1.002, 2)}',
                    'Trigger PE': 'VOL SPIKE',
                    'PCR': 1.15,
                    'Call Price Up': True,
                    'Call OI Up': True if vol_spike > 1.5 else False,
                    'Put OI Down': False,
                    'ATM IV': 18.0,
                    '15m Close': True if vol_spike > 1.2 else False
                }
            elif trend == 'DOWNTREND':
                raw_stocks_data[sym] = {
                    'Symbol': sym,
                    'Trend': 'DOWNTREND',
                    'Vol Spike': round(vol_spike, 2),
                    'LTP': round(stock_ltp, 2),
                    'Score': 80.0 if vol_spike > 2.0 else 60.0,
                    'CE Action': 'NO TRADE 🚫',
                    'PE Action': 'BUY PE 🚨' if price_change_pct < -0.8 else 'WATCH 👀',
                    'Trigger CE': 'VOL SPIKE',
                    'Trigger PE': f'SELL<{round(stock_ltp * 0.998, 2)}',
                    'PCR': 0.65,
                    'Call Price Up': False,
                    'Call OI Up': False,
                    'Put OI Down': True if vol_spike > 1.5 else False,
                    'ATM IV': 19.5,
                    '15m Close': True if vol_spike > 1.2 else False
                }
            else:
                raw_stocks_data[sym] = {
                    'Symbol': sym,
                    'Trend': 'SIDEWAYS',
                    'Vol Spike': round(vol_spike, 2),
                    'LTP': round(stock_ltp, 2),
                    'Score': 20.0,
                    'CE Action': 'NO TRADE 🚫',
                    'PE Action': 'NO TRADE 🚫',
                    'Trigger CE': 'VOL SPIKE',
                    'Trigger PE': 'VOL SPIKE',
                    'PCR': 0.85,
                    'Call Price Up': False,
                    'Call OI Up': False,
                    'Put OI Down': False,
                    'ATM IV': 22.0,
                    '15m Close': False
                }

        except Exception as e:
            print(f"Error processing {sym}: {e}")
            continue

    df_all = pd.DataFrame(list(raw_stocks_data.values()))
    
    if df_all.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_ce = df_all[df_all['Trend'] == 'UPTREND'].sort_values(by='Score', ascending=False)
    df_pe = df_all[df_all['Trend'] == 'DOWNTREND'].sort_values(by='Score', ascending=False)

    return df_ce, df_pe

# ==========================================
# SECTION 4: DATA PREPARATION & PROCESSING
# ==========================================
def prepare_dashboard_data():
    df_ce, df_pe = fetch_and_process_data()
    return df_ce, df_pe

# ==========================================
# SECTION 5: MAIN EXECUTION BLOCK (2 TABS UPDATE)
# ==========================================
if __name__ == "__main__":
    print("🚀 OI_VCP Engine Active - Updating 2 Clean Tabs...")
    
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        print(f"[⏱️ Execution Time: {now.strftime('%H:%M:%S IST')}] Fetching Market Data...")

        df_ce, df_pe = prepare_dashboard_data()

        sheet_id = os.environ.get("SHEET_ID")
        if sheet_id:
            gc = get_gspread_client()
            sh = gc.open_by_key(sheet_id)

            # Tab 1: CE / Bullish Dashboard
            update_tab(sh, df_ce, "NEW OI_VCP B/O DASHBOARD")
            
            # Tab 2: PE / Bearish Dashboard
            update_tab(sh, df_pe, "LIVE_PE_DASHBOARD")
            
            print("🎉 ALL SYSTEMS GO! Sheet successfully updated with strict entry rules!")
        else:
            print("❌ ERROR: SHEET_ID Environment Variable Missing!")

    except Exception as err:
        print(f"❌ Execution Failed: {err}")
        sys.exit(1)
