import os
import json
import time
from datetime import datetime, timedelta
import io
import zipfile
import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Credentials Setup
creds_json = os.environ.get('GCP_CREDENTIALS_JSON')
if not creds_json:
    raise ValueError("❌ GCP_CREDENTIALS_JSON environment variable not found!")
    
creds_dict = json.loads(creds_json)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Google Sheet ID & Worksheet Name
spreadsheet_id = "15LBUVcxELAmdffUxsboBjrXfuJyM9xC-KZVh6GwBzxg" 
worksheet = client.open_by_key(spreadsheet_id).worksheet("LIVE_MASTER_DASHBOARD")

# 2. NSE UDiFF Data Fetcher (Traded Value & Exclusion Filter)
def fetch_bhavcopy_for_date(date_obj):
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_filename = z.namelist()[0]
                with z.open(csv_filename) as f:
                    df = pd.read_csv(f)
                    
                    sym_col = 'TckrSymb' if 'TckrSymb' in df.columns else 'SYMBOL'
                    close_col = 'ClsPric' if 'ClsPric' in df.columns else 'CLOSE'
                    series_col = 'SctySrs' if 'SctySrs' in df.columns else 'SERIES'
                    
                    # Volume Column Findout
                    vol_col = 'TtlTradgVol'
                    for c in ['TtlTradgVol', 'TtlTrdQty', 'TotTrdQty', 'TOTTRDQTY']:
                        if c in df.columns:
                            vol_col = c
                            break
                    
                    # 1. Sirf EQ series aur ETFs/BEES ko bahar karna
                    if series_col in df.columns:
                        df = df[df[series_col].astype(str).str.strip() == 'EQ']
                    
                    filter_keywords = 'BEES|ETF|GOLD|LIQUID|CASE|SILVER|LIQ'
                    df = df[~df[sym_col].astype(str).str.contains(filter_keywords, case=False, na=False)]
                    
                    # 2. Unwanted Sectors/Names Exclusion (Banks, Finance, Win, Cigarettes, etc.)
                    # Yahan aap aur bhi keywords add kar sakte hain agar chahein
                    exclude_sectors = 'BANK|FIN|HOUSING|CIG|TOBACCO|INSUR|MUTUAL'
                    df = df[~df[sym_col].astype(str).str.contains(exclude_sectors, case=False, na=False)]
                    
                    # 3. Calculate Total Traded Value (Turnover = Volume * Close Price)
                    # Isse asli liquidity pata chalegi na ki sirf chote shares ki quantity
                    df['TRADED_VALUE'] = df[vol_col].astype(float) * df[close_col].astype(float)
                    
                    # 4. Sort by Traded Value (Highest Turnover first) and pick Top 250
                    df_top = df.sort_values(by='TRADED_VALUE', ascending=False).head(250)
                    
                    # Sheet par dikhane ke liye data format: [Symbol, Traded Value (in Crores), Close Price]
                    df_top['TURNOVER_CR'] = (df_top['TRADED_VALUE'] / 10000000).round(2) # Convert to Crores
                    
                    return df_top[[sym_col, 'TURNOVER_CR', close_col]].values.tolist()
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

# 3. Execution Logic
date = datetime.now()
data_to_insert = None
fetched_date_str = ""

for i in range(5): 
    test_date = date - timedelta(days=i)
    if test_date.weekday() >= 5: 
        continue
        
    data_to_insert = fetch_bhavcopy_for_date(test_date)
    if data_to_insert:
        fetched_date_str = test_date.strftime('%d-%b-%Y')
        break

# 4. Update Sheet with Headers and Clean Layout
if data_to_insert:
    worksheet.clear()  # Clear sheet completely
    
    # Write Column Headers in Row 1 (Ab Volume ki jagah Traded Value (Cr) aayega)
    headers = ["STOCK SYMBOL", "TRADED VALUE (CR)", "CLOSE PRICE"]
    worksheet.update('A1', [headers])
    
    # Write Top 250 Stocks Data starting from Row 2
    worksheet.update('A2', data_to_insert)
    
    # Status Message at E1
    ist_now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%d-%b %H:%M')
    status_msg = f"Data Date: {fetched_date_str} | Last Update: {ist_now} (IST)"
    worksheet.update('E1', [[status_msg]])
    
    print("SUCCESS: Sheet Updated with Traded Value & Sector Filtering!")
else:
    print("❌ Failed to fetch Bhavcopy data for recent days.")
