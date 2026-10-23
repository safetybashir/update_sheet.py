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

# --- STRICT CLEAN F&O STOCKS WHITELIST ---
STRICT_FNO_WHITELIST = {
    "INFY", "PAYTM", "BHARTIARTL", "ETERNAL", "TCS", "TMPV", "M&M", "OFSS", "KAYNES", "LT",
    "POWERINDIA", "APOLLOHOSP", "DIXON", "MARUTI", "PFC", "BHEL", "LAURUSLABS", "TRENT",
    "SWIGGY", "SONACOMS", "POLYCAB", "GRASIM", "DLF", "HINDALCO", "ZYDUSLIFE", "BEL",
    "SOLARINDS", "MOTHERSON", "ULTRACEMCO", "COALINDIA", "FORTIS", "INDIGO", "HINDZINC",
    "HCLTECH", "MAXHEALTH", "TORNTPHARM", "GLENMARK", "HAL", "TITAN", "SAIL", "LTF",
    "HINDPETRO", "TVSMOTOR", "POWERGRID", "CUMMINSIND", "PERSISTENT", "CDSL", "CIPLA",
    "ASHOKLEY", "KALYANKJIL", "HEROMOTOCO", "WIPRO", "AAREEENER", "IREDA", "EICHERMOT",
    "TECHM", "COFORGE", "NAUKRI", "HINDUNILVR", "DELHIVERY", "GVT&D", "BAJAJ-AUTO",
    "JSWSTEEL", "SUNPHARMA", "LTMR", "RECLTD", "DRREDDY", "ONGC", "OBEROIRLTY", "NYKAA",
    "UPL", "DMART", "FORCEMOT", "INDUSTOWER", "BHARATFORG", "AUROPHARMA", "PIIND",
    "BDL", "IOC", "ASIANPAINT", "BIOCON", "GMRAIRPORT", "JSWENERGY", "LODHA", "GAIL",
    "MAZDOCK", "PHOENIXLTD", "BOSCHLTD", "LUPIN", "BLUESTARCO", "RELIANCE", "NMDC",
    "TATACONSUM", "CGPOWER", "ANGELONE", "INOXWIND", "MANKIND", "PIDILITIND", "APLAPOLLO",
    "AMBER", "NATIONALUM", "COLPAL", "KEI", "KPITTECH", "TATAPOWER", "PAGEIND", "BPCL",
    "COCHINSHIP", "ABB", "TATAELXSI", "CAMS", "BRITANNIA", "NESTLEIND", "ASTRAL",
    "RVNL", "JINDALSTEL", "GODREJPROP", "PRESTIGE", "JUBLFOOD", "AMBUJACEM", "MPHASIS",
    "DALBHARAT", "VOLTAS", "PREMIERENE", "SUPREMEIND", "KFINTECH", "MARICO", "HAVELLS",
    "UNOMINDA", "CONCOR", "NBCC", "SIEMENS", "CROMPTON", "SRF", "DABUR", "GODREJCP",
    "PETRONET", "PGEL", "SHREECEM", "TIINDIA", "RSYSTEMS", "ALKEM"
}

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

                    if series_col and series_col in df.columns:
                        df = df[df[series_col].astype(str).str.strip() == 'EQ']
                    
                    df[sym_col] = df[sym_col].astype(str).str.strip()
                    df = df[df[sym_col].isin(STRICT_FNO_WHITELIST)]

                    df['TRADED_VALUE'] = df[vol_col].astype(float) * df[close_col].astype(float)
                    if prev_close_col and prev_close_col in df.columns:
                        df['DAY_CHANGE_PCT'] = ((df[close_col].astype(float) - df[prev_close_col].astype(float)) / df[prev_close_col].astype(float)) * 100
                    else:
                        df['DAY_CHANGE_PCT'] = 0.0

                    processed_data = []
                    for _, row in df.iterrows():
                        symbol = row[sym_col]
                        close_p = round(float(row[close_col]), 2)
                        turnover_cr = round(float(row['TRADED_VALUE']) / 10000000, 2)
                        change_pct = round(float(row['DAY_CHANGE_PCT']), 2)
                        
                        # --- ADVANCED BUYING SIGNALS ---
                        buy_signal = "—"
                        if (turnover_cr >= 400 and change_pct >= 2.0) or (turnover_cr >= 150 and change_pct >= 6.0):
                            buy_signal = "🟢 ROCKET BLAST (BUY)"
                        elif (turnover_cr >= 300 and change_pct >= 1.5) or (turnover_cr >= 100 and change_pct >= 4.0):
                            buy_signal = "🎯 SNIPER BULL (BUY)"
                        elif change_pct > 0:
                            buy_signal = "📈 MILD BULLISH"

                        # --- ADVANCED SELLING / DIP SIGNALS ---
                        sell_signal = "—"
                        if (turnover_cr >= 400 and change_pct <= -2.0) or (turnover_cr >= 150 and change_pct <= -4.0):
                            sell_signal = "🔴 SHARP DUMP (EXIT)"
                        elif (turnover_cr >= 300 and change_pct <= -1.5) or (turnover_cr >= 100 and change_pct <= -2.5):
                            sell_signal = "⚠️ BEAR HIT (SELL)"
                        elif change_pct < 0:
                            sell_signal = "📉 DEEP DIP / BEARISH"
                            
                        processed_data.append({
                            'symbol': symbol,
                            'turnover': turnover_cr,
                            'close': close_p,
                            'change_pct': change_pct,
                            'change_str': f"{change_pct:+.2f}%",
                            'buy': buy_signal,
                            'sell': sell_signal
                        })
                    return processed_data
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# 3. Execution Trigger
date = datetime.now()
raw_data = None

