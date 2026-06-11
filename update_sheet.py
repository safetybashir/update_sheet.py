import os, json, gspread, yfinance as yf, pytz
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. Multi-Timeframe Confluence Engine
def get_alpha_signal(sym):
    try:
        # Daily: Trend Direction
        df_d = yf.Ticker(sym).history(period="6mo", interval="1d")
        ema_50 = df_d['Close'].ewm(span=50).mean().iloc[-1]
        is_bullish_trend = df_d['Close'].iloc[-1] > ema_50
        
        # 15m: Momentum Direction
        df_15 = yf.Ticker(sym).history(period="5d", interval="15m")
        momentum = df_15['Close'].iloc[-1] > df_15['Close'].rolling(20).mean().iloc[-1]
        
        ltp = df_d['Close'].iloc[-1]
        atr = (df_d['High'] - df_d['Low']).rolling(14).mean().iloc[-1]
        
        # Logic: Alpha Confluence
        if is_bullish_trend and momentum:
            signal = "🎯 ALPHA BUY"
        elif is_bullish_trend and not momentum:
            signal = "⚡ PULLBACK"
        else:
            signal = "🛡️ DEFENSIVE"
            
        sl = round(ltp - (1.5 * atr), 2)
        tg = round(ltp + (3.0 * atr), 2)
        return [round(ltp, 2), signal, sl, tg]
    except:
        return [0, "DATA ERR", "-", "-"]

# 2. Main Execution
def main():
    universe = ['TRENT.NS', 'CUMMINSIND.NS', 'PERSISTENT.NS', 'TATAELXSI.NS', 'MAXHEALTH.NS']
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Map universe to results
        data = list(executor.map(lambda s: [s] + get_alpha_signal(s), universe))
    
    # Sheet Update
    creds = Credentials.from_service_account_info(json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    timestamp = datetime.now(pytz.timezone('Asia/Kolkata')).strftime("%H:%M:%S")
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Signal', 'SL', 'Target', 'Last Update']])
    sheet.update('A2', [[*row, timestamp] for row in data])

if __name__ == "__main__":
    main()
