# update_sheet.py – DEBUG VERSION
import os
import json
import gspread
import yfinance as yf
import logging
import sys
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.DEBUG)

try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
    logging.info(f"SHEET_ID: {SHEET_ID}")
except Exception as e:
    logging.error(f"Failed: {e}")
    sys.exit(1)

try:
    # Test Yahoo Finance
    ticker = yf.Ticker("RELIANCE.NS")
    df = ticker.history(period="1d")
    logging.info(f"✅ YFinance working. Close price: {df['Close'].iloc[-1] if not df.empty else 'No data'}")
    
    # Test Google Sheet
    creds = Credentials.from_service_account_info(GCP_CREDENTIALS, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)
    logging.info(f"✅ Sheet found: {sh.title}")
    
    # Write test
    ws = sh.get_worksheet(0)
    ws.clear()
    ws.update('A1', [['DEBUG TEST', 'SUCCESS']])
    logging.info("✅ Test row written")
    
except Exception as e:
    logging.error(f"❌ Error: {e}")
