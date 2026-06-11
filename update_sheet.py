import os, json, gspread, yfinance as yf, requests
from google.oauth2.service_account import Credentials

# 1. PEHLE FUNCTION DEFINITION (Isse Python pehle padhega)
def send_alert(stock, ltp):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('CHAT_ID')
    if token and chat_id:
        msg = f"🚀 *SNIPER RADAR: {stock}*\nPrice: {ltp:.2f}\nAction: Detected!"
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}&parse_mode=Markdown"
        requests.get(url)

def get_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 2. PHIR MAIN LOGIC
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
            
        ltp = df['Close'].iloc[-1]
        turnover = ltp * df['Volume'].iloc[-1]
        avg_turnover = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]
        rsi = get_rsi(df).iloc[-1]
        ema_50 = df['Close'].ewm(span=50).mean().iloc[-1]
        
        signal = "⏳ SEARCHING..."
        # Logic check
        if rsi < 30 and ltp > ema_50:
            signal = "⚡ REVERSAL BUY"
            send_alert(sym, ltp) 
        elif turnover > (avg_turnover * 1.5):
            signal = "🚀 VALUE BREAKOUT"
            send_alert(sym, ltp) 
         # Strategy 1: Momentum
if ltp > high_20 and vol > (avg_vol * 1.5):
    signal = "🚀 MOMENTUM BREAKOUT"

# Strategy 2: Reversal (Price 50 DMA ke upar nikal raha hai)
sma_50 = df['Close'].rolling(50).mean().iloc[-1]
if ltp > sma_50 and ltp_prev < sma_50_prev: # Cross-over
    signal = "📈 TREND REVERSAL"   
        report.append([sym, round(ltp, 2), signal])
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'REVERSAL', '🚀 MOMENTUM BREAKOUT', 'Action']] + report)

if __name__ == "__main__":
    main()
