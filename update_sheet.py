import os
import time
from datetime import datetime
import pytz
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ==============================================================================
# SECTION 1: GSPREAD / GOOGLE SHEETS SETUP
# ==============================================================================
def get_gspread_client():
    """Google Sheets API Authentication Setup"""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Agar environment variable se JSON key leni ho ya local file 'credentials.json' se
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    creds = Credentials.from_service_account_file(creds_path, scopes=scope)
    return gspread.authorize(creds)

def update_tab(sh, df, tab_name):
    """Google Sheet ke specific tab ko safely update karne ka function"""
    try:
        try:
            worksheet = sh.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=tab_name, rows="100", cols="20")
        
        worksheet.clear()
        # Header + Data write logic
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    except Exception as e:
        print(f"❌ Error updating tab '{tab_name}': {e}")

# ==============================================================================
# SECTION 2: HEAVYWEIGHT CONFLUENCE ENGINE (NIFTY 50 FILTER)
# ==============================================================================
def process_nifty_with_heavyweights(nifty_raw_score, stock_data_dict):
    """
    Nifty 50 ko tabhi UPTREND/DOWNTREND dega jab Heavyweights (HDFC, RELIANCE, ICICI, TCS) Confirm karenge.
    """
    heavyweights = ['HDFCBANK', 'RELIANCE', 'ICICIBANK', 'TCS']
    hw_score = 0
    hw_status_list = []
    
    for symbol in heavyweights:
        if symbol in stock_data_dict:
            item = stock_data_dict[symbol]
            trend = item.get('trend', 'SIDEWAYS')
            vol = item.get('vol_spike', 1.0)
            
            if trend == 'UPTREND' and vol >= 1.2:
                hw_score += 2
                hw_status_list.append(f"{symbol} 🟢")
            elif trend == 'UPTREND':
                hw_score += 1
                hw_status_list.append(f"{symbol} 🟢")
            elif trend == 'DOWNTREND':
                hw_score -= 2
                hw_status_list.append(f"{symbol} 🔴")
            else:
                hw_status_list.append(f"{symbol} 🟡")
        else:
            # Neutral fallback agar heavyweight fetch nahi hua
            hw_status_list.append(f"{symbol} ⚪")

    hw_summary = " | ".join(hw_status_list)

    # --- CONFIRMATION MATRIX ---
    if nifty_raw_score >= 5.0 and hw_score >= 3:
        final_trend = "🟢 UPTREND"
        action_plan = "BUY CE (HEAVYWEIGHT CONFIRMED) 🟢"
    elif nifty_raw_score <= -5.0 and hw_score <= -3:
        final_trend = "🔴 DOWNTREND"
        action_plan = "BUY PE (HEAVYWEIGHT CONFIRMED) 🔴"
    elif nifty_raw_score >= 5.0 and hw_score < 3:
        # Nifty upar dikh raha hai par Heavyweights support nahi kar rahe (TRAP)
        final_trend = "🟡 SIDEWAYS"
        action_plan = "NO TRADE 🚫 (HDFC/RELIANCE DIVERGENCE)"
    else:
        final_trend = "🟡 SIDEWAYS"
        action_plan = "NO TRADE 🚫"
        
    return final_trend, action_plan, hw_summary

