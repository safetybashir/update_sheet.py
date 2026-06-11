import os
import json
import gspread
import yfinance as yf
import pytz
from datetime import datetime as dt
from nsepython import *
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. Institutional Logic: OI + Price Action Fusion
def get_institutional_flow(sym):
    try:
        # NSE Derivative Data for OI
        oi_data = derivatives_data(sym.split('.')[0])
        price_change = oi_data.get('priceChange', 0)
        oi_change = oi_data.get('changeinOpenInterest', 0)
        
        if price_change > 0 and oi_change > 0:
            return "🎯 LONG BUILD-UP", 10
        elif price_change < 0 and oi_change > 0:
            return "⚠️ SHORT BUILD-UP", 2
        elif price_change > 0 and oi_change < 0:
            return "⚡ SHORT COVERING", 8
        else:
            return "🛡️ RANGE-BOUND", 5
    except:
        return "DATA ERR", 0

# 2. Scanner Logic
def scan_stock_v13(sym):
    try:
        df = yf.Ticker(sym).history(period="1mo")
        ltp = df['Close'].iloc[-1]
        flow_status, score = get_institutional_flow(sym)
        signal = "🔥 ALPHA MOVE" if score > 7 else "⏳ SEARCHING"
        return [round(ltp, 2), signal, flow_status, score]
    except:
        return [0, "ERR", "ERR", 0]

# 3. Main Execution Controller
def main():
    universe = ['TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI', 'MAXHEALTH']
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        data = list(executor.map(lambda s: [s + '.NS'] + scan_stock_v13(s + '.NS'), universe))
    
    # Google Sheet Auth
    creds = Credentials.from_service_account_info(json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
    
    # Final Update
    sheet.clear()
    sheet.update(range_name='A1', values=[['Symbol', 'LTP', 'Signal', 'OI Status', 'Insti Score', 'Last Update']])
    sheet.update(range_name='A2', values=[[*row, timestamp] for row in data])

if __name__ == "__main__":
    main()
