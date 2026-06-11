import os, json, gspread, yfinance as yf, pytz
from datetime import datetime
from nsepython import * from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. Institutional OI & Flow Analysis
def get_institutional_flow(sym):
    try:
        # Fetching Derivative Data (OI)
        oi_data = derivatives_data(sym)
        # Assuming we extract price change and OI change from NSE data
        price_change = oi_data.get('priceChange', 0)
        oi_change = oi_data.get('changeinOpenInterest', 0)
        
        if price_change > 0 and oi_change > 0:
            return "🎯 LONG BUILD-UP", 10 # Strong Institutional Buy
        elif price_change < 0 and oi_change > 0:
            return "⚠️ SHORT BUILD-UP", 2  # Strong Institutional Sell
        elif price_change > 0 and oi_change < 0:
            return "⚡ SHORT COVERING", 8   # Explosive Reversal
        else:
            return "🛡️ RANGE-BOUND", 5
    except:
        return "DATA ERR", 0

# 2. Sniper V13 Logic with Confluence
def scan_stock_v13(sym):
    try:
        # Price Action (Yahoo Finance)
        df = yf.Ticker(sym).history(period="1mo")
        ltp = df['Close'].iloc[-1]
        
        # Institutional Flow (NSE)
        flow_status, score = get_institutional_flow(sym)
        
        # Final Signal
        signal = "🔥 ALPHA MOVE" if score > 7 else "⏳ SEARCHING"
        
        return [round(ltp, 2), signal, flow_status, score]
    except:
        return [0, "ERR", "ERR", 0]

# 3. Execution
def main():
    universe = ['TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI', 'MAXHEALTH']
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        data = list(executor.map(lambda s: [s + '.NS'] + scan_stock_v13(s + '.NS'), universe))
    
    # Sheet Update
    creds = Credentials.from_service_account_info(json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Signal', 'OI Status', 'Insti Score', 'Last Update']])
    sheet.update('A2', [[*row, datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")] for row in data])

if __name__ == "__main__":
    main()
