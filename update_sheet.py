import os
import json
import gspread
import yfinance as yf
import pytz
from datetime import datetime as dt
from nsepython import *
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. Institutional Flow with Fallback
def get_institutional_flow(sym_full):
    try:
        sym = sym_full.split('.')[0]
        oi_data = derivatives_data(sym)
        
        if not oi_data or 'changeinOpenInterest' not in oi_data:
            return "⏳ NO DERIV DATA", 5
            
        price_change = oi_data.get('priceChange', 0)
        oi_change = oi_data.get('changeinOpenInterest', 0)
        
        if price_change > 0 and oi_change > 0: return "🎯 LONG BUILD-UP", 10
        elif price_change < 0 and oi_change > 0: return "⚠️ SHORT BUILD-UP", 2
        elif price_change > 0 and oi_change < 0: return "⚡ SHORT COVERING", 8
        else: return "🛡️ RANGE-BOUND", 5
    except:
        return "⏳ MARKET CLOSED", 5

# 2. Scanner Logic
def scan_stock_v16(sym):
    try:
        ticker = yf.Ticker(sym)
        df = ticker.history(period="5d")
        ltp = df['Close'].iloc[-1]
        flow_status, score = get_institutional_flow(sym)
        
        # Decision logic
        if score >= 8: action = "🚀 BUY ZONE"
        elif score <= 2: action = "📉 SELL ZONE"
        else: action = "⏳ WAIT/WATCH"
            
        return [round(ltp, 2), action, flow_status, score]
    except:
        return [0, "ERR", "ERR", 0]

# 3. Main Controller (Execution Engine)
def main():
    universe = ['TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI', 'MAXHEALTH']
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        data = list(executor.map(lambda s: [s + '.NS'] + scan_stock_v16(s + '.NS'), universe))
    
    # Credentials & Auth
    creds = Credentials.from_service_account_info(
        json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), 
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    # Forceful Update Logic
    sheet.clear()
    
    # Headers in A1:F1
    headers = ['Symbol', 'LTP', 'Action Plan', 'OI Status', 'Insti Score', 'Update Time']
    sheet.update(range_name='A1:F1', values=[headers])
    
    # Data in A2:F6
    timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
    formatted_data = [[*row, timestamp] for row in data]
    sheet.update(range_name='A2:F6', values=formatted_data)
    
    # Freeze Header
    sheet.freeze(rows=1)

if __name__ == "__main__":
    main()
