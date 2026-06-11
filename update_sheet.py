import os, json, gspread, yfinance as yf, numpy as np, pytz
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. New Institutional Indicators
def calculate_adx(df, period=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    plus_di = 100 * (high.diff().clip(lower=0)).rolling(period).mean() / (high - low).rolling(period).mean()
    minus_di = 100 * ((-low.diff()).clip(lower=0)).rolling(period).mean() / (high - low).rolling(period).mean()
    adx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    return round(adx.fillna(0).iloc[-1], 2)

# 2. Alpha Predator logic with New Columns
def scan_stock_v12(sym):
    try:
        df = yf.Ticker(sym).history(period="6mo")
        ltp = df['Close'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        vol_strength = round(df['Volume'].iloc[-1] / avg_vol, 2)
        adx = calculate_adx(df)
        
        # Confluence
        is_bullish = ltp > df['Close'].ewm(span=50).mean().iloc[-1]
        signal = "🎯 ALPHA BUY" if is_bullish and adx > 25 else "🛡️ DEFENSIVE"
        
        risk_score = 1 if vol_strength > 1.5 and adx > 25 else 3
        sl = round(ltp - (1.5 * (df['High']-df['Low']).mean()), 2)
        tg = round(ltp + (3.0 * (df['High']-df['Low']).mean()), 2)
        
        return [round(ltp, 2), signal, sl, tg, adx, vol_strength, risk_score]
    except:
        return [0, "ERR", "-", "-", 0, 0, 5]

# 3. Execution
def main():
    universe = ['TRENT.NS', 'CUMMINSIND.NS', 'PERSISTENT.NS', 'TATAELXSI.NS', 'MAXHEALTH.NS']
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        data = list(executor.map(lambda s: [s] + scan_stock_v12(s), universe))
    
    # Sheet Update
    creds = Credentials.from_service_account_info(json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Signal', 'SL', 'Target', 'ADX', 'Vol Strength', 'Risk Score', 'Last Update']])
    sheet.update('A2', [[*row, datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")] for row in data])

if __name__ == "__main__":
    main()
