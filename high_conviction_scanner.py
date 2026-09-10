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

# 🎯 YOUR EXACT SELECTED STOCK UNIVERSE (Including MOLBIO)
STOCK_UNIVERSE = [
    "ABB", "ABBOTINDIA", "ACC", "ATGL", "AJANTPHARM", "ALKEM", "AMBUJACEM", 
    "APOLLOHOSP", "APOLLOTYRE", "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUROPHARMA", 
    "AVENUESUPER", "DMART", "BALKRISIND", "BALRAMCHIN", "BATAINDIA", "BEL", "BHARATFORG", 
    "BHEL", "BIOCON", "BLS", "BLUESTARCO", "BOSCHLTD", "BRITANNIA", "BSE", "CAMS", 
    "CGPOWER", "CHAMBLFERT", "CIPLA", "COALINDIA", "COCHINSHIP", "COFORGE", "COLPAL", 
    "CONCOR", "COROMANDEL", "CROMPTON", "CUMMINSIND", "DABUR", "DalmiaBharat", 
    "DEEPAKFERT", "DELHIVERY", "DEVYANI", "DIVISLAB", "DIXON", "LALPATHLAB", "DRREDDY", 
    "EICHERMOT", "ELGIEQUIP", "EMAMILTD", "ENDURANCE", "ESCORTS", "EXIDEIND", "NYKAA", 
    "FACT", "FORCEMOT", "FORTIS", "GAIL", "GMRAIRPORT", "GICRE", "GILLETTE", "GLAXO", 
    "GLENMARK", "GMDC", "GODREJCP", "GODREJPROP", "GRANULES", "GRASIM", "GUJGASLTD", 
    "GNFC", "GPPL", "GSPL", "HAL", "HAVELLS", "HCLTECH", "HFCL", "HINDALCO", 
    "HINDCOPPER", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HUDCO", "IGL", "INDHOTEL", 
    "INDIACEM", "INDIANB", "INDIGO", "INDNIPPON", "INDUSTOWER", "INFY", "INOXWIND", 
    "IOC", "IPCALAB", "IRB", "IRCTC", "IRFC", "ITC", "JINDALSTEL", "JINDALSAW", "JSL", 
    "JSWENERGY", "JSWSTEEL", "JUBLFOOD", "JUBLINGREA", "KPITTECH", "KALYANKJIL", 
    "KAYNES", "KEC", "KEI", "KFINTECH", "KNRCON", "KPIL", "LTIM", "LTTS", "LUPIN", 
    "M&M", "MAHSECI", "MAGL", "MANKIND", "MARICO", "MARUTI", "MAXHEALTH", "MAZDOCK", 
    "MEDANTA", "METROPOLIS", "MFSL", "MOTHERSON", "MPHASIS", "MRF", "MSUMI", "NATIONALUM", 
    "NAVINFLUOR", "NAUKRI", "NBCC", "NCC", "NESTLEIND", "NHPC", "NLCINDIA", "NMDC", 
    "NTPC", "OBEROIRLTY", "ONGC", "OIL", "OISL", "PAYTM", "OFSS", "PAGEIND", "PATANJALI", 
    "PEL", "PERSISTENT", "PETRONET", "PFC", "PHOENIXLTD", "PIDILITIND", "PIIND", 
    "POLYCAB", "POONAWALLA", "PRAJIND", "PRESTIGE", "PGEL", "railtel", "RVNL", "RECLTD", 
    "RELIANCE", "SCHAEFFLER", "RENUKA", "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SOBHA", 
    "SOLARIND", "SONACOMS", "SRF", "STARHEALTH", "SAIL", "SUNPHARMA", "SUPREMEIND", 
    "SUZLON", "SYNGENE", "TVSMOTOR", "TATACHEM", "TATACOMM", "TCS", "TATACONSUM", 
    "TATAELXSI", "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TECHM", "TIINDIA", "TITAN", 
    "TORNTPOWER", "TORNTPHARM", "TRENT", "TRIDENT", "TRIVENI", "ULTRACEMCO", "UNOMINDA", 
    "UPL", "VEDL", "VIJAYA", "VOLTAS", "WAAREEENER", "WHIRLPOOL", "WIPRO", "ZFCVINDIA", 
    "ZYDUSLIFE", "ZOMATO", "MOLBIO"
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


def analyze_split_buy_sell_radar():
    print(f"⏳ Scanning your exact custom stock list ({len(STOCK_UNIVERSE)} Tickers including MOLBIO)...")
    
    tickers = [f"{sym.strip().replace('&', '%26')}.NS" for sym in STOCK_UNIVERSE]
    data = yf.download(tickers, period="5d", interval="5m", group_by="ticker", progress=False)
    
    ist = pytz.timezone("Asia/Kolkata")
    now_dt = datetime.now(ist)
    current_date_str = now_dt.strftime("%d-%b-%Y")
    current_time_str = now_dt.strftime("%H:%M")
    
    buy_records = []
    sell_records = []

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
            # SEGREGATION LOGIC (BUY vs SELL)
            # ----------------------------------------------------
            if day_change_pct >= 1.2 and day_pos_pct >= 55.0:
                action_signal = "🟢 BUY / ACCUMULATION" if day_change_pct < 5.0 else "🟢 ROCKET BLAST (BUY)"
                
                buy_records.append({
                    "data": [raw_sym, traded_value_cr, close_price, f"{day_change_pct:+.2f}%", action_signal, current_time_str],
                    "traded_value": traded_value_cr
                })
                
            elif day_change_pct <= -1.2 and day_pos_pct <= 45.0:
                action_signal = "🔴 SELL / BEARISH DUMP" if day_change_pct > -5.0 else "🔴 HEAVY CRASH (SELL)"
                
                sell_records.append({
                    "data": [raw_sym, traded_value_cr, close_price, f"{day_change_pct:+.2f}%", action_signal, current_time_str],
                    "traded_value": traded_value_cr
                })

        except Exception as e:
            continue

    # 🔥 Sort both lists strictly by Highest Traded Value (Descending Order)
    sorted_buys = sorted(buy_records, key=lambda x: x["traded_value"], reverse=True)[:25]
    sorted_sells = sorted(sell_records, key=lambda x: x["traded_value"], reverse=True)[:25]
    
    return [item["data"] for item in sorted_buys], [item["data"] for item in sorted_sells]


def run_split_radar_sync(max_retries=3, delay=5):
    buy_rows, sell_rows = analyze_split_buy_sell_radar()
    
    buy_headers = ["TOP BUY SYMBOL", "TRADED VAL (CR)", "CLOSE", "CHANGE %", "ACTION", "TIME"]
    sell_headers = ["TOP SELL SYMBOL", "TRADED VAL (CR)", "CLOSE", "CHANGE %", "ACTION", "TIME"]

    max_rows = max(len(buy_rows), len(sell_rows))
    
    combined_payload = [
        buy_headers + [""] + sell_headers
    ]

    for i in range(max_rows):
        b_row = buy_rows[i] if i < len(buy_rows) else ["", "", "", "", "", ""]
        s_row = sell_rows[i] if i < len(sell_rows) else ["", "", "", "", "", ""]
        combined_payload.append(b_row + [""] + s_row)

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Attempt {attempt}/{max_retries}: Pushing custom stock list radar to Google Sheets...")
            client = get_gspread_client()
            
            target_sheet_id = os.environ.get("SHEET_ID", SHEET_ID)
            sheet = client.open_by_key(target_sheet_id)

            try:
                ws = sheet.worksheet(SENSIBULE_TAB_NAME)
            except Exception:
                ws = sheet.add_worksheet(title=SENSIBULE_TAB_NAME, rows="100", cols="15")

            ws.clear()
            ws.update(values=combined_payload, range_name="A1")
            print(f"🎉 Successfully updated Google Sheet tab '{SENSIBULE_TAB_NAME}' with your custom universe (Molbio included)!")
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
    run_split_radar_sync()
