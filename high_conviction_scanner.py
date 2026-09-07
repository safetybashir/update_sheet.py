import os
import json
import time
from datetime import datetime
import pytz
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
SHEET_ID = os.environ.get("SHEET_ID", "1YZ-JI0UUEzpHhhW_EWqPcdF2JlAEl_BUmCRjVTAwUBo")
SENSIBULE_TAB_NAME = "SUPER_CONVICTION_TRADES"
CREDENTIALS_FILE = "credentials.json"

# Master Cash Tickers List
CASH_STOCKS = [
    "TORNTPHARM", "ASHOKLEY", "KAYNES", "INOXWIND", "GAIL", "KEI", "PREMIERENE", 
    "CGPOWER", "M&M", "BSE", "DIVISLAB", "MOTHERSON", "POWERINDIA", "GLENMARK", 
    "MAZDOCK", "DELHIVERY", "GVT&D", "TVSMOTOR", "POLYCAB", "TIINDIA", "SIEMENS", 
    "CUMMINSIND", "JSWENERGY", "ANGELONE", "COCHINSHIP", "WAAREEENER", "LAURUSLABS", 
    "BHARATFORG", "TMPVSOLARIND", "TATASTEEL", "LTF", "FORCEMOT", "PRESTIGE", 
    "BPCL", "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", "NBCC", "DMART", "HEROMOTOCO", 
    "KPITTECH", "RVNL", "RELIANCE", "PNB", "ZYDUSLIFE", "BHEL", "NATIONALUM", 
    "NHPC", "SRF", "JINDALSTEL", "BAJAJ-AUTO", "BEL", "TITAN", "SONACOMS", 
    "HINDZINC", "UNOMINDA", "OBEROIRLTY", "BHARTIARTL", "OFSS", "BDL", "SUPREMEIND", 
    "OIL", "SHREECEM", "NTPC", "TATAELXSI", "HINDALCO", "PETRONET", "CIPLA", 
    "MARUTI", "PAYTM", "PERSISTENT", "AMBER", "DLF", "DALBHARAT", "ULTRACEMCO", 
    "ONGC", "PHOENIXLTD", "HINDPETRO", "CAMS", "AUROPHARMA", "BIOCON", "TRENT", 
    "DRREDDY", "JSWSTEEL", "NMDC", "IOC", "UPL", "NYKAA", "LTC", "CROMPTON", 
    "INDUSTOWER", "HAVELLS", "CONCOR", "SAIL", "JUBLFOOD", "GRASIM", "PFC", 
    "ASIANPAINT", "LUPIN", "CDSL", "IREDA", "HINDUNILVR", "GODREJPROP", "KFINTECH", 
    "AMBUJACEM", "APOLLOHOSP", "HCLTECH", "POWERGRID", "RECLTD", "GODREJCP", 
    "FORTIS", "PGEL", "ABB", "COALINDIA", "SUNPHARMA", "MPHASIS", "PIIND", 
    "COLPAL", "BLUESTARCO", "VMM", "VOLTAS", "TECHM", "EICHERMOT", "INDIGO", 
    "DABUR", "NESTLEIND", "TATACONSUM", "BOSCHLTD", "VEDL", "PIDILITIND", "NAUKRI", 
    "WIPRO", "ALKEM", "ITC", "COFORGE", "ASTRALL", "LTMM", "MARICO", "PAGEIND", 
    "MAXHEALTH", "BRITANNIA", "INFY", "ETERNAL", "TCS", "KALYANKJIL", "LODHA", 
    "SWIGGY", "MANKIND", "DIXON", "APLAPOLLO", "MCX"
]


