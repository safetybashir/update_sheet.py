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

# --- STRICT CLEAN F&O & HIGH-MOVER WHITELIST (UPDATED WITH YOUR EXACT LIST) ---
STRICT_FNO_WHITELIST = {
    "BOSCHLTD", "SHREECEM", "POWERINDIA", "SOLARINDS", "POLYCAB", "OFSS", "ABB", "KEI", 
    "NIFTY", "HEROMOTOCO", "ULTRACEMCO", "BSE", "PERSISTENT", "KAYNES", "APOLLOHOSP", 
    "DIVISLAB", "COFORGE", "LAURUSLABS", "MANKIND", "ALKEM", "DRREDDY", "MPHASIS", 
    "JSWSTEEL", "GLENMARK", "INDIGO", "GRASIM", "HAL", "INFY", "PAYTM", "BHARTIARTL", 
    "ETERNAL", "TCS", "TMPV", "M&M", "DIXON", "MARUTI", "PFC", "BHEL", "TRENT", 
    "SWIGGY", "SONACOMS", "DLF", "HINDALCO", "ZYDUSLIFE", "BEL", "MOTHERSON", 
    "COALINDIA", "FORTIS", "HINDZINC", "HCLTECH", "MAXHEALTH", "TORNTPHARM", "TITAN", 
    "SAIL", "LTF", "HINDPETRO", "TVSMOTOR", "POWERGRID", "CUMMINSIND", "CDSL", "CIPLA", 
    "ASHOKLEY", "KALYANKJIL", "WIPRO", "AAREEENER", "IREDA", "EICHERMOT", "TECHM", 
    "NAUKRI", "HINDUNILVR", "DELHIVERY", "GVT&D", "BAJAJ-AUTO", "SUNPHARMA", "LTMR", 
    "RECLTD", "ONGC", "OBEROIRLTY", "NYKAA", "UPL", "DMART", "FORCEMOT", "INDUSTOWER", 
    "BHARATFORG", "AUROPHARMA", "PIIND", "BDL", "IOC", "ASIANPAINT", "BIOCON", 
    "GMRAIRPORT", "JSWENERGY", "LODHA", "GAIL", "MAZDOCK", "PHOENIXLTD", "LUPIN", 
    "BLUESTARCO", "RELIANCE", "NMDC", "TATACONSUM", "CGPOWER", "ANGELONE", "INOXWIND", 
    "PIDILITIND", "APLAPOLLO", "AMBER", "NATIONALUM", "COLPAL", "KPITTECH", "TATAPOWER", 
    "PAGEIND", "BPCL", "COCHINSHIP", "TATAELXSI", "CAMS", "BRITANNIA", "NESTLEIND", 
    "ASTRAL", "RVNL", "JINDALSTEL", "GODREJPROP", "PRESTIGE", "JUBLFOOD", "AMBUJACEM", 
    "DALBHARAT", "VOLTAS", "PREMIERENE", "SUPREMEIND", "KFINTECH", "MARICO", "HAVELLS", 
    "UNOMINDA", "CONCOR", "NBCC", "SIEMENS", "CROMPTON", "SRF", "DABUR", "GODREJCP", 
    "PETRONET", "PGEL", "TIINDIA", "RSYSTEMS"
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
                        df = df[df[series_col].astype(str).str.strip().isin(['EQ', 'BE'])]
                    
                    df[sym_col] = df[sym_col].astype(str).str.strip()
                    df = df[df[sym_col].isin(STRICT_FNO_WHITELIST)]

                    df['TRADED_VALUE'] = df[vol_col].astype(float) * df[close_col].astype(float)
                    if prev_close_col and prev_close_col in df.columns:
                        df['DAY_CHANGE_PTS'] = df[close_col].astype(float) - df[prev_close_col].astype(float)
                        df['DAY_CHANGE_PCT'] = (df['DAY_CHANGE_PTS'] / df[prev_close_col].astype(float)) * 100
                    else:
                        df['DAY_CHANGE_PTS'] = 0.0
                        df['DAY_CHANGE_PCT'] = 0.0

                    processed_data = []
                    for _, row in df.iterrows():
                        symbol = row[sym_col]
                        close_p = round(float(row[close_col]), 2)
                        turnover_cr = round(float(row['TRADED_VALUE']) / 10000000, 2)
                        change_pct = round(float(row['DAY_CHANGE_PCT']), 2)
                        change_pts = round(float(row['DAY_CHANGE_PTS']), 2)
                        
                        # --- RECALIBRATED LOGIC FOR HIGH MOVERS & ABSOLUTE POINTS ---
                        buy_signal = "—"
                        buy_heat = "⚪ [LOW]"
                        
                        # Rule 1: High Absolute Move (+100 Points or 3%+) OR High Turnover Surge
                        if change_pts >= 100 or (turnover_cr >= 250 and change_pct >= 2.5):
                            buy_signal = f"🚀 NUCLEAR MOVER (+{change_pts} Pts)"
                            buy_heat = "🟢🟢🟢 [SUPER HOT]"
                        elif change_pts >= 50 or (turnover_cr >= 150 and change_pct >= 1.8):
                            buy_signal = f"🟢 ROCKET BLAST (+{change_pts} Pts)"
                            buy_heat = "🟢🟢 [HIGH HEAT]"
                        elif change_pts >= 25 or (turnover_cr >= 80 and change_pct >= 1.0):
                            buy_signal = "🎯 SNIPER BULL (BUY)"
                            buy_heat = "🌱 [WARM]"
                        elif change_pct > 0:
                            buy_signal = "📈 MILD BULLISH"
                            buy_heat = "⚡ [MODERATE]"

                        # --- RECALIBRATED SELLING LOGIC ---
                        sell_signal = "—"
                        sell_heat = "⚪ [LOW]"
                        
                        if change_pts <= -100 or (turnover_cr >= 250 and change_pct <= -2.5):
                            sell_signal = f"🔴 HEAVY INSTI DUMP ({change_pts} Pts)"
                            sell_heat = "🔴🔴🔴 [EXTREME DUMP]"
                        elif change_pts <= -50 or (turnover_cr >= 150 and change_pct <= -1.8):
                            sell_signal = f"⚠️ SHARP DUMP ({change_pts} Pts)"
                            sell_heat = "🔴🔴 [HIGH DUMP]"
                        elif change_pts <= -25 or (turnover_cr >= 80 and change_pct <= -1.0):
                            sell_signal = "📉 BEAR HIT (SELL)"
                            sell_heat = "🚨 [HEAVY BEAR]"
                        elif change_pct < 0:
                            sell_signal = "📉 DEEP DIP / BEARISH"
                            sell_heat = "⚡ [MODERATE DIP]"
                            
                        processed_data.append({
                            'symbol': symbol,
                            'turnover': turnover_cr,
                            'close': close_p,
                            'change_pct': change_pct,
                            'change_pts': change_pts,
                            'change_str': f"{change_pct:+.2f}% ({change_pts:+.1f} Pts)",
                            'buy': buy_signal,
                            'buy_heat': buy_heat,
                            'sell': sell_signal,
                            'sell_heat': sell_heat
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

# 4. Sheet Output
if raw_data:
    worksheet.clear()  
    
    bullish_list = [x for x in raw_data if x['change_pct'] >= 0]
    bearish_list = [x for x in raw_data if x['change_pct'] < 0]
    
    # Priority sorting by Absolute Points & Percentage Change
    bullish_list.sort(key=lambda x: (x['change_pts'], x['change_pct']), reverse=True)
    bearish_list.sort(key=lambda x: (x['change_pts'], x['change_pct']), reverse=False)
    
    ist_now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%d-%b %H:%M')
    
    headers_bull = ["🟢 BUYING SYMBOL", "LTP", "TURNOVER (CR)", "CHANGE % (PTS)", "BUY SIGNAL", "HEAT METER"]
    center_header = [f"🕒 UPDATED: {ist_now} (IST)"]
    headers_bear = ["🔴 SELLING / DIP SYMBOL", "LTP", "TURNOVER (CR)", "CHANGE % (PTS)", "SELL SIGNAL", "HEAT METER"]
    
    full_headers = headers_bull + center_header + headers_bear
    worksheet.update('A1', [full_headers])
    
    max_rows = max(len(bullish_list), len(bearish_list))
    combined_rows = []
    
    for idx in range(max_rows):
        row = []
        if idx < len(bullish_list):
            b = bullish_list[idx]
            row.extend([b['symbol'], b['close'], b['turnover'], b['change_str'], b['buy'], b['buy_heat']])
        else:
            row.extend(["", "", "", "", "", ""])
            
        row.append("")
        
        if idx < len(bearish_list):
            r = bearish_list[idx]
            row.extend([r['symbol'], r['close'], r['turnover'], r['change_str'], r['sell'], r['sell_heat']])
        else:
            row.extend(["", "", "", "", "", ""])
            
        combined_rows.append(row)
        
    worksheet.update('A2', combined_rows)
    print("SUCCESS: Recalibrated Mover Logic Executed Successfully!")
else:
    print("❌ Failed to fetch data.")
