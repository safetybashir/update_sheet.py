import os
import json
import gspread
import yfinance as yf
import requests
from oauth2client.service_account import ServiceAccountCredentials

# Telegram Alert Function
def send_telegram_alert(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}"
    requests.get(url)

def main():
    stocks = ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS']
    
    creds_raw = os.environ.get('GCP_CREDENTIALS_JSON')
    creds_dict = json.loads(creds_raw)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    results = []
    for symbol in stocks:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")
            ltp = round(data['Close'].iloc[-1], 2)
            
            action = '⏳ WAIT'
            if ltp > 1000: # Aapka Buy Logic
                action = '🚀 BUY'
                # Yahan Telegram alert trigger hoga
                send_telegram_alert(f"📢 SIGNAL: {symbol} is at {ltp}. Action: {action}")
                
            results.append([symbol, ltp, action])
        except Exception as e:
            results.append([symbol, 0, "❌ ERROR"])
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action']] + results)

if __name__ == "__main__":
    main()
