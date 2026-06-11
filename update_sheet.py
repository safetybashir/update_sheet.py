import os
import json
import gspread
import yfinance as yf
import pytz
from datetime import datetime as dt
from nsepython import *
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. Institutional Logic
def get_institutional_flow(sym_full):
    try:
        sym = sym_full.split('.')[0]
        oi_data = derivatives_data(sym)
        if not oi_data or 'changeinOpenInterest' not in oi_data: return "⏳ NO DATA", 5
        price_change = oi_data.get('priceChange', 0)
        oi_change = oi_data.get('changeinOpenInterest', 0)
        
        if price_change > 0 and oi_change > 0: return "🎯 LONG BUILD-UP", 10
        elif price_change < 0 and oi_change > 0: return "⚠️ SHORT BUILD-UP", 2
        elif price_change > 0 and oi_change < 0: return "⚡ SHORT COVERING", 8
        else: return "🛡️ RANGE-BOUND", 5
    except: return "⏳ MARKET CLOSED", 5

# 2. Scanner Logic
def scan_stock_v17(sym):
    try:
        ticker = yf.Ticker(sym)
        df = ticker.history(period="5d")
        ltp = df['Close'].iloc[-1]
        flow_status, score = get_institutional_flow(sym)
        
        if score >= 8: action = "🚀 BUY ZONE"
        elif score <= 2: action = "📉 SELL ZONE"
        else: action = "⏳ WAIT/WATCH"
        
        # 6 Data points return kar rahe hain
        return [round(ltp, 2), action, flow_status, score]
    except: return [0, "ERR", "ERR", 0]

# 3. Main Controller with Journaling Columns
def main():
    universe = ['TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI', 'MAXHEALTH']
    with ThreadPoolExecutor(max_workers=5) as executor:
        data = list(executor.map(lambda s: [s + '.NS'] + scan_stock_v17(s + '.NS'), universe))
    
    creds = Credentials.from_service_account_info(
        json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), 
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    sheet.clear()
    
    # 10 Columns total: 6 Auto + 4 Manual
    headers = ['Symbol', 'LTP', 'Action Plan', 'OI Status', 'Insti Score', 'Update Time', 'Buy Price', 'Qty', 'Sell Price', 'P/L']
    sheet.update(range_name='A1:J1', values=[headers])
    
    timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
    # Hum sirf data populate karenge, last 4 columns khali rahenge jise aap manual bharenge
    formatted_data = [[*row, timestamp] for row in data]
    sheet.update(range_name='A2:F6', values=formatted_data)
    
    sheet.freeze(rows=1)
    
    # P/L Column mein Formula add karna (Optional: Sheet mein khud se bhi kar sakte hain)
    # Range J2 se J6 mein formula: =(I2-G2)*H2
    for i in range(2, 7):
        sheet.update_cell(i, 10, f'=IF(ISBLANK(I{i}), "", (I{i}-G{i})*H{i})')

if __name__ == "__main__":
    main()
