import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. GitHub Secrets se Credentials aur Sheet ID nikalna
SCOPE = ["https://google.com", "https://googleapis.com"]

def connect_google_sheets():
    try:
        # GitHub Secrets se encrypted json key padhna
        creds_json = os.environ.get("GCP_CREDENTIALS_JSON")
        sheet_id = os.environ.get("SHEET_ID")
        
        if not creds_json or not sheet_id:
            print("❌ Error: GitHub Secrets (GCP_CREDENTIALS_JSON ya SHEET_ID) missing hain!")
            return None
            
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        
        # URL ke badle direct SHEET_ID se file open karna (Sabse safe aur fast)
        spreadsheet = client.open_by_key(sheet_id) 
        return spreadsheet
    except Exception as e:
        print(f"❌ Google Sheets Connection Error: {e}")
        return None

def fetch_derivatives_data():
    print("🔄 Fetching Live Market Data (F&O Chain + Cash Pricing)...")
    # Mock data testing ke liye (Live market mein yahan aapki main link connect hogi)
    mock_market_feed = {
        "M&M": {
            "high": 3351.7, "low": 3302.0, "close": 3334.0, "ltp": 3354.7, "pivot": 3329.0,
            "volume_spike": "SPIKE ⚡ (2.0x)", "oi_chg": 6.5, "pcr": 1.3, "max_pain": 3300.0,
            "iv_call": 18.5, "iv_put": 14.2, "delta_mom": "Increasing"
        },
        "RELIANCE": {
            "high": 1325.2, "low": 1281.2, "close": 1325.0, "ltp": 1315.0, "pivot": 1310.0,
            "volume_spike": "NORMAL (1.1x)", "oi_chg": 1.2, "pcr": 0.9, "max_pain": 1320.0,
            "iv_call": 12.1, "iv_put": 13.5, "delta_mom": "Decreasing"
        }
    }
    return mock_market_feed

def update_scanner_dashboard():
    sheet = connect_google_sheets()
    if not sheet:
        return
        
    cash_tab = sheet.worksheet("DATA_CASH")
    derivatives_tab = sheet.worksheet("DATA_DERIVATIVES")
    
    tickers_cash = cash_tab.col_values(1)[1:]  # Skip header row
    market_data = fetch_derivatives_data()
    
    cash_updates = []
    derivatives_updates = []
    
    for idx, ticker in enumerate(tickers_cash, start=2):
        if ticker in market_data:
            data = market_data[ticker]
            
            # TAB 1: DATA_CASH Columns Mapping
            cash_updates.append({
                'range': f'B{idx}:E{idx}',
                'values': [[data['high'], data['low'], data['close'], data['ltp']]]
            })
            cash_updates.append({
                'range': f'I{idx}:J{idx}',
                'values': [[data['pivot'], data['volume_spike']]]
            })
            
            # TAB 2: DATA_DERIVATIVES Columns Mapping
            price_change_pct = ((data['ltp'] - data['close']) / data['close']) * 100
            derivatives_updates.append({
                'range': f'C{idx}:D{idx}',
                'values': [[data['pcr'], data['max_pain']]]
            })
            derivatives_updates.append({
                'range': f'F{idx}:G{idx}',
                'values': [[data['oi_chg'], round(price_change_pct, 2)]]
            })
            derivatives_updates.append({
                'range': f'I{idx}:J{idx}',
                'values': [[data['iv_call'], data['iv_put']]]
            })
            derivatives_updates.append({
                'range': f'L{idx}',
                'values': [[data['delta_mom']]]
            })

    if cash_updates:
        cash_tab.batch_update(cash_updates)
    if derivatives_updates:
        derivatives_tab.batch_update(derivatives_updates)
        
    print("✅ System Success: Both back-end tabs updated via Secrets successfully!")

if __name__ == "__main__":
    update_scanner_dashboard()

