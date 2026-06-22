# update_sheet.py – CONNECTION DIAGNOSTIC SCRIPT
import os
import json
import gspread
import logging
import sys
from google.oauth2.service_account import Credentials

# --- Setup Logging ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- Load Secrets ---
try:
    GCP_CREDENTIALS_RAW = os.environ.get('GCP_CREDENTIALS_JSON', '{}')
    logging.info(f"✅ GCP_CREDENTIALS_JSON length: {len(GCP_CREDENTIALS_RAW)}")
    
    GCP_CREDENTIALS = json.loads(GCP_CREDENTIALS_RAW)
    SHEET_ID = os.environ.get('SHEET_ID', '1T0r-MG2oxImCyhJv0q98bdCEnjNschePHBhOtMmW9Bg')
    logging.info(f"✅ SHEET_ID: {SHEET_ID}")
except Exception as e:
    logging.error(f"❌ Failed to load secrets: {e}")
    sys.exit(1)

# --- Step 1: Check Credentials ---
def check_credentials():
    logging.info("🔍 Step 1: Checking Credentials...")
    try:
        required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        for key in required_keys:
            if key not in GCP_CREDENTIALS:
                logging.error(f"❌ Missing key: {key}")
                return False
        logging.info(f"✅ Credentials OK. Client Email: {GCP_CREDENTIALS.get('client_email')}")
        return True
    except Exception as e:
        logging.error(f"❌ Credentials Error: {e}")
        return False

# --- Step 2: Authenticate ---
def test_authentication():
    logging.info("🔍 Step 2: Testing Authentication...")
    try:
        creds = Credentials.from_service_account_info(
            GCP_CREDENTIALS,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        logging.info("✅ Authentication Successful")
        return creds
    except Exception as e:
        logging.error(f"❌ Authentication Failed: {e}")
        return None

# --- Step 3: Connect to Sheet ---
def test_sheet_connection(creds):
    logging.info("🔍 Step 3: Connecting to Google Sheet...")
    try:
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)
        logging.info(f"✅ Sheet Found: {sh.title} (ID: {sh.id})")
        return sh
    except Exception as e:
        logging.error(f"❌ Sheet Connection Failed: {e}")
        return None

# --- Step 4: Write a Test Row ---
def write_test_row(sh):
    logging.info("🔍 Step 4: Writing a test row...")
    try:
        dash_sheet = sh.get_worksheet(0)
        test_data = [["✅ DIAGNOSTIC TEST", "SUCCESSFUL", "Connection Working", "Time: " + str(os.time())]]
        dash_sheet.clear()
        dash_sheet.update(range_name='A1', values=[["🔍 DIAGNOSTIC TEST - " + str(os.time()), "", "", ""]])
        dash_sheet.update(range_name='A2', values=[["Status", "Message", "Details", "Timestamp"]])
        dash_sheet.update(range_name='A3', values=test_data)
        logging.info("✅ Test row written successfully!")
        return True
    except Exception as e:
        logging.error(f"❌ Write Failed: {e}")
        return False

# --- Main Diagnostic ---
def main():
    logging.info("🚀 Starting Connection Diagnostic...")
    
    if not check_credentials():
        logging.error("❌ Diagnostic FAILED at Step 1")
        sys.exit(1)
    
    creds = test_authentication()
    if creds is None:
        logging.error("❌ Diagnostic FAILED at Step 2")
        sys.exit(1)
    
    sh = test_sheet_connection(creds)
    if sh is None:
        logging.error("❌ Diagnostic FAILED at Step 3")
        sys.exit(1)
    
    if write_test_row(sh):
        logging.info("✅ ALL TESTS PASSED! Check your Google Sheet.")
    else:
        logging.error("❌ Diagnostic FAILED at Step 4")

if __name__ == "__main__":
    main()