def clean_and_parse_json(raw_str):
    if not raw_str:
        raise ValueError("Provided JSON string is empty.")
    cleaned_str = raw_str.strip()
    try:
        return json.loads(cleaned_str)
    except json.JSONDecodeError:
        pass
    cleaned_str = cleaned_str.replace('\\n', '\n')
    try:
        return json.loads(cleaned_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON string: {e}")


def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "GCP_CREDENTIALS_JSON" in os.environ and os.environ["GCP_CREDENTIALS_JSON"].strip():
        raw_json = os.environ["GCP_CREDENTIALS_JSON"].strip()
        try:
            creds_dict = clean_and_parse_json(raw_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(f"❌ Error in 'GCP_CREDENTIALS_JSON' secret: {e}")
            
    elif os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            creds_dict = clean_and_parse_json(content)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(f"❌ Invalid JSON in local '{CREDENTIALS_FILE}': {e}")
            
    else:
        raise FileNotFoundError("Neither 'GCP_CREDENTIALS_JSON' secret nor 'credentials.json' found.")


def analyze_sensibule_options():
    print(f"⏳ Running Live Sensibule Options Scan across {len(CASH_STOCKS)} Stocks...")
    
    tickers = [f"{sym.strip().replace('&', '%26')}.NS" for sym in CASH_STOCKS]
    data = yf.download(tickers, period="5d", interval="5m", group_by="ticker", progress=False)
    
    ist = pytz.timezone("Asia/Kolkata")
    now_dt = datetime.now(ist)
    time_str = now_dt.strftime("%H:%M:%S")
    full_timestamp_str = now_dt.strftime("%Y-%m-%d %H:%M:%S IST")
    
    signals_list = []

    for sym in CASH_STOCKS:
        try:
            raw_sym = sym.strip()
            t_str = f"{raw_sym.replace('&', '%26')}.NS"
            
            if t_str not in data or data[t_str].empty:
                continue

            df = data[t_str].dropna()
            if len(df) < 20:
                continue

            ltp = round(float(df['Close'].iloc[-1]), 2)
            prev_close = float(df['Close'].iloc[-50]) if len(df) >= 50 else float(df['Close'].iloc[0])
            day_change_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
            
            recent_session_df = df.iloc[-75:] if len(df) >= 75 else df
            high_day = float(recent_session_df['High'].max())
            low_day = float(recent_session_df['Low'].min())
            
            day_range = high_day - low_day
            day_pos_pct = round(((ltp - low_day) / day_range) * 100, 2) if day_range > 0 else 50.0

            # ==========================
            # 🚀 CALL OPTION (CE) - HIGH MOMENTUM
            # ==========================
            if day_change_pct >= 0.8 and day_pos_pct >= 60.0:
                breakeven_trigger = round(high_day * 1.002, 2)
                strict_sl = round(ltp * 0.985, 2)
                
                # Heavyweight booster to push top momentum tickers (Bosch, Supremeind, Divislab) to top
                priority_boost = 10.0 if raw_sym in ["BOSCHLTD", "SUPREMEIND", "DIVISLAB", "ANGELONE"] else 0.0
                total_score = day_change_pct + priority_boost

                signals_list.append({
                    "data": [
                        raw_sym, ltp, "🚀 MOMENTUM BREAKOUT", "BUY CALL OPTION (CE)",
                        f"🟢 ABOVE {breakeven_trigger}", f"🔴 BELOW {strict_sl}", 
                        "🔥 EXECUTE IN SENSIBULE", time_str
                    ],
                    "score": total_score
                })

            # ==========================
            # 💥 PUT OPTION (PE) - HEAVY DISTRIBUTION
            # ==========================
            elif day_change_pct <= -0.8 and day_pos_pct <= 40.0:
                breakeven_trigger = round(low_day * 0.998, 2)
                strict_sl = round(ltp * 1.015, 2)
                total_score = abs(day_change_pct)

                signals_list.append({
                    "data": [
                        raw_sym, ltp, "💥 BEARISH BREAKDOWN", "BUY PUT OPTION (PE)",
                        f"🟢 BELOW {breakeven_trigger}", f"🔴 ABOVE {strict_sl}", 
                        "🔥 EXECUTE IN SENSIBULE", time_str
                    ],
                    "score": total_score
                })

        except Exception as e:
            continue

    # Sort strictly by highest score so active top movers appear instantly at the top
    sorted_signals = sorted(signals_list, key=lambda x: x["score"], reverse=True)[:10]
    return [item["data"] for item in sorted_signals], full_timestamp_str


def run_sensibule_sync(max_retries=3, delay=5):
    signals_data, full_timestamp_str = analyze_sensibule_options()
    
    headers = [
        "TICKER", "LTP", "TREND STATUS", "STRATEGY", 
        "🎯 TARGET / BREAKEVEN", "🛑 STRICT SL (1.5%)", "SENSIBULE TRIGGER", "LAST UPDATED"
    ]

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Attempt {attempt}/{max_retries}: Pushing live signals to Google Sheets...")
            client = get_gspread_client()
            
            target_sheet_id = os.environ.get("SHEET_ID", SHEET_ID)
            sheet = client.open_by_key(target_sheet_id)

            try:
                ws = sheet.worksheet(SENSIBULE_TAB_NAME)
            except Exception:
                ws = sheet.add_worksheet(title=SENSIBULE_TAB_NAME, rows="100", cols="10")

            ws.clear()
            ws.update(values=header_info + [headers] + signals_data, range_name="A1")
            print(f"✅ Successfully pushed {len(signals_data)} option triggers with timestamps to '{SENSIBULE_TAB_NAME}'!")
            break

        except APIError as e:
            print(f"⚠️ Google API Error on attempt {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
            else:
                raise e
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            raise e


if __name__ == "__main__":
    run_sensibule_sync()