# ==============================================================================
# SECTION 3: DATA FETCHING & PROCESSING ENGINE
# ==============================================================================
def fetch_and_process_data():
    """
    Data fetch simulation / live API integration.
    Aap yahan apni existing NSE / Broker API ka code link karein.
    """
    ist = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist).strftime('%H:%M:%S')

    # Mocking Data Structure (Isme aapki live API ka output map hoga)
    # Target Stocks: NIFTY 50 + Heavyweights + Watchlist Stocks
    raw_stocks = {
        'HDFCBANK': {'trend': 'SIDEWAYS', 'vol_spike': 0.9, 'ltp': 1650.0},
        'RELIANCE': {'trend': 'DOWNTREND', 'vol_spike': 1.1, 'ltp': 2980.0},
        'ICICIBANK': {'trend': 'UPTREND', 'vol_spike': 1.0, 'ltp': 1120.0},
        'TCS': {'trend': 'UPTREND', 'vol_spike': 0.8, 'ltp': 4150.0},
        'MANKIND': {'trend': 'UPTREND', 'vol_spike': 8.09, 'ltp': 2398.0, 'score': 10.0, 'action': 'BUY CE (SWEET SPOT) 🟢', 'trigger': 'BUY > 2398.0 | T1: 2404.7 (SL: 2393.5)'},
        'UNOMINDA': {'trend': 'UPTREND', 'vol_spike': 0.81, 'ltp': 1279.8, 'score': 4.6, 'action': 'WATCH CE 👀', 'trigger': 'WAIT FOR VOL SPIKE'},
        'TIINDIA': {'trend': 'UPTREND', 'vol_spike': 0.68, 'ltp': 2869.1, 'score': 4.5, 'action': 'WATCH CE 👀', 'trigger': 'WAIT FOR VOL SPIKE'},
        'APOLLOHOSP': {'trend': 'UPTREND', 'vol_spike': 2.50, 'ltp': 8800.0, 'score': 3.5, 'action': 'WATCH CE 👀', 'trigger': 'FLAT RANGE / SL TOO TIGHT'},
        'KAYNES': {'trend': 'UPTREND', 'vol_spike': 0.62, 'ltp': 4039.0, 'score': 2.3, 'action': 'WATCH CE 👀', 'trigger': 'WAIT FOR VOL SPIKE'},
    }

    # 1. Evaluate Nifty 50 with Heavyweight Confluence
    nifty_raw_score = 6.0  # Technical Indicator (VCP/OI) says positive, BUT...
    nifty_trend, nifty_action, hw_summary = process_nifty_with_heavyweights(nifty_raw_score, raw_stocks)

    # 2. Build Dashboard DataFrame (CE)
    data_ce = []
    
    # Nifty 50 Entry (#1 Row)
    data_ce.append({
        'Rank': '#1',
        'TrendClean': nifty_trend,
        'Symbol': 'NIFTY 50',
        'LTP': 24154.6,
        'Action / Entry Trigger': nifty_action,
        'CE Entry Plan': f"HW Status: {hw_summary}",
        'Volume Spike': '1.0x ⚡',
        'CE Strength Score': 0.0 if 'NO TRADE' in nifty_action else 6.0,
        'Execution Time': curr_time
    })

    # Stocks Entry (#2 onwards)
    rank_count = 2
    for symbol, item in raw_stocks.items():
        if symbol in ['HDFCBANK', 'RELIANCE', 'ICICIBANK', 'TCS']:
            continue  # Heavyweights processed in background
            
        data_ce.append({
            'Rank': f"#{rank_count}",
            'TrendClean': '🟢 UPTREND' if item['trend'] == 'UPTREND' else '🟡 SIDEWAYS',
            'Symbol': symbol,
            'LTP': item['ltp'],
            'Action / Entry Trigger': item.get('action', 'WATCH CE 👀'),
            'CE Entry Plan': item.get('trigger', 'WAIT FOR VOL SPIKE'),
            'Volume Spike': f"{item['vol_spike']}x ⚡" if item['vol_spike'] >= 1.0 else f"{item['vol_spike']}x 💧",
            'CE Strength Score': item.get('score', 0.0),
            'Execution Time': curr_time
        })
        rank_count += 1

    df_ce = pd.DataFrame(data_ce)
    df_pe = df_ce.copy() # Placeholder for PE DataFrame logic

    return df_ce, df_pe

