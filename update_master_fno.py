import os
import json
import time
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Credentials Setup
creds_json = os.environ.get('GCP_CREDENTIALS_JSON')
if not creds_json:
    # Fallback for local testing if file exists
    if os.path.exists('credentials.json'):
        with open('credentials.json') as f:
            creds_dict = json.load(f)
    else:
        raise ValueError("❌ GCP_CREDENTIALS_JSON environment variable not found!")
else:
    creds_dict = json.loads(creds_json)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Google Sheet ID & Worksheet Name
spreadsheet_id = "15LBUVcxELAmdffUxsboBjrXfuJyM9xC-KZVh6GwBzxg" 
worksheet = client.open_by_key(spreadsheet_id).worksheet("LIVE_MASTER_DASHBOARD")

# --- WHITELIST WITH .NS EXTENSION FOR YFINANCE ---
RAW_WHITELIST = [
    "BOSCHLTD", "SHREECEM", "POWERINDIA", "SOLARINDS", "POLYCAB", "OFSS", "ABB", "KEI", 
    "HEROMOTOCO", "ULTRACEMCO", "BSE", "PERSISTENT", "KAYNES", "APOLLOHOSP", 
    "DIVISLAB", "COFORGE", "LAURUSLABS", "MANKIND", "ALKEM", "DRREDDY", "MPHASIS", 
    "JSWSTEEL", "GLENMARK", "INDIGO", "GRASIM", "HAL", "INFY", "PAYTM", "BHARTIARTL", 
    "ETERNAL", "TCS", "M&M", "DIXON", "MARUTI", "PFC", "BHEL", "TRENT", 
    "SWIGGY", "SONACOMS", "DLF", "HINDALCO", "ZYDUSLIFE", "BEL", "MOTHERSON", 
    "COALINDIA", "FORTIS", "HINDZINC", "HCLTECH", "MAXHEALTH", "TORNTPHARM", "TITAN", 
    "SAIL", "LTF", "HINDPETRO", "TVSMOTOR", "POWERGRID", "CUMMINSIND", "CDSL", "CIPLA", 
    "ASHOKLEY", "KALYANKJIL", "WIPRO", "IREDA", "EICHERMOT", "TECHM", 
    "NAUKRI", "HINDUNILVR", "DELHIVERY", "BAJAJ-AUTO", "SUNPHARMA", 
    "RECLTD", "ONGC", "OBEROIRLTY", "NYKAA", "UPL", "DMART", "FORCEMOT", "INDUSTOWER", 
    "BHARATFORG", "AUROPHARMA", "PIIND", "BDL", "IOC", "ASIANPAINT", "BIOCON", 
    "GMRAIRPORT", "JSWENERGY", "LODHA", "GAIL", "MAZDOCK", "PHOENIXLTD", "LUPIN", 
    "BLUESTARCO", "RELIANCE", "NMDC", "TATACONSUM", "CGPOWER", "ANGELONE", "INOXWIND", 
    "PIDILITIND", "APLAPOLLO", "AMBER", "NATIONALUM", "COLPAL", "KPITTECH", "TATAPOWER", 
    "PAGEIND", "BPCL", "COCHINSHIP", "TATAELXSI", "CAMS", "BRITANNIA", "NESTLEIND", 
    "ASTRAL", "RVNL", "JINDALSTEL", "GODREJPROP", "PRESTIGE", "JUBLFOOD", "AMBUJACEM", 
    "DALBHARAT", "VOLTAS", "SUPREMEIND", "KFINTECH", "MARICO", "HAVELLS", 
    "UNOMINDA", "CONCOR", "NBCC", "SIEMENS", "CROMPTON", "SRF", "DABUR", "GODREJCP", 
    "PETRONET", "PGEL", "TIINDIA", "RSYSTEMS"
]

def fetch_live_intraday_data():
    tickers = [f"{sym}.NS" for sym in RAW_WHITELIST]
    print("🔄 Fetching live market snapshot via Free Data Source...")
    
    try:
        # Download today's data snapshot
        data = yf.download(tickers, period='1d', interval='1m', progress=False)
        if data.empty:
            return None
        
        processed_data = []
        for sym in RAW_WHITELIST:
            ticker_str = f"{sym}.NS"
            try:
                # Extract close and volume for the specific ticker
                if len(tickers) == 1:
                    df_ticker = data
                else:
                    df_ticker = data.xs(ticker_str, level=1, axis=1) if ticker_str in data.columns.levels[1] else None
                
                if df_ticker is None or df_ticker.empty:
                    continue
                
                closes = df_ticker['Close'].dropna()
                volumes = df_ticker['Volume'].dropna()
                
                if len(closes) < 2:
                    continue
                
                current_price = float(closes.iloc[-1])
                prev_close = float(closes.iloc[0]) # Opening/Prev reference for intraday
                total_vol = float(volumes.sum())
                
                change_pts = round(current_price - prev_close, 2)
                change_pct = round((change_pts / prev_close) * 100, 2) if prev_close > 0 else 0.0
                turnover_cr = round((total_vol * current_price) / 10000000, 2)
                
                # --- HEAT METER LOGIC ---
                buy_signal = "—"
                buy_heat = "⚪ [LOW]"
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
                    'symbol': sym,
                    'turnover': turnover_cr,
                    'close': round(current_price, 2),
                    'change_pct': change_pct,
                    'change_pts': change_pts,
                    'change_str': f"{change_pct:+.2f}% ({change_pts:+.1f} Pts)",
                    'buy': buy_signal,
                    'buy_heat': buy_heat,
                    'sell': sell_signal,
                    'sell_heat': sell_heat
                })
            except Exception as e:
                continue
        return processed_data
    except Exception as e:
        print(f"Error fetching live data: {e}")
        return None

# 4. Continuous Loop for Market Hours (Runs every 5 mins)
if __name__ == "__main__":
    print("🚀 Free Live Intraday Screener Initialized...")
    while True:
        now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
        
        # Check if market is open (Monday to Friday, 9:15 AM to 3:30 PM IST)
        if now_ist.weekday() < 5 and (9 <= now_ist.hour < 16):
            raw_data = fetch_live_intraday_data()
            
            if raw_data:
                worksheet.clear()
                bullish_list = [x for x in raw_data if x['change_pct'] >= 0]
                bearish_list = [x for x in raw_data if x['change_pct'] < 0]
                
                bullish_list.sort(key=lambda x: (x['change_pts'], x['change_pct']), reverse=True)
                bearish_list.sort(key=lambda x: (x['change_pts'], x['change_pct']), reverse=False)
                
                ist_now_str = now_ist.strftime('%d-%b %H:%M')
                headers_bull = ["🟢 BUYING SYMBOL", "LTP", "TURNOVER (CR)", "CHANGE % (PTS)", "BUY SIGNAL", "HEAT METER"]
                center_header = [f"🕒 LIVE: {ist_now_str} (IST)"]
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
                print(f"✅ Google Sheet Updated Live at {ist_now_str}")
            
            # Wait for 5 minutes before next refresh
            time.sleep(300)
        else:
            print("⏳ Market Closed. Waiting for next market session...")
            time.sleep(600)