for i in range(5): 
    test_date = date - timedelta(days=i)
    if test_date.weekday() >= 5: 
        continue
    raw_data = fetch_bhavcopy_for_date(test_date)
    if raw_data:
        break

# 4. Sheet Output (Side-by-Side Buying & Selling Layout)
if raw_data:
    worksheet.clear()  
    
    bullish_list = [x for x in raw_data if x['change_pct'] >= 0]
    bearish_list = [x for x in raw_data if x['change_pct'] < 0]
    
    bullish_list.sort(key=lambda x: x['change_pct'], reverse=True)
    bearish_list.sort(key=lambda x: x['change_pct'], reverse=False)
    
    ist_now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%d-%b %H:%M')
    
    # Left Side: Buying (Cols A to E), Center: Time (Col F), Right Side: Selling/Dips (Cols G to K)
    headers_bull = ["🟢 BUYING SYMBOL", "TURNOVER (CR)", "CLOSE", "CHANGE %", "BUY SIGNAL"]
    center_header = [f"🕒 UPDATED: {ist_now} (IST)"]
    headers_bear = ["🔴 SELLING / DIP SYMBOL", "TURNOVER (CR)", "CLOSE", "CHANGE %", "SELL SIGNAL"]
    
    full_headers = headers_bull + center_header + headers_bear
    worksheet.update('A1', [full_headers])
    
    max_rows = max(len(bullish_list), len(bearish_list))
    combined_rows = []
    
    for idx in range(max_rows):
        row = []
        # Bullish / Buying Side (Cols A to E)
        if idx < len(bullish_list):
            b = bullish_list[idx]
            row.extend([b['symbol'], b['turnover'], b['close'], b['change_str'], b['buy']])
        else:
            row.extend(["", "", "", "", ""])
            
        # Center Timestamp Column (Col F) - Empty for rows
        row.append("")
        
        # Bearish / Selling Side (Cols G to K)
        if idx < len(bearish_list):
            r = bearish_list[idx]
            row.extend([r['symbol'], r['turnover'], r['close'], r['change_str'], r['sell']])
        else:
            row.extend(["", "", "", "", ""])
            
        combined_rows.append(row)
        
    worksheet.update('A2', combined_rows)
    print("SUCCESS: Buying & Selling Dual-Side Dashboard Updated!")
else:
    print("❌ Failed to fetch data.")
