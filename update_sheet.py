import os
import yfinance as yf
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def main():
    # 1. Stocks List
    stocks = ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS']
    
    # 2. Credentials Setup
    creds_raw = os.environ.get('GCP_CREDENTIALS_JSON')
    creds_dict = json.loads(creds_raw)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    )
    client = gspread.authorize(creds)
    
    # 3. Sheet Connect (Correct Sequence)
    sheet_id = os.environ.get('SHEET_ID')
    spreadsheet = client.open_by_key(sheet_id)
    
    # PEHLI TAB UTHANE KA SABSE SAFE TAREEKA (Name ka panga khatam)
    sheet = spreadsheet.get_worksheet(0)
    
  # 4. Processing Loop
    results = []
    for symbol in stocks:
        try:
            # Ticker data fetch karna
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")
            
            # Check karein data empty toh nahi
            if not data.empty:
                ltp = round(data['Close'].iloc[-1], 2)
            else:
                ltp = 0.0
            
            # Logic
            action = '⏳ WAIT'
            if ltp > 1000:
                action = '🚀 BUY'
                
            results.append([symbol, ltp, action])
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            results.append([symbol, 0.0, "❌ ERROR"])
    
    # 5. Sheet Update
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action']] + results)

if __name__ == "__main__":
    main()
