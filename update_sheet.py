import os, json, gspread, yfinance as yf, requests
from google.oauth2.service_account import Credentials

# 1. Alert Function
def send_alert(stock, ltp):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('CHAT_ID')
    if token and chat_id:
        msg = f"🚀 *SNIPER RADAR: {stock}*\nPrice: {ltp:.2f}\nAction: Detected!"
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}&parse_mode=Markdown"
        requests.get(url)

# 2. Indicator: RSI
def get_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 3. Main Engine
def main():
    universe = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HINDUNILVR.NS', 'SBIN.NS', 'ICICIBANK.NS', 'TATAMOTORS.NS']
    
    creds_dict = json.loads(os.environ.get('GCP_CREDENTIALS_JSON'))
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    report = []
    for sym in universe:
        df = yf.Ticker(sym).history(period="3mo")
        if len(df) < 50: continue
            
        # Data Points
        ltp = df['Close'].iloc[-1]
        ltp_prev = df['Close'].iloc[-2]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        turnover = ltp * vol
        avg_turnover = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]
        high_20 = df['High'].rolling(20).max().iloc[-2]
        rsi = get_rsi(df).iloc[-1]
        ema_50 = df['Close'].ewm(span=50).mean().iloc[-1]
        sma_50 = df['Close'].rolling(50).mean().iloc[-1]
        sma_50_prev = df['Close'].rolling(50).mean().iloc[-2]
        
        # Priority Logic
        signal = "⏳ SEARCHING..."
        if rsi < 30 and ltp > ema_50:
            signal = "⚡ REVERSAL BUY"
            send_alert(sym, ltp)
        elif turnover > (avg_turnover * 1.5):
            signal = "🚀 VALUE BREAKOUT"
            send_alert(sym, ltp)
        elif ltp > high_20 and vol > (avg_vol * 1.5):
            signal = "🚀 MOMENTUM BREAKOUT"
            send_alert(sym, ltp)
        elif ltp > sma_50 and ltp_prev < sma_50_prev:
            signal = "📈 TREND REVERSAL"
            send_alert(sym, ltp)
            
        report.append([sym, round(ltp, 2), signal])
    
    # Sheet Update
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action']] + report)

if __name__ == "__main__":
    main()