# ==============================================================================
# SECTION 4: MAIN DASHBOARD DATA RETRIEVAL & MAPPING
# ==============================================================================
def fetch_and_process_data():
    """
    Data fetch & processing engine.
    Nifty Heavyweight Confluence scan karne ke baad final DataFrame banata hai.
    """
    ist = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist).strftime('%H:%M:%S')

    # Mocking Data Structure (Yahan aapka Live Broker/NSE API Data map hoga)
    raw_stocks = {
        'HDFCBANK': {'trend': 'SIDEWAYS', 'vol_spike': 0.9, 'ltp': 1650.0},
        'RELIANCE': {'trend': 'DOWNTREND', 'vol_spike': 1.1, 'ltp': 2980.0},
        'ICICIBANK': {'trend': 'UPTREND', 'vol_spike': 1.0, 'ltp': 1120.0},
        'TCS': {'trend': 'UPTREND', 'vol_spike': 0.8, 'ltp': 4150.0},
        'MANKIND': {'trend': 'UPTREND', 'vol_spike': 8.09, 'ltp': 2398.0, 'score': 10.0, 'action': 'BUY CE (SWEET SPOT) 🟢', 'trigger': 'BUY > 2398.0 | T1: 2404.7 (SL: 2393.5)'},
        'UNOMINDA': {'trend': 'UPTREND', 'vol_spike': 0.81, 'ltp': 1279.8, 'score': 4.6, 'action': 'WATCH CE 👀', 'trigger': 'WAIT FOR VOL SPIKE'},
        'TIINDIA': {'trend': 'UPTREND', 'vol_spike': 0.68, 'ltp': 2869.1, 'score': 4.5, 'action': 'WATCH CE 👀', 'trigger': 'WAIT FOR VOL SPIKE'},
        'APOLLOHOSP': {'trend': 'UPTREND', 'vol_spike': 2.50, 'ltp': 8800.0, 'score': 3.5, 'action': 'WATCH CE 👀', 'trigger': 'FLAT RANGE / SL TOO TIGHT'},
        'KAYNES': {'trend': 'UPTREND', 'vol_spike': 0.62, 'ltp': 4039.0, 'score': 2.3, 'action': 'WATCH CE 👀', 'trigger': 'WAIT FOR VOL SPIKE'},
    }

    # 1. Evaluate Nifty 50 with Background Heavyweight Confluence
    nifty_raw_score = 6.0  
    nifty_trend, nifty_action, hw_summary = process_nifty_with_heavyweights(nifty_raw_score, raw_stocks)

    # 2. Build Dashboard DataFrame (CE)
    data_ce = []
    
    # Nifty 50 Entry (#1 Row)
    data_ce.append({
        'Rank': '#1',
        'TrendClean': nifty_trend,
        'Symbol': 'NIFTY 50',
        'LTP': 24154.6,
        'Action / Entry Trigger': nifty_action,
        'CE Entry Plan': f"HW Status: {hw_summary}",
        'Volume Spike': '1.0x ⚡',
        'CE Strength Score': 0.0 if 'NO TRADE' in nifty_action else 6.0,
        'Execution Time': curr_time
    })

    # Stocks Entry (#2 onwards)
    rank_count = 2
    for symbol, item in raw_stocks.items():
        if symbol in ['HDFCBANK', 'RELIANCE', 'ICICIBANK', 'TCS']:
            continue  # Heavyweights processed silently in background
            
        data_ce.append({
            'Rank': f"#{rank_count}",
            'TrendClean': '🟢 UPTREND' if item['trend'] == 'UPTREND' else '🟡 SIDEWAYS',
            'Symbol': symbol,
            'LTP': item['ltp'],
            'Action / Entry Trigger': item.get('action', 'WATCH CE 👀'),
            'CE Entry Plan': item.get('trigger', 'WAIT FOR VOL SPIKE'),
            'Volume Spike': f"{item['vol_spike']}x ⚡" if item['vol_spike'] >= 1.0 else f"{item['vol_spike']}x 💧",
            'CE Strength Score': item.get('score', 0.0),
            'Execution Time': curr_time
        })
        rank_count += 1

    df_ce = pd.DataFrame(data_ce)
    df_pe = df_ce.copy() 

    return df_ce, df_pe

# ==============================================================================
# SECTION 5: MAIN EXECUTION LOOP (15-MINUTE AUTO REFRESH LOOP)
# ==============================================================================
if __name__ == "__main__":
    # 15 Minutes = 900 Seconds (Run flow clutter free rakhne ke liye)
    SLEEP_INTERVAL = 900  

    print("🚀 OI_VCP Auto-Scanner Engine Active...")

    while True:
        try:
            ist = pytz.timezone('Asia/Kolkata')
            now = datetime.now(ist)

            is_weekday = now.weekday() < 5
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

            # Live Trading Hours Check (09:15 AM to 03:30 PM IST)
            if is_weekday and (market_open <= now <= market_close):
                start_time = time.time()
                print(f"\n[⏱️ {now.strftime('%H:%M:%S IST')}] Scanning Heavyweights & Refreshing Dashboard...")
                
                try:
                    df_ce, df_pe = fetch_and_process_data()
                    sheet_id = os.environ.get("SHEET_ID")
                    
                    if sheet_id:
                        gc = get_gspread_client()
                        sh = gc.open_by_key(sheet_id)
                        
                        # Aapke Exact Tab Name ke saath Update:
                        update_tab(sh, df_ce, "NEW OI_VCP B/O DASHBOARD")
                        update_tab(sh, df_pe, "LIVE_PE_DASHBOARD")
                        
                        elapsed = round(time.time() - start_time, 2)
                        print(f"✅ 'NEW OI_VCP B/O DASHBOARD' Updated Successfully in {elapsed} sec!")
                    else:
                        print("⚠️ SHEET_ID variable missing in environment!")

                except Exception as fetch_err:
                    print(f"❌ Scan/Update Error: {fetch_err}")

                print("💤 Sleeping for 15 minutes... Next update in 15 mins.")
                time.sleep(SLEEP_INTERVAL)

            elif not is_weekday:
                print("📅 Weekend detected - Market Closed. Waiting...")
                time.sleep(3600)  # Check every 1 hour
            else:
                print(f"⏰ Market Closed ({now.strftime('%H:%M:%S IST')}). Waiting for next market session...")
                time.sleep(900)

        except KeyboardInterrupt:
            print("\n🛑 Script stopped manually.")
            break
        except Exception as global_err:
            print(f"⚠️ Unexpected Error: {global_err}")
            time.sleep(10)
