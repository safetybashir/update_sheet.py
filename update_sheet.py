import os, json, gspread, yfinance as yf, requests
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. Alert Function (Same)
def send_alert(stock, ltp, signal, sl, tg):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('CHAT_ID')
    if token and chat_id:
        msg = f"🎯 *SNIPER V6.0: {stock}*\nPrice: {ltp:.2f}\nAction: {signal}\nSL: {sl}\nTarget: {tg}"
        requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}&parse_mode=Markdown")

# 2. Indicator Logic
def get_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 3. Scanning Logic for 250 Stocks
def scan_stock(sym):
    try:
        # Fetching 3 months of data
        df = yf.Ticker(sym).history(period="3mo")
        if len(df) < 50: return [sym, 0, "DATA ERR", "-", "-", "-", "-", "-"]
            
        ltp = df['Close'].iloc[-1]
        ltp_prev = df['Close'].iloc[-2]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        
        # Calculations
        turnover = ltp * vol
        avg_turnover = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]
        high_20 = df['High'].rolling(20).max().iloc[-2]
        rsi = get_rsi(df).iloc[-1]
        ema_50 = df['Close'].ewm(span=50).mean().iloc[-1]
        sma_50 = df['Close'].rolling(50).mean().iloc[-1]
        sma_50_prev = df['Close'].rolling(50).mean().iloc[-2]
        
        pct_change = ((ltp - ltp_prev) / ltp_prev) * 100
        vol_spike = round(vol / avg_vol, 2)
        atr = (df['High'] - df['Low']).rolling(14).mean().iloc[-1]
        sl = round(ltp - (1.5 * atr), 2)
        tg = round(ltp + (3.0 * atr), 2)
        
        # Logic Priority
        signal = "⏳ SEARCHING..."
        if rsi < 30 and ltp > ema_50: signal = "⚡ REVERSAL BUY"
        elif turnover > (avg_turnover * 1.5): signal = "🚀 VALUE BREAKOUT"
        elif ltp > high_20 and vol > (avg_vol * 1.5): signal = "🚀 MOMENTUM BREAKOUT"
        elif ltp > sma_50 and ltp_prev < sma_50_prev: signal = "📈 TREND REVERSAL"
        
        # Send Alert only for strong signals
        if signal != "⏳ SEARCHING...":
            send_alert(sym, ltp, signal, sl, tg)
            
        return [sym, round(ltp, 2), signal, f"{pct_change:.2f}%", round(rsi, 2), f"{vol_spike}x", sl, tg]
    except:
        return [sym, 0, "ERROR", "-", "-", "-", "-", "-"]

# 4. Main Engine
def main():
    # Aap yahan poore 250 tickers ki list yahan dal sakte hain
    # Ya phir kisi file se read kar sakte hain: universe = open("midcap250.txt").read().splitlines()
    universe = ['TRENT.NS', 'CUMMINSIND.NS', 'PERSISTENT.NS', 'TATAELXSI.NS', 'MAXHEALTH.NS'] # Example list
    
    creds_dict = json.loads(os.environ.get('GCP_CREDENTIALS_JSON'))
    creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    # 250 stocks ke liye max_workers badha sakte hain
    with ThreadPoolExecutor(max_workers=20) as executor:
        report = list(executor.map(scan_stock, universe))
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action', '% Change', 'RSI', 'Vol Spike', 'Stop Loss', 'Target']] + report)

if __name__ == "__main__":
    main()
