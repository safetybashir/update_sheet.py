import os
import json
import gspread
import yfinance as yf
import pytz
from datetime import datetime as dt
from nsepython import *
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. Institutional Flow with Exception Handling
def get_institutional_flow(sym):
    try:
        # NSE data fetch
        oi_data = derivatives_data(sym)
        if not oi_data or 'changeinOpenInterest' not in oi_data:
            return "🛡️ DATA SYNCING", 5
            
        price_change = oi_data.get('priceChange', 0)
        oi_change = oi_data.get('changeinOpenInterest', 0)
        
        if price_change > 0 and oi_change > 0: return "🎯 LONG BUILD-UP", 10
        elif price_change < 0 and oi_change > 0: return "⚠️ SHORT BUILD-UP", 2
        elif price_change > 0 and oi_change < 0: return "⚡ SHORT COVERING", 8
        return "🛡️ RANGE-BOUND", 5
    except:
        return "⏳ LIVE DATA SYNCING", 5

# 2. Scanner Logic
def scan_stock_v19(sym):
    try:
        # YFinance for LTP
        ticker = yf.Ticker(sym + ".NS")
        ltp = ticker.history(period="1d")['Close'].iloc[-1]
        flow_status, score = get_institutional_flow(sym)
        
        if score >= 8: action = "🚀 BUY ZONE"
        elif score <= 2: action = "📉 SELL ZONE"
        else: action = "⏳ WAIT/WATCH"
        
        return [round(ltp, 2), action, flow_status, score]
    except:
        return [0, "FETCH ERR", "RETRYING", 0]

# 3. Main Execution
def main():
    # Universe list (Sirf naam, bina .NS ke)
    universe = ['TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI', 'POWERINDIA', 'MAXHEALTH']
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        data = list(executor.map(lambda s: [s + '.NS'] + scan_stock_v19(s), universe))
    
    creds = Credentials.from_service_account_info(
        json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), 
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    sh = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID'))
    dash_sheet = sh.get_worksheet(0)
    
    # Refresh Sheet
    dash_sheet.clear()
    dash_sheet.update(range_name='A1', values=[['Symbol', 'LTP', 'Action Plan', 'OI Status', 'Insti Score', 'Update Time']])
    
    timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
    formatted_data = [[*row, timestamp] for row in data]
    dash_sheet.update(range_name='A2', values=formatted_data)
    dash_sheet.freeze(rows=1)

if __name__ == "__main__":
    main()
