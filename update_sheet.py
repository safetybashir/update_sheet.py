import os, json, gspread, yfinance as yf, requests
from google.oauth2.service_account import Credentials

def send_alert(stock, ltp):
    msg = f"🚀 *SNIPER RADAR: {stock}*\nPrice: {ltp:.2f}\nVolume Blast & Breakout detected!"
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('CHAT_ID')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}&parse_mode=Markdown"
        requests.get(url)

def main():
    universe = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HINDUNILVR.NS', 'SBIN.NS', 'ICICIBANK.NS'] 
    
    # Naya Auth Setup (No oauth2client anymore)
    creds_dict = json.loads(os.environ.get('GCP_CREDENTIALS_JSON'))
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    report = []
    for sym in universe:
        ticker = yf.Ticker(sym)
        df = ticker.history(period="1mo")
        if df.empty: continue
            
        ltp = df['Close'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        high_20 = df['High'].rolling(20).max().iloc[-2]
        
        if ltp > high_20 and vol > (avg_vol * 1.5):
            action = '🚀 BREAKOUT'
            send_alert(sym, ltp)
        else:
            action = '⏳ SEARCHING...'
            
        report.append([sym, round(ltp, 2), action])
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action']] + report)

if __name__ == "__main__":
    main()
