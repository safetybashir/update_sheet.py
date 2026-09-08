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

# 2. Super-Charged Sniper Engine with Dynamic Thresholds
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
                    
                    df.columns = [col.strip().upper() for col in df.columns]
                    
                    sym_col = 'TCKRSYMB' if 'TCKRSYMB' in df.columns else ('SYMBOL' if 'SYMBOL' in df.columns else None)
                    close_col = 'CLSPRIC' if 'CLSPRIC' in df.columns else ('CLOSE' if 'CLOSE' in df.columns else None)
                    high_col = 'HIGHPRIC' if 'HIGHPRIC' in df.columns else ('HIGH' if 'HIGH' in df.columns else None)
                    low_col = 'LOWPRIC' if 'LOWPRIC' in df.columns else ('LOW' if 'LOW' in df.columns else None)
                    
                    prev_close_col = None
                    for col in df.columns:
                        if 'PRV' in col or 'PVS' in col or ('PREV' in col and 'CLS' in col):
                            prev_close_col = col
                            break
                            
                    series_col = 'SCTYSRS' if 'SCTYSRS' in df.columns else ('SERIES' if 'SERIES' in df.columns else None)
                    
                    vol_col = 'TTLTRADGVOL'
                    for c in ['TTLTRADGVOL', 'TTLTRDQTY', 'TOTTRDQTY']:
                        if c in df.columns:
                            vol_col = c
                            break
                    
                    if not sym_col or not close_col:
                        return None

                    # --- FILTERS ---
                    if series_col and series_col in df.columns:
                        df = df[df[series_col].astype(str).str.strip() == 'EQ']
                    
                    filter_keywords = 'BEES|ETF|GOLD|LIQUID|CASE|SILVER|LIQ'
                    df = df[~df[sym_col].astype(str).str.contains(filter_keywords, case=False, na=False)]
                    
                    exclude_sectors = 'BANK|FIN|HOUSING|CIG|TOBACCO|INSUR|MUTUAL|CAPITAL|FINSERV|CREDIT|INVEST|BREW|SPIRIT|ALCOHOL|LIQUOR'
                    df = df[~df[sym_col].astype(str).str.contains(exclude_sectors, case=False, na=False)]
                    
                    df = df[df[close_col].astype(float) >= 150.0]
                    
                    df['TRADED_VALUE'] = df[vol_col].astype(float) * df[close_col].astype(float)
                    
                    if prev_close_col and prev_close_col in df.columns:
                        df['DAY_CHANGE_PCT'] = ((df[close_col].astype(float) - df[prev_close_col].astype(float)) / df[prev_close_col].astype(float)) * 100
                    else:
                        df['DAY_CHANGE_PCT'] = 0.0

                    df_top = df.sort_values(by='TRADED_VALUE', ascending=False).head(150)
                    
                    processed_data = []
                    for _, row in df_top.iterrows():
                        symbol = row[sym_col]
                        close_p = round(float(row[close_col]), 2)
                        turnover_cr = round(float(row['TRADED_VALUE']) / 10000000, 2)
                        change_pct = round(float(row['DAY_CHANGE_PCT']), 2)
                        
                        high_p = float(row[high_col]) if high_col and high_col in df.columns else close_p
                        low_p = float(row[low_col]) if low_col and low_col in df.columns else close_p
                        prev_c = float(row[prev_close_col]) if prev_close_col and prev_close_col in df.columns else close_p
                        
                        # --- Col E: DYNAMIC BUY & ROCKET RADAR ---
                        buy_signal = "—"
                        if (turnover_cr >= 500 and change_pct >= 2.0) or (turnover_cr >= 150 and change_pct >= 8.0):
                            buy_signal = "🟢 ROCKET BLAST (BUY)"
                        elif (turnover_cr >= 400 and change_pct >= 1.5) or (turnover_cr >= 200 and change_pct >= 5.0):
                            buy_signal = "🎯 SNIPER BULL HIT (BUY)"
                        elif turnover_cr >= 1000 and (-0.6 <= change_pct <= 0.6):
                            buy_signal = "⚡ COILED SPRING (ACCUMULATION)"
                        elif change_pct > 0:
                            buy_signal = "📈 MILD BULLISH"

                        # --- Col F: SELL & DUMP RADAR ---
                        sell_signal = "—"
                        if (turnover_cr >= 500 and change_pct <= -2.0) or (turnover_cr >= 150 and change_pct <= -5.0):
                            sell_signal = "🔴 SHARP DUMP (SELL/EXIT)"
                        elif (turnover_cr >= 400 and change_pct <= -1.5) or (turnover_cr >= 200 and change_pct <= -3.0):
                            sell_signal = "⚠️ SNIPER BEAR HIT (INSTI SELL)"

                        # --- Col G: BULL TRAP DETECTOR ---
                        upper_wick_pct = ((high_p - max(close_p, prev_c)) / prev_c) * 100 if prev_c > 0 else 0
                        
                        if turnover_cr >= 250 and upper_wick_pct >= 1.5 and change_pct < 1.0:
                            bull_trap = "🚨 BULL TRAP (TOP REJECTION)"
                        elif turnover_cr >= 400 and change_pct <= -1.0:
                            bull_trap = "⚠️ BEAR TRAP / DUMP ZONE"
                        else:
                            bull_trap = "✅ CLEAN PRICE ACTION"
                            
                        processed_data.append({
                            'symbol': symbol,
                            'turnover': turnover_cr,
                            'close': close_p,
                            'change_pct': change_pct,
                            'change_str': f"{change_pct:+.2f}%",
                            'buy': buy_signal,
                            'sell': sell_signal,
                            'trap': bull_trap
                        })
                        
                    # Sort by Day Change % (Highest Gainers on Top)
                    processed_data.sort(key=lambda x: x['change_pct'], reverse=True)
                    
                    final_rows = [[item['symbol'], item['turnover'], item['close'], item['change_str'], item['buy'], item['sell'], item['trap']] for item in processed_data]
                    return final_rows
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# 3. Execution Trigger
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

# 4. Sheet Output
if data_to_insert:
    worksheet.clear()  
    
    headers = ["STOCK SYMBOL", "TRADED VALUE (CR)", "CLOSE PRICE", "DAY CHANGE %", "🟢 BUY / ROCKET RADAR", "🔴 SELL / DUMP RADAR", "🚨 BULL TRAP ALERT"]
    worksheet.update('A1', [headers])
    worksheet.update('A2', data_to_insert)
    
    ist_now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%d-%b %H:%M')
    status_msg = f"Data Date: {fetched_date_str} | Updated: {ist_now} (IST)"
    worksheet.update('I1', [[status_msg]])
    
    print("SUCCESS: Super-Charged Sheet Updated with Dynamic Rules!")
else:
    print("❌ Failed to fetch data.")
