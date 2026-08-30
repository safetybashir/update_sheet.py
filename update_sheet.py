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

# ==============================================================================
# SECTION 3: OPTION CHAIN ENGINE & ENTRY LOGIC (WITH 15-MIN CONFIRMATION)
# ==============================================================================
def calculate_7point_option_score(pcr, ltp, call_price_up, call_oi_up, put_oi_down, atm_iv, is_ce=True, hw_ok=True, is_15min_closed=True):
    score = 0

    if is_ce:
        # CE Rules (Bullish)
        if pcr > 1.0: score += 25
        if atm_iv < 20.0: score += 25
        if call_price_up and call_oi_up: score += 25
        if put_oi_down: score += 25
        is_favorable_pcr = pcr > 1.0
    else:
        # PE Rules (Bearish)
        if pcr < 0.8: score += 25
        if atm_iv < 20.0: score += 25
        if not call_price_up: score += 25  # Price breakdown
        if not put_oi_down: score += 25    # Put writing active
        is_favorable_pcr = pcr < 0.8

    tag = "🔥" if score >= 75 else ("🟢" if score >= 50 else "🔴")
    score_str = f"{score} {tag}"

    # Strict Entry Filters
    if score >= 75 and is_favorable_pcr and atm_iv < 20.0:
        if not hw_ok:
            entry_status = "WAIT HW CONFIRM ⏳"  # Heavyweight rule failed (Less than 3 Green/Red)
        elif not is_ce and not is_15min_closed:
            entry_status = "WAIT 15M CLOSE ⏳"   # PE Breakdown needs 15M Candle Confirmation
        else:
            entry_status = "READY ENTRY 🚀"
    elif score >= 50:
        entry_status = "WAIT FOR BREAKOUT ⏳"
    else:
        entry_status = "NO ENTRY 🚫"

    return score_str, entry_status

