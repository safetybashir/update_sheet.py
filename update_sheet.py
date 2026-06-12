import os
import json
import gspread
import yfinance as yf
import pytz
import pandas as pd
from datetime import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. NEW: Institutional Logic based on Price Action & Volume
def get_invincible_score(ticker_obj):
    try:
        # 5 din ka data lete hain
        df = ticker_obj.history(period="5d")
        ltp = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].mean()
        
        # Logic: Price up + Volume Spike = Institutional Buying
        score = 5
        if ltp > prev_close and vol > avg_vol: score = 10  # Bullish Breakout
        elif ltp < prev_close and vol > avg_vol: score = 2   # Institutional Dumping
        elif ltp > prev_close: score = 8                    # Mild Buying
        
        status = "🎯 STRONG BUY" if score >= 8 else "⚠️ WEAK/SELL" if score <= 2 else "🛡️ RANGE-BOUND"
        return status, score, round(ltp, 2)
    except:
        return "⏳ SYNCING", 5, 0

# 2. Main Controller
def main():
    universe = ['TRENT', 'CUMMINSIND', 'PERSISTENT', 'TATAELXSI','TORNTPHARM', 'WAAREEENER', 'SOLARINDS', 'ALKEM', 'DIVISLAB', 'JSWSTEEL', 'APOLLOHOSP', 'POWERINDIA', 'MAXHEALTH']
    
    # Credentials setup
    creds = Credentials.from_service_account_info(
        json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), 
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    sh = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID'))
    dash_sheet = sh.get_worksheet(0)
    
    # Process
    final_data = []
    for sym in universe:
        ticker = yf.Ticker(sym + ".NS")
        status, score, ltp = get_invincible_score(ticker)
        action = "🚀 BUY ZONE" if score >= 8 else "📉 SELL ZONE" if score <= 2 else "⏳ WAIT/WATCH"
        timestamp = dt.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
        final_data.append([sym + ".NS", ltp, action, status, score, timestamp])
    
    # 1. Clear sheet safely
    dash_sheet.clear()
    
    # 2. Update Header
    header = [['Symbol', 'LTP', 'Action Plan', 'Trend Status', 'Insti Score', 'Update Time']]
    dash_sheet.update(range_name='A1', values=header)
    
    # 3. Update Data
    if final_data:
        dash_sheet.update(range_name='A2', values=final_data)
        
    # 4. Freeze Header
    dash_sheet.freeze(rows=1)

if __name__ == "__main__":
    main()
