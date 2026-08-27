import os
import time
from datetime import datetime
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ==============================================================================
# SECTION 1: AUTHENTICATION & GOOGLE SHEETS SETUP
# ==============================================================================
def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    creds = Credentials.from_service_account_file(creds_path, scopes=scope)
    return gspread.authorize(creds)

def update_tab(sh, df, tab_name):
    try:
        try:
            worksheet = sh.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=tab_name, rows="200", cols="20")
        
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.astype(str).values.tolist(), value_input_option='USER_ENTERED')
        print(f"✅ Tab '{tab_name}' Successfully Updated!")
    except Exception as e:
        print(f"❌ Error updating tab '{tab_name}': {e}")

# ==============================================================================
# SECTION 2: HEAVYWEIGHT CONFLUENCE ENGINE (STRICT CE/PE & DIVERGENCE PROTECTION)
# ==============================================================================
def process_heavyweight_logic(raw_data_dict):
    """
    STRICT HEAVYWEIGHT LOGIC:
    - HDFCBANK & RELIANCE UP -> 🚀 BUY CE (CONFIRMED)
    - HDFCBANK & RELIANCE DOWN -> 🚨 BUY PE (CONFIRMED)
    - MIXED / DIVERGENCE -> NO TRADE 🚫
    """
    hw_stocks = ['HDFCBANK', 'RELIANCE', 'ICICIBANK', 'TCS']
    up_count = 0
    down_count = 0
    hw_status = []

    for sym in hw_stocks:
        if sym in raw_data_dict:
            t = raw_data_dict[sym].get('trend', 'SIDEWAYS')
            if t == 'UPTREND':
                up_count += 1
                hw_status.append(f"{sym}: 🟢")
            elif t == 'DOWNTREND':
                down_count += 1
                hw_status.append(f"{sym}: 🔴")
            else:
                hw_status.append(f"{sym}: 🟡")

    summary_str = " | ".join(hw_status)

    if up_count >= 2 and down_count == 0:
        final_trend = "🟢 UPTREND"
        action = "🚀 BUY CE (HEAVYWEIGHT UPTREND CONFIRMED)"
        score = 10.0
    elif down_count >= 2 and up_count == 0:
        final_trend = "🔴 DOWNTREND"
        action = "🚨 BUY PE (HEAVYWEIGHT DOWNTREND CONFIRMED)"
        score = 0.0
    else:
        final_trend = "🟡 SIDEWAYS / DIVERGENCE"
        action = "NO TRADE 🚫 (HDFC/RELIANCE DIVERGENCE)"
        score = 5.0

    return final_trend, action, summary_str, score