# ==============================================================================
# SECTION 4: DATA PROCESSING & SEPARATION (CE vs PE)
# ==============================================================================
def fetch_and_process_data():
    ist = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist).strftime('%H:%M:%S')

    sample_stock_ltps = {
        "CROMPTON": 385.4, "HINDZINC": 512.1, "LODHA": 1180.0, "BLUESTARCO": 1690.5, 
        "BEL": 288.3, "JUBLFOOD": 560.2, "PREMIERENE": 950.0, "GMRAIRPORT": 92.4, 
        "VEDL": 465.0, "CONCOR": 1020.0, "PIIND": 3890.0, "EICHERMOT": 4850.0, 
        "MANKIND": 2398.0, "HDFCBANK": 1650.0, "RELIANCE": 2980.0, "TATASTEEL": 155.0,
        "INFY": 1880.0, "TCS": 4200.0, "ICICIBANK": 1220.0, "SBIN": 815.0
    }

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

    raw_stocks_data = {}
    for sym in all_user_stocks:
        stock_ltp = sample_stock_ltps.get(sym, 450.0)
        
        # Bullish Sample
        if sym in ['MANKIND', 'HDFCBANK', 'RELIANCE', 'TATASTEEL']:
            raw_stocks_data[sym] = {
                'trend': 'UPTREND', 'vol_spike': 3.5, 'ltp': stock_ltp, 'score': 10.0,
                'ce_action': 'BUY CE 🚀', 'pe_action': 'NO TRADE 🚫',
                'trigger_ce': f'BUY>{stock_ltp}', 'trigger_pe': 'VOL SPIKE',
                'pcr': 1.25, 'call_price_up': True, 'call_oi_up': True, 
                'put_oi_down': True, 'atm_iv': 15.0, 'is_15m_close': True
            }
        # Bearish Sample
        elif sym in ['CROMPTON', 'HINDZINC', 'LODHA']:
            raw_stocks_data[sym] = {
                'trend': 'DOWNTREND', 'vol_spike': 3.2, 'ltp': stock_ltp, 'score': 9.0,
                'ce_action': 'NO TRADE 🚫', 'pe_action': 'BUY PE 🚨',
                'trigger_ce': 'VOL SPIKE', 'trigger_pe': f'SELL<{stock_ltp}',
                'pcr': 0.65, 'call_price_up': False, 'call_oi_up': False, 
                'put_oi_down': False, 'atm_iv': 16.0, 'is_15m_close': True
            }
        else:
            raw_stocks_data[sym] = {
                'trend': 'SIDEWAYS', 'vol_spike': 1.0, 'ltp': stock_ltp, 'score': 2.0,
                'ce_action': 'WATCH 👀', 'pe_action': 'WATCH 👀',
                'trigger_ce': 'VOL SPIKE', 'trigger_pe': 'VOL SPIKE',
                'pcr': 0.8, 'call_price_up': False, 'call_oi_up': False, 
                'put_oi_down': False, 'atm_iv': 22.0, 'is_15m_close': False
            }

    hw_summary, n_ce_trend, n_ce_action, ce_hw_ok, n_pe_trend, n_pe_action, pe_hw_ok = process_heavyweight_logic(raw_stocks_data)

    data_ce = []
    data_pe = []
    
    # --------------------------------------------------------------------------
    # 1. CE DASHBOARD PREPARATION
    # --------------------------------------------------------------------------
    n_ce_score, n_ce_entry = calculate_7point_option_score(
        1.25, 24154.6, True, True, True, 14.0, is_ce=True, hw_ok=ce_hw_ok, is_15min_closed=True
    )
    data_ce.append({
        'Rank': '#1', 'Trend': n_ce_trend, 'Symbol': 'NIFTY 50', 'LTP': 24154.6,
        'Trigger Plan': f"HW: {hw_summary}", 'Signal': n_ce_action,
        '7-Pt Score': n_ce_score, 'Entry Status': n_ce_entry, 'Time': curr_time
    })

    ce_sorted = sorted(raw_stocks_data.items(), key=lambda x: x[1].get('score', 0.0) if x[1].get('trend') == 'UPTREND' else 0, reverse=True)
    rank_count = 2
    for symbol, item in ce_sorted:
        t_label = '🟢 UP' if item.get('trend') == 'UPTREND' else ('🔴 DOWN' if item.get('trend') == 'DOWNTREND' else '🟡 SIDE')
        opt_score, opt_entry = calculate_7point_option_score(
            item['pcr'], item['ltp'], item['call_price_up'], item['call_oi_up'], item['put_oi_down'], item['atm_iv'],
            is_ce=True, hw_ok=True, is_15min_closed=item.get('is_15m_close', True)
        )
        data_ce.append({
            'Rank': f"#{rank_count}", 'Trend': t_label, 'Symbol': symbol, 'LTP': item.get('ltp', 0.0),
            'Trigger Plan': item.get('trigger_ce', 'VOL SPIKE'), 'Signal': item.get('ce_action', 'NO TRADE 🚫'),
            '7-Pt Score': opt_score, 'Entry Status': opt_entry, 'Time': curr_time
        })
        rank_count += 1

    # --------------------------------------------------------------------------
    # 2. PE DASHBOARD PREPARATION
    # --------------------------------------------------------------------------
    n_pe_score, n_pe_entry = calculate_7point_option_score(
        0.65, 24154.6, False, False, False, 14.0, is_ce=False, hw_ok=pe_hw_ok, is_15min_closed=True
    )
    data_pe.append({
        'Rank': '#1', 'Trend': n_pe_trend, 'Symbol': 'NIFTY 50', 'LTP': 24154.6,
        'Trigger Plan': f"HW: {hw_summary}", 'Signal': n_pe_action,
        '7-Pt Score': n_pe_score, 'Entry Status': n_pe_entry, 'Time': curr_time
    })

    pe_sorted = sorted(raw_stocks_data.items(), key=lambda x: x[1].get('score', 0.0) if x[1].get('trend') == 'DOWNTREND' else 0, reverse=True)
    rank_count = 2
    for symbol, item in pe_sorted:
        t_label = '🔴 DOWN' if item.get('trend') == 'DOWNTREND' else ('🟢 UP' if item.get('trend') == 'UPTREND' else '🟡 SIDE')
        opt_score, opt_entry = calculate_7point_option_score(
            item['pcr'], item['ltp'], item['call_price_up'], item['call_oi_up'], item['put_oi_down'], item['atm_iv'],
            is_ce=False, hw_ok=True, is_15min_closed=item.get('is_15m_close', True)
        )
        data_pe.append({
            'Rank': f"#{rank_count}", 'Trend': t_label, 'Symbol': symbol, 'LTP': item.get('ltp', 0.0),
            'Trigger Plan': item.get('trigger_pe', 'VOL SPIKE'), 'Signal': item.get('pe_action', 'NO TRADE 🚫'),
            '7-Pt Score': opt_score, 'Entry Status': opt_entry, 'Time': curr_time
        })
        rank_count += 1

    return pd.DataFrame(data_ce), pd.DataFrame(data_pe)

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
