import os, json, gspread, yfinance as yf, requests
from google.oauth2.service_account import Credentials
import pandas as pd

def get_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def main():
    universe = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'SBIN.NS', 'ICICIBANK.NS', 'TATAMOTORS.NS']
    
    creds_dict = json.loads(os.environ.get('GCP_CREDENTIALS_JSON'))
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    report = []
    for sym in universe:
        df = yf.Ticker(sym).history(period="3mo") # 3 mahine ka data chahiye indicators ke liye
        if len(df) < 50: continue
            
        ltp = df['Close'].iloc[-1]
        # Turnover (Value) Calculation: Price * Volume
        turnover = ltp * df['Volume'].iloc[-1]
        avg_turnover = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]
        rsi = get_rsi(df).iloc[-1]
        ema_50 = df['Close'].ewm(span=50).mean().iloc[-1]
        
        
        # SMART LOGIC
        signal = "⏳ SEARCHING..."
        if rsi < 30 and ltp > ema_50:
            signal = "⚡ REVERSAL BUY"
            send_alert(sym, ltp) # Alert sirf tabhi jayega
        elif turnover > (avg_turnover * 1.5):
            signal = "🚀 VALUE BREAKOUT"
            send_alert(sym, ltp) # Alert sirf tabhi jayega
            
        report.append([sym, round(ltp, 2), signal])
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action']] + report)

if __name__ == "__main__":
    main()
