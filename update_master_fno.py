import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import random # Testing ke liye random values generate karne ke liye

SCOPE = ["https://google.com", "https://googleapis.com"]

def connect_google_sheets():
    try:
        creds_json = os.environ.get("GCP_CREDENTIALS_JSON")
        sheet_id = os.environ.get("SHEET_ID")
        
        if not creds_json or not sheet_id:
            print("❌ Error: GitHub Secrets missing hain!")
            return None
            
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(sheet_id) 
        return spreadsheet
    except Exception as e:
        print(f"❌ Google Sheets Connection Error: {e}")
        return None

def update_scanner_dashboard():
    spreadsheet = connect_google_sheets()
    if not spreadsheet:
        return
        
    cash_tab = spreadsheet.worksheet("DATA_CASH")
    derivatives_tab = spreadsheet.worksheet("DATA_DERIVATIVES")
    master_dashboard = spreadsheet.worksheet("MASTER_DASHBOARD")
    
    # 👑 MASTER STOCKS LIST (Nifty 50 on top + All your stocks)
    master_stocks = [
        "NIFTY_50", "TORNTPHARM", "ASHOKLEY", "KAYNES", "INOXWIND", "GAIL", "KEI", 
        "PREMIERENE", "CGPOWER", "M&M", "BSE", "DIVISLAB", "MOTHERSON", "POWERINDIA", 
        "GLENMARK", "MAZDOCK", "DELHIVERY", "GVT&D", "TVSMOTOR", "POLYCAB", "TIINDIA", 
        "SIEMENS", "CUMMINSIND", "JSWENERGY", "ANGELONE", "COCHINSHIP", "WAAREEENER", 
        "LAURUSLABS", "MOTILALOFS", "BHARATFORG", "TMPV", "SOLARINDS", "TATASTEEL", 
        "LTF", "FORCEMOT", "PRESTIGE", "BPCL", "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", 
        "NBCC", "DMART", "HEROMOTOCO", "KPITTECH", "RVNL", "RELIANCE", "PNB", "ZYDUSLIFE", 
        "BHEL", "NATIONALUM", "NHPC", "SRF", "JINDALSTEL", "BAJAJ-AUTO", "BEL", "TITAN", 
        "SONACOMS", "HINDZINC", "UNOMINDA", "OBEROIRLTY", "BHARTIARTL", "OFSS", "BDL", 
        "SUPREMEIND", "OIL", "SHREECEM", "NTPC", "TATAELXSI", "HINDALCO", "PETRONET", 
        "CIPLA", "MARUTI", "PAYTM", "PERSISTENT", "AMBER", "DLF", "DALBHARAT", "ULTRACEMCO", 
        "ONGC", "PHOENIXLTD", "HINDPETRO", "CAMS", "AUROPHARMA", "BIOCON", "TRENT", "DRREDDY", 
        "JSWSTEEL", "NMDC", "IOC", "UPL", "NYKAA", "LT", "CROMPTON", "INDUSTOWER", "HAVELLS", 
        "CONCOR", "SAIL", "JUBLFOOD", "GRASIM", "PFC", "ASIANPAINT", "LUPIN", "CDSL", "IREDA", 
        "HINDUNILVR", "GODREJPROP", "KFINTECH", "AMBUJACEM", "APOLLOHOSP", "HCLTECH", "POWERGRID", 
        "RECLTD", "GODREJCP", "FORTIS", "PGEL", "ABB", "COALINDIA", "SUNPHARMA", "MPHASIS", 
        "PIIND", "COLPAL", "BLUESTARCO", "VMM", "VOLTAS", "TECHM", "EICHERMOT", "INDIGO", 
        "DABUR", "NESTLEIND", "TATACONSUM", "BOSCHLTD", "VEDL", "PIDILITIND", "NAUKRI", 
        "WIPRO", "ALKEM", "ITC", "COFORGE", "ASTRAL", "LTM", "MARICO", "PAGEIND", "MAXHEALTH", 
        "BRITANNIA", "INFY", "ETERNAL", "TCS", "KALYANKJIL", "LODHA", "SWIGGY", "MANKIND", 
        "DIXON", "APLAPOLLO"
    ]
    
    ticker_updates = [[ticker] for ticker in master_stocks]
    end_row = len(master_stocks) + 1
    
    # Step 1: Force column A registration across all tabs
    print("📝 Syncing Master Tickers in Column A...")
    cash_tab.update(values=ticker_updates, range_name=f'A2:A{end_row}')
    derivatives_tab.update(values=ticker_updates, range_name=f'A2:A{end_row}')
    master_dashboard.update(values=ticker_updates, range_name=f'A2:A{end_row}')
    
    # ⏱️ India Time (IST) Generation
    IST = pytz.timezone('Asia/Kolkata')
    current_time_str = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    
    # Grid separation matrix
    highs, lows, closes, ltps, price_chgs, pivots, vol_spikes, times = [], [], [], [], [], [], [], []
    der_ltps, pcrs, max_pains, oi_chgs, der_price_chgs, iv_calls, iv_puts, deltas = [], [], [], [], [], [], [], []
    
    # ⚡ AUTOMATED DATA SIMULATOR FOR ALL 150+ STOCKS
    # Taaki saare rows bharein aur Google API drop na kare
    for ticker in master_stocks:
        # Standard variables calculation
        mock_close = random.randint(100, 3000)
        mock_ltp = mock_close + random.randint(-20, 50)
        p_chg = round(((mock_ltp - mock_close) / mock_close) * 100, 2)
        mock_pivot = mock_close - 10
        
        # Testing target breakouts dynamically
        if ticker in ["M&M", "KAYNES", "CGPOWER"]:
            mock_ltp = 3354.7 if ticker == "M&M" else mock_pivot + 50
            mock_pivot = 3329.0 if ticker == "M&M" else mock_close - 20
            v_spike = "SPIKE ⚡ (2.3x)"
            oi_val = 6.5
            pcr_val = 1.3
            m_pain = mock_ltp - 30
            d_mom = "Increasing"
        else:
            v_spike = "NORMAL (1.0x)"
            oi_val = random.randint(1, 4)
            pcr_val = round(random.uniform(0.7, 0.9), 2)
            m_pain = mock_ltp + 10
            d_mom = "Stable"
            
        # TAB 1: DATA_CASH Dataset Array Matrix 
        highs.append([mock_ltp + 5])
        lows.append([mock_ltp - 5])
        closes.append([mock_close])
        ltps.append([mock_ltp])
        price_chgs.append([p_chg])
        pivots.append([mock_pivot])
        vol_spikes.append([v_spike])
        times.append([current_time_str])
        
        # TAB 2: DATA_DERIVATIVES Dataset Array Matrix
        der_ltps.append([mock_ltp])
        pcrs.append([pcr_val])
        max_pains.append([m_pain])
        oi_chgs.append([oi_val])
        der_price_chgs.append([p_chg])
        iv_calls.append([20])
        iv_puts.append([18])
        deltas.append([d_mom])

    print("🚀 Forcing discrete columns matrix into Google Sheets cells...")
    
    # Update TAB 1: DATA_CASH
    cash_tab.update(values=highs, range_name=f'B2:B{end_row}', value_input_option='USER_ENTERED')
    cash_tab.update(values=lows, range_name=f'C2:C{end_row}', value_input_option='USER_ENTERED')
    cash_tab.update(values=closes, range_name=f'D2:D{end_row}', value_input_option='USER_ENTERED')
    cash_tab.update(values=ltps, range_name=f'E2:E{end_row}', value_input_option='USER_ENTERED')
    cash_tab.update(values=price_chgs, range_name=f'F2:F{end_row}', value_input_option='USER_ENTERED')
    cash_tab.update(values=pivots, range_name=f'I2:I{end_row}', value_input_option='USER_ENTERED')
    cash_tab.update(values=vol_spikes, range_name=f'J2:J{end_row}', value_input_option='USER_ENTERED')
    cash_tab.update(values=times, range_name=f'P2:P{end_row}', value_input_option='USER_ENTERED')
    
    # Update TAB 2: DATA_DERIVATIVES
    derivatives_tab.update(values=der_ltps, range_name=f'B2:B{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=pcrs, range_name=f'C2:C{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=max_pains, range_name=f'D2:D{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=oi_chgs, range_name=f'F2:F{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=der_price_chgs, range_name=f'G2:G{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=iv_calls, range_name=f'I2:I{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=iv_puts, range_name=f'J2:J{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=deltas, range_name=f'L2:L{end_row}', value_input_option='USER_ENTERED')
        
    print(f"✅ Master Success: All {len(master_stocks)} columns globally locked at {current_time_str} IST!")

if __name__ == "__main__":
    update_scanner_dashboard()
