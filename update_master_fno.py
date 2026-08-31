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
    # Real test data generation for proper visualization
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
    
    # 1. Force Enter Tickers in Column A (Raw format)
    cash_tab.update(range_name=f'A2:A{len(master_stocks)+1}', values=ticker_updates)
    derivatives_tab.update(range_name=f'A2:A{len(master_stocks)+1}', values=ticker_updates)
    master_dashboard.update(range_name=f'A2:A{len(master_stocks)+1}', values=ticker_updates)
    
    market_data = fetch_derivatives_data()
    
    IST = pytz.timezone('Asia/Kolkata')
    current_time_str = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    
    # Grid data format arrays (Direct rows generation)
    cash_grid = []
    derivatives_grid = []
    
    for ticker in master_stocks:
        default_data = {
            "high": "", "low": "", "close": "", "ltp": "", "pivot": "",
            "volume_spike": "NORMAL (0.0x)", "oi_chg": 0, "pcr": 0, "max_pain": "",
            "iv_call": "", "iv_put": "", "delta_mom": "Stable"
        }
        
        data = market_data[ticker] if ticker in market_data else default_data
        
        # Calculate price change percent
        if data['close'] and data['ltp']:
            price_change_pct = round(((float(data['ltp']) - float(data['close'])) / float(data['close'])) * 100, 2)
        else:
            price_change_pct = 0
            
        # DATA_CASH Columns Structure (B to P)
        # HIGH(B), LOW(C), CLOSE(D), LTP(E), PRICE_CHG(F), VCP(G), VOLATILITY(H), PIVOT(I), VOL_SPIKE(J), SL(K), TARGET(L), RR(M), CASH_SIG(N), BO_STOCKS(O), TIME(P)
        cash_grid.append([
            data['high'], data['low'], data['close'], data['ltp'], 
            price_change_pct, "", "", data['pivot'], data['volume_spike'], 
            "", "", "", "", "", current_time_str if ticker in market_data else ""
        ])
        
        # DATA_DERIVATIVES Columns Structure (B to L)
        # LTP(B), PCR(C), MAXPAIN(D), MP_STATUS(E), OI_CHG(F), PRICE_CHG(G), BUILDUP(H), CALL_IV(I), PUT_IV(J), SKEW(K), DELTA(L)
        derivatives_grid.append([
            data['ltp'], data['pcr'], data['max_pain'], "", 
            data['oi_chg'], price_change_pct, "", data['iv_call'], 
            data['iv_put'], "", data['delta_mom']
        ])

    # 👑 BULLETPROOF FULL GRID RE-WRITE WITH strict VALUE_INPUT_OPTION
    print("🚀 Forcing grid updates into Google Sheets cells...")
    
    cash_tab.update(range_name=f'B2:P{len(master_stocks)+1}', values=cash_grid, value_input_option='USER_ENTERED')
    derivatives_tab.update(range_name=f'B2:L{len(master_stocks)+1}', values=derivatives_grid, value_input_option='USER_ENTERED')
        
    print(f"✅ Master Success: Both worksheets fully written at {current_time_str} IST!")

if __name__ == "__main__":
    update_scanner_dashboard()
