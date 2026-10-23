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

                    # --- 1. SERIES FILTER ---
                    if series_col and series_col in df.columns:
                        df = df[df[series_col].astype(str).str.strip() == 'EQ']
                    
                    # --- 2. WHITELIST FILTER ---
                    df[sym_col] = df[sym_col].astype(str).str.strip()
                    df = df[df[sym_col].isin(STRICT_FNO_WHITELIST)]

                    # --- 3. CALCULATIONS ---
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
                        
                        high_p = float(row[high_col]) if high_col and high_col in df.columns else close_p
                        prev_c = float(row[prev_close_col]) if prev_close_col and prev_close_col in df.columns else close_p
                        
                        buy_signal = "—"
                        if (turnover_cr >= 400 and change_pct >= 2.0) or (turnover_cr >= 150 and change_pct >= 6.0):
                            buy_signal = "🟢 ROCKET BLAST (BUY)"
                        elif (turnover_cr >= 300 and change_pct >= 1.5) or (turnover_cr >= 100 and change_pct >= 4.0):
                            buy_signal = "🎯 SNIPER BULL HIT (BUY)"
                        elif turnover_cr >= 800 and (-0.5 <= change_pct <= 0.5):
                            buy_signal = "⚡ COILED SPRING"
                        elif change_pct > 0:
                            buy_signal = "📈 MILD BULLISH"

                        sell_signal = "—"
                        if (turnover_cr >= 400 and change_pct <= -2.0) or (turnover_cr >= 150 and change_pct <= -4.0):
                            sell_signal = "🔴 SHARP DUMP (EXIT)"
                        elif (turnover_cr >= 300 and change_pct <= -1.5) or (turnover_cr >= 100 and change_pct <= -2.5):
                            sell_signal = "⚠️ BEAR HIT (SELL)"

                        upper_wick_pct = ((high_p - max(close_p, prev_c)) / prev_c) * 100 if prev_c > 0 else 0
                        if turnover_cr >= 200 and upper_wick_pct >= 1.2 and change_pct < 0.8:
                            organic_status = "🚨 TRAP / REJECTION"
                        elif turnover_cr >= 300 and change_pct <= -1.0:
                            organic_status = "⚠️ BEAR TRAP"
                        else:
                            organic_status = "🌱 ORGANIC"
                            
                        processed_data.append({
                            'symbol': symbol,
                            'turnover': turnover_cr,
                            'close': close_p,
                            'change_pct': change_pct,
                            'change_str': f"{change_pct:+.2f}%",
                            'buy': buy_signal,
                            'sell': sell_signal,
                            'organic': organic_status
                        })
                        
                    return processed_data
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# 3. Execution Trigger
date = datetime.now()
raw_data = None
fetched_date_str = ""

for i in range(5): 
    test_date = date - timedelta(days=i)
    if test_date.weekday() >= 5: 
        continue
        
    raw_data = fetch_bhavcopy_for_date(test_date)
    if raw_data:
        fetched_date_str = test_date.strftime('%d-%b-%Y')
        break

# 4. Sheet Output (Split into Bullish & Bearish Halves side-by-side)
if raw_data:
    worksheet.clear()  
    
    # Split data into Bullish (>=0) and Bearish (<0)
    bullish_list = [x for x in raw_data if x['change_pct'] >= 0]
    bearish_list = [x for x in raw_data if x['change_pct'] < 0]
    
    # Sort Bullish: Highest gainers on top
    bullish_list.sort(key=lambda x: x['change_pct'], reverse=True)
    
    # Sort Bearish: Deepest negative / dips on top (MAXHEALTH style)
    bearish_list.sort(key=lambda x: x['change_pct'], reverse=False)
    
    ist_now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%d-%b %H:%M')
    
    # Headers for Left (Cols A-G) and Right (Cols I-O), Center Status in Col H
    headers_bull = ["🟢 BULLISH SYMBOL", "TURNOVER", "CLOSE", "CHANGE %", "BUY RADAR", "SELL RADAR", "ORGANIC"]
    center_status = [f"Data: {fetched_date_str} | Updated: {ist_now} (IST)"]
    headers_bear = ["🔴 BEARISH / DIP", "TURNOVER", "CLOSE", "CHANGE %", "BUY RADAR", "SELL RADAR", "ORGANIC"]
    
    full_headers = headers_bull + center_status + headers_bear
    worksheet.update('A1', [full_headers])
    
    # Combine side-by-side rows
    max_rows = max(len(bullish_list), len(bearish_list))
    combined_rows = []
    
    for idx in range(max_rows):
        row = []
        # Bullish Side (Cols A to G)
        if idx < len(bullish_list):
            b = bullish_list[idx]
            row.extend([b['symbol'], b['turnover'], b['close'], b['change_str'], b['buy'], b['sell'], b['organic']])
        else:
            row.extend(["", "", "", "", "", "", ""])
            
        # Center Separator / Blank (Col H)
        row.append("")
        
        # Bearish Side (Cols I to O)
        if idx < len(bearish_list):
            r = bearish_list[idx]
            row.extend([r['symbol'], r['turnover'], r['close'], r['change_str'], r['buy'], r['sell'], r['organic']])
        else:
            row.extend(["", "", "", "", "", "", ""])
            
        combined_rows.append(row)
        
    worksheet.update('A2', combined_rows)
    print("SUCCESS: Dual-Side Bullish/Bearish Dashboard & Center Time Updated!")
else:
    print("❌ Failed to fetch data.")
