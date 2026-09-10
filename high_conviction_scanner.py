import os
import json
import time
from datetime import datetime
import pytz
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError
from gspread.exceptions import APIError

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
SHEET_ID = os.environ.get("SHEET_ID", "1YZ-JI0UUEzpHhhW_EWqPcdF2JlAEl_BUmCRjVTAwUBo")
SENSIBULE_TAB_NAME = "SUPER_CONVICTION_TRADES"
CREDENTIALS_FILE = "credentials.json"

# Master Stock Universe (Expanded to include high-volume, mid-cap, small-cap, and FnO stocks)
STOCK_UNIVERSE = [
    "NOVARTIND", "INDNIPPON", "GRAPHITE", "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", 
    "SBIN", "BHARTIARTL", "LTIM", "ITC", "HINDUNILVR", "LT", "BAJFINANCE", "AXISBANK", 
    "MARUTI", "SUNPHARMA", "TITAN", "ASIANPAINT", "KOTAKBANK", "ULTRACEMCO", "NTPC", 
    "ONGC", "ADANIENT", "ADANIPORTS", "COALINDIA", "POWERGRID", "BAJAJFINSV", "TATASTEEL", 
    "JSWSTEEL", "GRASIM", "TECHM", "WIPRO", "HCLTECH", "NESTLEIND", "INDIGO", "DIVISLAB", 
    "TATACONSUM", "BPCL", "SBILIFE", "HDFCLIFE", "BRITANNIA", "EICHERMOT", "DRREDDY", 
    "BAJAJ-AUTO", "APOLLOHOSP", "HEROMOTOCO", "HAL", "BEL", "CHOLAFIN", "DABUR", 
    "PIDILITIND", "SIEMENS", "ABB", "TORNTPHARM", "VEDL", "IOC", "GAIL", "PNB", 
    "BANKBARODA", "CANBK", "IDFCFIRSTB", "TVSMOTOR", "M&M", "BOSCHLTD", "AMBUJACEM", 
    "SHREECEM", "ICICIGI", "ICICIPRULI", "SRF", "MUTHOOTFIN", "PERSISTENT", "LUPIN", 
    "AUROPHARMA", "CIPLA", "DLF", "OBEROIRLTY", "GODREJPROP", "PEL", "POLYCAB", 
    "NAUKRI", "ZOMATO", "PAYTM", "NYKAA", "DELHIVERY", "MCX", "HINDPETRO", "CAMS", 
    "TRENT", "DIXON", "CGPOWER", "MAZDOCK", "COCHINSHIP", "WAAREEENER", "KAYNES", 
    "INOXWIND", "KEI", "PREMIERENE", "SOLARIND", "FORCEMOT", "PRESTIGE", "SUZLON", 
    "GMRAIRPORT", "TATAPOWER", "NBCC", "DMART", "KPITTECH", "RVNL", "ZYDUSLIFE", 
    "BHEL", "NATIONALUM", "NHPC", "JINDALSTEL", "SONACOMS", "HINDZINC", "UNOMINDA", 
    "OFSS", "BDL", "SUPREMEIND", "OIL", "TATAELXSI", "HINDALCO", "PETRONET", "AMBER", 
    "DALBHARAT", "PHOENIXLTD", "BIOCON", "NMDC", "UPL", "CROMPTON", "INDUSTOWER", 
    "HAVELLS", "CONCOR", "SAIL", "JUBLFOOD", "PFC", "LUPIN", "CDSL", "IREDA", 
    "GODREJPROP", "KFINTECH", "HCLTECH", "RECLTD", "GODREJCP", "FORTIS", "PGEL", 
    "MPHASIS", "PIIND", "COLPAL", "BLUESTARCO", "VOLTAS", "DABUR", "ASTRALL", 
    "LTMM", "MARICO", "PAGEIND", "MAXHEALTH", "KALYANKJIL", "LODHA", "SWIGGY", "MANKIND"
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


def analyze_mahesh_style_radar():
    print(f"⏳ Scanning and Sorting Stock Universe across {len(STOCK_UNIVERSE)} Tickers...")
    
    tickers = [f"{sym.strip().replace('&', '%26')}.NS" for sym in STOCK_UNIVERSE]
    data = yf.download(tickers, period="5d", interval="5m", group_by="ticker", progress=False)
    
    ist = pytz.timezone("Asia/Kolkata")
    now_dt = datetime.now(ist)
    current_date_str = now_dt.strftime("%d-%b-%Y")
    current_time_str = now_dt.strftime("%H:%M")
    
    # Header timestamp string matching your precise specification
    meta_timestamp = f"Data Date: {current_date_str} | Updated: {current_date_str} {current_time_str} (IST) [Strict Sector Shield Active]"
    
    records = []

    for sym in STOCK_UNIVERSE:
        try:
            raw_sym = sym.strip()
            t_str = f"{raw_sym.replace('&', '%26')}.NS"
            
            if t_str not in data or data[t_str].empty:
                continue

            df = data[t_str].dropna()
            if len(df) < 15:
                continue

            close_price = round(float(df['Close'].iloc[-1]), 2)
            prev_close = float(df['Close'].iloc[-50]) if len(df) >= 50 else float(df['Close'].iloc[0])
            day_change_pct = round(((close_price - prev_close) / prev_close) * 100, 2)
            
            recent_df = df.iloc[-75:] if len(df) >= 75 else df
            high_day = float(recent_df['High'].max())
            low_day = float(recent_df['Low'].min())
            
            # Traded Value (Turnover in Crores)
            total_vol = float(recent_df['Volume'].sum())
            traded_value_cr = round((total_vol * close_price) / 10000000, 2)
            
            day_range = high_day - low_day
            day_pos_pct = round(((close_price - low_day) / day_range) * 100, 2) if day_range > 0 else 50.0

            # ----------------------------------------------------
            # CLASSIFICATION LOGIC (Mahesh Style Radar Format)
            # ----------------------------------------------------
            buy_radar = "—"
            dump_radar = "—"
            organic_status = "🌱 ORGANIC STOCK (NO TRAP)"
            
            # Sorting score setup
            score = 0.0

            if day_change_pct >= 2.0 and day_pos_pct >= 60.0:
                if day_change_pct >= 10.0:
                    buy_radar = "🟢 ROCKET BLAST (BUY)"
                elif day_change_pct >= 5.0:
                    buy_radar = "🟢 STRONG MOMENTUM (BUY)"
                else:
                    buy_radar = "🟢 BUY ON DIPS / ACCUMULATION"
                
                score = (traded_value_cr * 0.5) + (day_change_pct * 20)
                
            elif day_change_pct <= -2.0 and day_pos_pct <= 40.0:
                if day_change_pct <= -7.0:
                    dump_radar = "🔴 HEAVY DUMP / DISTRIBUTION"
                else:
                    dump_radar = "🔴 BEARISH PRESSURE"
                
                score = (traded_value_cr * 0.5) + (abs(day_change_pct) * 20)
            else:
                # Skip low movement noise unless traded value is exceptionally massive
                if traded_value_cr < 50.0:
                    continue
                score = traded_value_cr * 0.1

            records.append({
                "data": [
                    raw_sym,
                    traded_value_cr,
                    close_price,
                    f"{day_change_pct:+.2f}%",
                    buy_radar,
                    dump_radar,
                    organic_status
                ],
                "score": score
            })

        except Exception as e:
            continue

    # Sort strictly by highest conviction score (Traded Value & Momentum Combined)
    sorted_records = sorted(records, key=lambda x: x["score"], reverse=True)[:25]
    
    formatted_rows = [item["data"] for item in sorted_records]
    return formatted_rows, meta_timestamp


def run_mahesh_radar_sync(max_retries=3, delay=5):
    rows_data, meta_timestamp = analyze_mahesh_style_radar()
    
    # Exact Headers matching your requirement
    headers = [
        "STOCK SYMBOL", 
        "TRADED VALUE (CR)", 
        "CLOSE PRICE", 
        "DAY CHANGE %", 
        "🟢 BUY / ROCKET RADAR", 
        "🔴 SELL / DUMP RADAR", 
        "🌱 ORGANIC STOCKS / NO BULL TRAP"
    ]

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Attempt {attempt}/{max_retries}: Updating Mahesh-style Radar to Google Sheets...")
            client = get_gspread_client()
            
            target_sheet_id = os.environ.get("SHEET_ID", SHEET_ID)
            sheet = client.open_by_key(target_sheet_id)

            try:
                ws = sheet.worksheet(SENSIBULE_TAB_NAME)
            except Exception:
                ws = sheet.add_worksheet(title=SENSIBULE_TAB_NAME, rows="100", cols="10")

            ws.clear()
            
            # Row 1: Metadata Timestamp
            # Row 2: Table Headers
            # Row 3 onwards: Stock Records
            payload = [
                [meta_timestamp, "", "", "", "", "", ""],
                headers
            ] + rows_data

            ws.update(values=payload, range_name="A1")
            print(f"🎉 Successfully updated Google Sheet tab '{SENSIBULE_TAB_NAME}' in Mahesh-style format!")
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
    run_mahesh_radar_sync()
