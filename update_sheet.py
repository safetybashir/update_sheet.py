import os
import json
import gspread
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
from oauth2client.service_account import ServiceAccountCredentials

# Telegram Alert Function
def send_telegram_alert(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('CHAT_ID')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=Markdown"
        requests.get(url)

def main():
    stocks = ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS']
    creds_dict = json.loads(os.environ.get('GCP_CREDENTIALS_JSON'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    # Purana data read karo taaki cooldown check kar sakein
    existing_data = sheet.get_all_records()
    results = []

    for symbol in stocks:
        try:
            df = yf.Ticker(symbol).history(period="1mo")
            df.ta.vwap(append=True)
            df.ta.bbands(length=20, std=2, append=True)
            
            ltp = round(df['Close'].iloc[-1], 2)
            vwap = round(df['VWAP_14'].iloc[-1], 2)
            bb_low = round(df['BBL_20_2.0'].iloc[-1], 2)
            
            # Smart Radar Logic
            action = '⏳ WAIT'
            if ltp <= bb_low:
                action = '🎯 BUY SIGNAL'
                entry = ltp
                sl = round(ltp * 0.98, 2)
                target = round(ltp * 1.05, 2)
                
                # Cooldown Check: Agar pehle se BUY tha, toh alert mat bhejo
                prev_status = next((d['Action'] for d in existing_data if d['Symbol'] == symbol), None)
                if prev_status != '🎯 BUY SIGNAL':
                    send_telegram_alert(f"🎯 *RADAR HIT: {symbol}*\n🟢 Entry: {entry}\n🔴 SL: {sl}\n💰 Target: {target}")
            
            results.append([symbol, ltp, action, vwap, bb_low])
        except Exception:
            results.append([symbol, 0, "❌ ERROR", 0, 0])
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action', 'VWAP', 'BB_Low']] + results)

if __name__ == "__main__":
    main()
