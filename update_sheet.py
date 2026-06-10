import os
import json
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials

def main():
    # 1. Stocks List (Future mein bas yahan naye stocks add kariye)
    stocks = ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS']
    
    # 2. Credentials Setup
    creds_raw = os.environ.get('GCP_CREDENTIALS_JSON')
    creds_dict = json.loads(creds_raw)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    )
    client = gspread.authorize(creds)
    
    # 3. Sheet Connect (GitHub Secrets mein SHEET_ID save rakhein)
    sheet_id = os.environ.get('SHEET_ID')
    spreadsheet = client.open_by_key(sheet_id)
    # Agar tab ka naam "Sheet1" hai toh yahan "Sheet1" likhein
    sheet = spreadsheet.worksheet('Sheet1') 
    
    # 4. Processing Loop
    results = []
    for symbol in stocks:
        # Yahan aapka logic aayega
        action = '⏳ WAIT' 
        results.append([symbol, 0, action])
    
    # 5. Sheet Update
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action']] + results)

if __name__ == "__main__":
    main()
