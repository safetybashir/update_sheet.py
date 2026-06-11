import os
import json
import gspread
import yfinance as yf
import pandas as pd
import requests
from oauth2client.service_account import ServiceAccountCredentials

def send_telegram_alert(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('CHAT_ID')
    if token and chat_id:
        requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=Markdown")

def main():
    # Stocks list yahan define hai, ab error nahi aayega!
    stocks = ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS']
    
    creds_dict = json.loads(os.environ.get('GCP_CREDENTIALS_JSON'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    results = []
    for symbol in stocks:
        try:
            df = yf.Ticker(symbol).history(period="1mo")
            ltp = round(df['Close'].iloc[-1], 2)
            
            # Indicators
            df['VWAP'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / df['Volume'].cumsum()
            df['SMA'] = df['Close'].rolling(20).mean()
            df['STD'] = df['Close'].rolling(20).std()
            df['BB_Low'] = df['SMA'] - (2 * df['STD'])
            
            vwap = round(df['VWAP'].iloc[-1], 2)
            bb_low = round(df['BB_Low'].iloc[-1], 2)
            
            action = '⏳ WAIT'
            if ltp <= bb_low:
                action = '🎯 BUY SIGNAL'
                send_telegram_alert(f"🎯 *RADAR HIT: {symbol}*\n🟢 Entry: {ltp}\n💰 Target: {round(ltp*1.05, 2)}")
            
            results.append([symbol, ltp, action, vwap, bb_low])
        except Exception as e:
            results.append([symbol, 0, "❌ ERROR", 0, 0])
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action', 'VWAP', 'BB_Low']] + results)

if __name__ == "__main__":
    main()
