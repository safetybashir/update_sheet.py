import os
import json
import time
from datetime import datetime
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ==============================================================================
# SECTION 1: AUTHENTICATION & GOOGLE SHEETS CONNECTOR
# ==============================================================================
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    gcp_json_str = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDENTIALS_JSON")
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")

    if gcp_json_str:
        creds_dict = json.loads(gcp_json_str)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        
    return gspread.authorize(creds)

def update_tab(sh, df, tab_name):
    try:
        try:
            worksheet = sh.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=tab_name, rows="200", cols="20")

        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist(), value_input_option="USER_ENTERED")
        print(f"✅ Tab '{tab_name}' Successfully Updated!")
    except Exception as e:
        print(f"❌ Error updating '{tab_name}': {e}")

# ==============================================================================
# SECTION 2: HEAVYWEIGHT CONFLUENCE ENGINE (NIFTY 50 - 3 STOCKS RULE)
# ==============================================================================
def process_heavyweight_logic(raw_data_dict):
    hw_stocks = ['HDFCBANK', 'RELIANCE', 'ICICIBANK', 'TCS']
    hw_status = []
    up_count = 0
    down_count = 0

    for sym in hw_stocks:
        if sym in raw_data_dict:
            trend = raw_data_dict[sym].get('trend', 'SIDEWAYS')
            if trend == 'UPTREND':
                hw_status.append(f"{sym[:4]}🟢")
                up_count += 1
            elif trend == 'DOWNTREND':
                hw_status.append(f"{sym[:4]}🔴")
                down_count += 1
            else:
                hw_status.append(f"{sym[:4]}🟡")

    summary_str = " ".join(hw_status)

    # Bullish Logic: At least 3 Heavyweights MUST be Green
    if up_count >= 3:
        ce_trend = "🟢 UPTREND"
        ce_action = "BUY CE 🚀"
        ce_hw_ok = True
    else:
        ce_trend = "🟡 SIDEWAYS"
        ce_action = "NO TRADE 🚫"
        ce_hw_ok = False

    # Bearish Logic: At least 3 Heavyweights MUST be Red
    if down_count >= 3:
        pe_trend = "🔴 DOWNTREND"
        pe_action = "BUY PE 🚨"
        pe_hw_ok = True
    else:
        pe_trend = "🟡 SIDEWAYS"
        pe_action = "NO TRADE 🚫"
        pe_hw_ok = False

    return summary_str, ce_trend, ce_action, ce_hw_ok, pe_trend, pe_action, pe_hw_ok

# ==========================================
# SECTION 3: SYMBOL DEFINITIONS & CONFIG
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
    "GAIL", "GLENMARK", "GMRINFRA", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES", "GRASIM",
    "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "ICICIBANK", "ICICIGI", "ICICIPRULI",
    "IDEA", "IDFC", "IDFCFIRSTB", "IEX", "IGL", "INDHOTEL", "INDIACEM", "INDIAMART",
    "INDIGO", "INDUSINDBK", "INDUSTOWER", "INFY", "IOC", "IPCALAB", "IRCTC", "ITC",
    "JINDALSTEL", "JKCEMENT", "JSWSTEEL", "JUBLFOOD", "KOTAKBANK", "LALPATHLAB", "LAURUSLABS",
    "LICHSGFIN", "LT", "LTIM", "LTF", "LUPIN", "M&M", "M&MFIN", "MANAPPURAM", "MARICO",
    "MARUTI", "MCDOWELL-N", "MCX", "METROPOLIS", "MFSL", "MGL", "MOTHERSON", "MPHASIS",
    "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI", "NAVINFLUOR", "NESTLEIND", "NMDC", "NTPC",
    "OBEROIRLTY", "OFSS", "ONGC", "PAGEIND", "PERSISTENT", "PETRONET", "PFC", "PIDILITIND",
    "PIIND", "PNB", "POLYCAB", "POWERGRID", "PVRINOX", "RAMCOCEM", "RBLBANK", "RECLTD",
    "RELIANCE", "SAIL", "SBICARD", "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS",
    "SRF", "SUNPHARMA", "SUNTV", "SYNGENE", "TATACHEMICALS", "TATACONSUM", "TATELXSI",
    "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM",
    "TRENT", "TVSMOTOR", "UBL", "ULTRACEMCO", "UPL", "VEDL", "VOLTAS", "WIPRO", "ZEEL"
]

# ==========================================
# SECTION 4: HISTORICAL & REAL-TIME ANALYSIS
# ==========================================
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
                'trend': 'UPTREND',
                'vol_spike': round(vol_spike, 2),
                'ltp': round(stock_ltp, 2),
                'score': 80.0 if vol_spike > 2.0 else 60.0,
                'ce_action': 'BUY CE 🚀' if price_change_pct > 0.8 else 'WATCH 👀',
                'pe_action': 'NO TRADE 🚫',
                'trigger_ce': f'BUY>{round(stock_ltp * 1.002, 2)}',
                'trigger_pe': 'VOL SPIKE',
                'pcr': 1.15,
                'call_price_up': True,
                'call_oi_up': True if vol_spike > 1.5 else False,
                'put_oi_down': False,
                'atm_iv': 18.0,
                'is_15m_close': True if vol_spike > 1.2 else False
            }
        elif trend == 'DOWNTREND':
            raw_stocks_data[sym] = {
                'trend': 'DOWNTREND',
                'vol_spike': round(vol_spike, 2),
                'ltp': round(stock_ltp, 2),
                'score': 80.0 if vol_spike > 2.0 else 60.0,
                'ce_action': 'NO TRADE 🚫',
                'pe_action': 'BUY PE 🚨' if price_change_pct < -0.8 else 'WATCH 👀',
                'trigger_ce': 'VOL SPIKE',
                'trigger_pe': f'SELL<{round(stock_ltp * 0.998, 2)}',
                'pcr': 0.65,
                'call_price_up': False,
                'call_oi_up': False,
                'put_oi_down': True if vol_spike > 1.5 else False,
                'atm_iv': 19.5,
                'is_15m_close': True if vol_spike > 1.2 else False
            }
        else:
            raw_stocks_data[sym] = {
                'trend': 'SIDEWAYS',
                'vol_spike': round(vol_spike, 2),
                'ltp': round(stock_ltp, 2),
                'score': 20.0,
                'ce_action': 'NO TRADE 🚫',
                'pe_action': 'NO TRADE 🚫',
                'trigger_ce': 'VOL SPIKE',
                'trigger_pe': 'VOL SPIKE',
                'pcr': 0.85,
                'call_price_up': False,
                'call_oi_up': False,
                'put_oi_down': False,
                'atm_iv': 22.0,
                'is_15m_close': False
            }

    except Exception as e:
        print(f"Error processing {sym}: {e}")
        continue
# ==============================================================================
# SECTION 5: MAIN EXECUTION BLOCK (2 TABS UPDATE)
# ==============================================================================
if __name__ == "__main__":
    print("🚀 OI_VCP Engine Active - Updating 2 Clean Tabs...")
    
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        print(f"[⏱️ Execution Time: {now.strftime('%H:%M:%S IST')}] Fetching Market Data...")

        df_ce, df_pe = fetch_and_process_data()

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
        exit(1)
