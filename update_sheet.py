import os
import json
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials

def main():
    # 1. Stocks List (Yahan define kiya hai)
    stocks = ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS']
    
    # 2. Credentials
    creds_raw = os.environ.get('GCP_CREDENTIALS_JSON')
    creds_dict = json.loads(creds_raw)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    )
    client = gspread.authorize(creds)
    
    # 3. Loop (Ab yahan 'stocks' define hai, error nahi aayega)
    results = []
    for symbol in stocks:
        # Example logic
        action = '⏳ WAIT'
        results.append({'Symbol': symbol, 'LTP': 0, 'Action': action})
    
    # 4. Sheet Update
    sheet = client.open_by_key(os.environ.get('SHEET_ID')).worksheet('LIVE_DASHBOARD')
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action']] + [[r['Symbol'], r['LTP'], r['Action']] for r in results])

if __name__ == "__main__":
    main()
