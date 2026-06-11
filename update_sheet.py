import os, json, gspread, yfinance as yf, requests
from oauth2client.service_account import ServiceAccountCredentials

def send_alert(stock, ltp):
    msg = f"🚀 *SNIPER RADAR: {stock}*\nPrice: {ltp}\nVolume Blast & Breakout detected!"
    requests.get(f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_TOKEN')}/sendMessage?chat_id={os.environ.get('CHAT_ID')}&text={msg}&parse_mode=Markdown")

def main():
    # Poora Nifty 50 scan karne ke liye symbols (Short list for example)
    universe = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HINDUNILVR.NS', 'SBIN.NS', 'ICICIBANK.NS'] 
    
    # Auth setup (purana hi rahega)
    creds_dict = json.loads(os.environ.get('GCP_CREDENTIALS_JSON'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ['https://spreadsheets.google.com/feeds', 'https://spreadsheets.google.com/drive'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    report = []
    for sym in universe:
        df = yf.Ticker(sym).history(period="1mo")
        ltp = df['Close'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        high_20 = df['High'].rolling(20).max().iloc[-2] # Pichle 20 din ka high
        
        # SNIPER CONDITION
        if ltp > high_20 and vol > (avg_vol * 1.5):
            action = '🚀 BREAKOUT'
            send_alert(sym, ltp)
        else:
            action = '⏳ SEARCHING...'
            
        report.append([sym, ltp, action])
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action']] + report)

if __name__ == "__main__":
    main()
