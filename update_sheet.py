import os, json, gspread, yfinance as yf, requests, pytz
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

def get_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def scan_stock(sym):
    try:
        df = yf.Ticker(sym).history(period="3mo")
        if len(df) < 50: return [sym, 0, "DATA ERR", "-", "-", "-", "-", "-", "-"]
        
        ltp = df['Close'].iloc[-1]
        ltp_prev = df['Close'].iloc[-2]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        rsi = get_rsi(df).iloc[-1]
        ema_50 = df['Close'].ewm(span=50).mean().iloc[-1]
        atr = (df['High'] - df['Low']).rolling(14).mean().iloc[-1]
        
        # V7.0 Logic: Trend Strength Filter
        pct_change = ((ltp - ltp_prev) / ltp_prev) * 100
        vol_spike = round(vol / avg_vol, 2)
        sl = round(ltp - (1.5 * atr), 2)
        tg = round(ltp + (3.0 * atr), 2)
        
        # Signal Engine
        signal = "⏳ SEARCHING..."
        if rsi < 30 and ltp > ema_50: signal = "⚡ REVERSAL BUY"
        elif vol_spike > 2.0 and pct_change > 2: signal = "🚀 EXPLOSIVE BREAKOUT"
        elif ltp > ema_50 and rsi > 60: signal = "📈 STRONG TREND"
        
        return [sym, round(ltp, 2), signal, f"{pct_change:.2f}%", round(rsi, 2), f"{vol_spike}x", sl, tg]
    except:
        return [sym, 0, "ERROR", "-", "-", "-", "-", "-", "-"]

def main():
    universe = ['TRENT.NS', 'CUMMINSIND.NS', 'PERSISTENT.NS', 'TATAELXSI.NS', 'MAXHEALTH.NS']
    ist = pytz.timezone('Asia/Kolkata')
    
    # Batch Processing for Speed
    with ThreadPoolExecutor(max_workers=20) as executor:
        report = list(executor.map(scan_stock, universe))
    
    # Sheet Update
    creds = Credentials.from_service_account_info(json.loads(os.environ.get('GCP_CREDENTIALS_JSON')), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    timestamp = datetime.now(ist).strftime("%H:%M:%S")
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action', '% Change', 'RSI', 'Vol Spike', 'Stop Loss', 'Target', 'Last Update']])
    sheet.update('A2', [[*row, timestamp] for row in report])

if __name__ == "__main__":
    main()
