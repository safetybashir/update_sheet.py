# update_sheet.py – CONNECTION TEST (Fixed)
import os
import json
import gspread
import logging
import sys
from datetime import datetime
from google.oauth2.service_account import Credentials

# --- Setup Logging ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Load Secrets ---
try:
    GCP_CREDENTIALS = json.loads(os.environ.get('GCP_CREDENTIALS_JSON', '{}'))
    SHEET_ID = os.environ.get('SHEET_ID', '1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg')
    logging.info(f"✅ SHEET_ID: {SHEET_ID}")
except Exception as e:
    logging.error(f"❌ Failed to load secrets: {e}")
    sys.exit(1)

# --- Connection Test ---
def test_connection():
    logging.info("🚀 Testing Google Sheet connection...")
    try:
        # 1. Authenticate
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        logging.info("✅ Authentication successful")
        
        # 2. Connect to sheet
        client = gspread.authorize(creds)
        logging.info("✅ Client authorized")
        
        # 3. Open sheet
        sh = client.open_by_key(SHEET_ID)
        logging.info(f"✅ Sheet opened: {sh.title} (ID: {sh.id})")
        
        # 4. Get worksheet
        ws = sh.get_worksheet(0)
        logging.info(f"✅ Worksheet: {ws.title}")
        
        # 5. Write test
        ws.clear()
        ws.update('A1', [['✅ CONNECTION TEST SUCCESSFUL', 'SHEET_ID: ' + SHEET_ID, 'Time: ' + str(datetime.now())]])
        logging.info("✅ Test row written successfully")
        
        return True
    except Exception as e:
        logging.error(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