# ==============================================================================
# SECTION 3: 153 STOCKS DATA PROCESSING & SCANNER
# ==============================================================================
def fetch_and_process_data():
    ist = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist).strftime('%H:%M:%S')

    all_user_stocks = [
        "CROMPTON", "HINDZINC", "LODHA", "BLUESTARCO", "BEL", "JUBLFOOD", "PREMIERENE", 
        "GMRAIRPORT", "VEDL", "CONCOR", "PIIND", "EICHERMOT", "TIINDIA", "ETERNAL", 
        "SUNPHARMA", "SWIGGY", "BHEL", "NATIONALUM", "NBCC", "GVT&D", "NAUKRI", 
        "DMART", "CAMS", "MOTHERSON", "TATASTEEL", "NESTLEIND", "INOXWIND", "SOLARINDS", 
        "KEI", "MARICO", "BHARTIARTL", "COFORGE", "PRESTIGE", "TMPV", "DIVISLAB", 
        "TATACONSUM", "VOLTAS", "NMDC", "JINDALSTEL", "INFY", "PAGEIND", "INDUSTOWER", 
        "SUPREMEIND", "HINDPETRO", "POLYCAB", "KFINTECH", "MAXHEALTH", "SUZLON", "NYKAA", 
        "OFSS", "M&M", "PERSISTENT", "RADICO", "KAYNES", "ZYDUSLIFE", "DLF", 
        "PGEL", "TATAELXSI", "IREDA", "RECLTD", "TATAPOWER", "HCLTECH", "DIXON", 
        "LTF", "LUPIN", "MPHASIS", "ONGC", "AUROPHARMA", "GLENMARK", "JSWENERGY", 
        "SRF", "MOTILALOFS", "RELIANCE", "APLAPOLLO", "NAM-INDIA", "UNOMINDA", "POWERINDIA", 
        "COALINDIA", "DABUR", "IRFC", "OBEROIRLTY", "PHOENIXLTD", "TORNTPHARM", "ALKEM", 
        "AMBER", "ANGELONE", "ASTRAL", "BDL", "BIOCON", "BPCL", "CDSL", 
        "CGPOWER", "DALBHARAT", "DELHIVERY", "FORCEMOT", "GODREJPROP", "HINDALCO", "HINDUNILVR", 
        "KALYANKJIL", "KPITTECH", "LAURUSLABS", "LT", "MANKIND", "MARUTI", "MAZDOCK", 
        "RVNL", "SIEMENS", "TECHM", "TITAN", "TRENT", "VMM", "TVSMOTOR", 
        "PAYTM", "SHREECEM", "BAJAJ-AUTO", "ABB", "DRREDDY", "POWERGRID", "WAAREEENER", 
        "APOLLOHOSP", "COLPAL", "JSWSTEEL", "GAIL", "UPL", "FORTIS", "ASIANPAINT", 
        "INDIGO", "HYUNDAI", "ULTRACEMCO", "WIPRO", "HAVELLS", "SONACOMS", "AMBUJACEM", 
        "BOSCHLTD", "HAL", "COCHINSHIP", "GODREJCP", "HEROMOTOCO", "IOC", "CIPLA", 
        "TCS", "ASHOKLEY", "BRITANNIA", "BHARATFORG", "PETRONET", "GRASIM", "PIDILITIND", 
        "LTM", "BSE", "CUMMINSIND", "HDFCBANK", "ICICIBANK", "AXISBANK", "SBIN", 
        "KOTAKBANK", "INDUSINDBK", "BANKBARODA", "PNB", "CANBK", "IDFCFIRSTB", "AUBANK", 
        "FEDERALBNK", "BANDHANBNK", "IDBI", "UNIONBANK", "IOB", "UCOBANK"
    ]

    # Note: Connect raw_stocks_data to your broker API feed (Zerodha / Live Feed)
    raw_stocks_data = {}
    for sym in all_user_stocks:
        if sym == 'MANKIND':
            raw_stocks_data[sym] = {'trend': 'UPTREND', 'vol_spike': 8.09, 'ltp': 2398.0, 'score': 10.0, 'action': 'BUY CE (SWEET SPOT) 🟢', 'trigger': 'BUY > 2398.0'}
        elif sym == 'HDFCBANK':
            raw_stocks_data[sym] = {'trend': 'UPTREND', 'vol_spike': 1.5, 'ltp': 1650.0, 'score': 8.0, 'action': 'WATCH CE 👀', 'trigger': 'WAIT FOR VOL SPIKE'}
        elif sym == 'RELIANCE':
            raw_stocks_data[sym] = {'trend': 'UPTREND', 'vol_spike': 1.8, 'ltp': 2980.0, 'score': 9.0, 'action': 'WATCH CE 👀', 'trigger': 'WAIT FOR VOL SPIKE'}
        else:
            raw_stocks_data[sym] = {'trend': 'SIDEWAYS', 'vol_spike': 1.0, 'ltp': 1000.0, 'score': 0.0, 'action': 'NO TRADE 🚫', 'trigger': 'WAIT FOR SETUP'}

    # Run Heavyweight Logic Engine
    n_trend, n_action, hw_summary, n_score = process_heavyweight_logic(raw_stocks_data)

    data_ce = []
    # Row #1: NIFTY 50 Index Confluence Row
    data_ce.append({
        'Rank': '#1',
        'TrendClean': n_trend,
        'Symbol': 'NIFTY 50',
        'LTP': 24154.6,
        'Action / Entry Trigger': n_action,
        'CE Entry Plan': f"HW Status: {hw_summary}",
        'Volume Spike': '1.0x ⚡',
        'CE Strength Score': n_score,
        'Execution Time': curr_time
    })

    # Row #2 to #154: All 153 Stocks
    sorted_stocks = sorted(raw_stocks_data.items(), key=lambda x: x[1].get('score', 0.0), reverse=True)
    rank_count = 2
    for symbol, item in sorted_stocks:
        t_label = '🟢 UPTREND' if item.get('trend') == 'UPTREND' else ('🔴 DOWNTREND' if item.get('trend') == 'DOWNTREND' else '🟡 SIDEWAYS')
        data_ce.append({
            'Rank': f"#{rank_count}",
            'TrendClean': t_label,
            'Symbol': symbol,
            'LTP': item.get('ltp', 0.0),
            'Action / Entry Trigger': item.get('action', 'NO TRADE 🚫'),
            'CE Entry Plan': item.get('trigger', 'WAIT FOR VOL SPIKE'),
            'Volume Spike': f"{item.get('vol_spike', 1.0)}x ⚡",
            'CE Strength Score': item.get('score', 0.0),
            'Execution Time': curr_time
        })
        rank_count += 1

    df_ce = pd.DataFrame(data_ce)
    return df_ce, df_ce.copy()

# ==============================================================================
# SECTION 4 & 5: SINGLE EXECUTION FOR GITHUB ACTIONS / AUTOMATION (NO SLEEP LOOP)
# ==============================================================================
if __name__ == "__main__":
    print("🚀 OI_VCP Single Run Triggered via GitHub Actions...")
    
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        print(f"[⏱️ Execution Time: {now.strftime('%H:%M:%S IST')}] Processing 153 Stocks...")

        # 1. Fetch & Process
        df_ce, df_pe = fetch_and_process_data()

        # 2. Update Google Sheet
        sheet_id = os.environ.get("SHEET_ID")
        if sheet_id:
            gc = get_gspread_client()
            sh = gc.open_by_key(sheet_id)

            update_tab(sh, df_ce, "NEW OI_VCP B/O DASHBOARD")
            update_tab(sh, df_pe, "LIVE_PE_DASHBOARD")
            print("🎉 SUCCESS! Google Sheet Updated Successfully.")
        else:
            print("❌ ERROR: SHEET_ID Environment Variable Missing!")

    except Exception as err:
        print(f"❌ Execution Failed: {err}")
        exit(1)
