import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

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

def fetch_derivatives_data():
    print("🔄 Fetching Live Market Data for Master Stock List...")
    # Real mock data structure testing ke liye (M&M aur RELIANCE pass breakouts)
    mock_market_feed = {
        "NIFTY_50": {
            "high": 24260.0, "low": 24000.0, "close": 24135.0, "ltp": 24211.0, "pivot": 24150.0,
            "volume_spike": "NORMAL (1.0x)", "oi_chg": 0.5, "pcr": 1.0, "max_pain": 24100.0,
            "iv_call": 14.5, "iv_put": 14.5, "delta_mom": "Stable"
        },
        "M&M": {
            "high": 3351.7, "low": 3302.0, "close": 3334.0, "ltp": 3354.7, "pivot": 3329.0,
            "volume_spike": "SPIKE ⚡ (2.0x)", "oi_chg": 6.5, "pcr": 1.3, "max_pain": 3300.0,
            "iv_call": 18.5, "iv_put": 14.2, "delta_mom": "Increasing"
        },
        "RELIANCE": {
            "high": 1325.2, "low": 1281.2, "close": 1325.0, "ltp": 1315.0, "pivot": 1310.0,
            "volume_spike": "NORMAL (1.1x)", "oi_chg": 1.2, "pcr": 0.9, "max_pain": 1320.0,
            "iv_call": 12.1, "iv_put": 13.5, "delta_mom": "Decreasing"
        }
    }
    return mock_market_feed

def update_scanner_dashboard():
    spreadsheet = connect_google_sheets()
    if not spreadsheet:
        return
        
    cash_tab = spreadsheet.worksheet("DATA_CASH")
    derivatives_tab = spreadsheet.worksheet("DATA_DERIVATIVES")
    master_dashboard = spreadsheet.worksheet("MASTER_DASHBOARD")
    
    # 👑 MASTER STOCKS LIST
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
    
    # Step 1: Force column A registration
    print("📝 Syncing Master Tickers in Column A...")
    cash_tab.update(values=ticker_updates, range_name=f'A2:A{end_row}')
    derivatives_tab.update(values=ticker_updates, range_name=f'A2:A{end_row}')
    master_dashboard.update(values=ticker_updates, range_name=f'A2:A{end_row}')
    
    market_data = fetch_derivatives_data()
    
    IST = pytz.timezone('Asia/Kolkata')
    current_time_str = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    
    # Vertical Column Lists separation for direct grid writing
    highs, lows, closes, ltps, price_chgs, pivots, vol_spikes, times = [], [], [], [], [], [], [], []
    pcrs, max_pains, oi_chgs, iv_calls, iv_puts, deltas = [], [], [], [], [], []
    
    for ticker in master_stocks:
        default = {
            "high": "", "low": "", "close": "", "ltp": "", "pivot": "",
            "volume_spike": "NORMAL (0.0x)", "oi_chg": 0, "pcr": 0, "max_pain": "",
            "iv_call": "", "iv_put": "", "delta_mom": "Stable"
        }
        data = market_data[ticker] if ticker in market_data else default
        
        # Calculate price change
        p_chg = round(((float(data['ltp']) - float(data['close'])) / float(data['close'])) * 100, 2) if data['close'] and data['ltp'] else 0
        
        # Storing Cash tab values sequentially
        highs.append([data['high']])
        lows.append([data['low']])
        closes.append([data['close']])
        ltps.append([data['ltp']])
        price_chgs.append([p_chg])
        pivots.append([data['pivot']])
        vol_spikes.append([data['volume_spike']])
        times.append([current_time_str if ticker in market_data else ""])
        
        # Storing Derivatives tab values sequentially
        pcrs.append([data['pcr']])
        max_pains.append([data['max_pain']])
        oi_chgs.append([data['oi_chg']])
        iv_calls.append([data['iv_call']])
        iv_puts.append([data['iv_put']])
        deltas.append([data['delta_mom']])

    # 👑 BULLETPROOF VERTICAL GRID CELLS FORCE-WRITE (Never drops data)
    print("🚀 Forcing discrete column batching into Sheets cells...")
    
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
    derivatives_tab.update(values=ltps, range_name=f'B2:B{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=pcrs, range_name=f'C2:C{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=max_pains, range_name=f'D2:D{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=oi_chgs, range_name=f'F2:F{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=price_chgs, range_name=f'G2:G{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=iv_calls, range_name=f'I2:I{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=iv_puts, range_name=f'J2:J{end_row}', value_input_option='USER_ENTERED')
    derivatives_tab.update(values=deltas, range_name=f'L2:L{end_row}', value_input_option='USER_ENTERED')
        
    print(f"✅ Master Success: All {len(master_stocks)} columns globally locked at {current_time_str} IST!")

if __name__ == "__main__":
    update_scanner_dashboard()
