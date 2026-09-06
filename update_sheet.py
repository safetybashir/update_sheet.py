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
SHEET_ID = os.environ.get("SHEET_ID", "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg")
BULLISH_TAB_NAME = "LIVE_BULLISH_CASH_DASHBOARD"
BEARISH_TAB_NAME = "LIVE_BEARISH_CASH_DASHBOARD"
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
    "SWIGGY", "MANKIND", "DIXON", "APLAPOLLO"
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


def analyze_market_data():
    print(f"⏳ Running Institutional Dual Scan (Bullish & Bearish) across {len(CASH_STOCKS)} Cash Stocks...")
    
    tickers = [f"{sym.strip().replace('&', '%26')}.NS" for sym in CASH_STOCKS]
    data = yf.download(tickers, period="60d", interval="1d", group_by="ticker", progress=False)
    
    ist = pytz.timezone("Asia/Kolkata")
    time_str = datetime.now(ist).strftime("%H:%M:%S")  # Sirf Exact Time (HH:MM:SS)
    
    bullish_results = []
    bearish_results = []

    for sym in CASH_STOCKS:
        try:
            raw_sym = sym.strip()
            t_str = f"{raw_sym.replace('&', '%26')}.NS"
            
            if t_str not in data or data[t_str].empty:
                continue

            df = data[t_str].dropna()
            if len(df) < 15:
                continue

            ltp = round(float(df['Close'].iloc[-1]), 2)
            prev_close = float(df['Close'].iloc[-2])
            day_change_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
            
            high_day = float(df['High'].iloc[-1])
            low_day = float(df['Low'].iloc[-1])
            vol_today = float(df['Volume'].iloc[-1])
            
            # 5-Day High / Low Baselines
            five_day_high = float(df['High'].iloc[-6:-1].max())
            five_day_low = float(df['Low'].iloc[-6:-1].min())
            
            is_breakout = ltp >= five_day_high
            weekly_breakout = "YES (5-DAY HIGH)" if is_breakout else "NO"

            is_bearish_breakdown = ltp <= five_day_low
            bearish_weekly_status = "YES (5-DAY LOW)" if is_bearish_breakdown else "NO"
            
            # Day Range Position % Calculation
            day_range = high_day - low_day
            day_pos_pct = round(((ltp - low_day) / day_range) * 100, 2) if day_range > 0 else 50.0
            
            # Volume Baseline 10-Day Average
            vol_avg_10 = float(df['Volume'].iloc[-11:-1].mean())
            vol_mult = round(vol_today / vol_avg_10, 2) if vol_avg_10 > 0 else 1.0
            
            vol_status = "🔥 MASSIVE DELIVERY" if vol_mult >= 2.0 else ("⚡ MODERATE VOLUME" if vol_mult >= 1.3 else "NORMAL VOLUME")
            
            # VWAP Proxy
            typical_price = round((high_day + low_day + ltp) / 3, 2)
            is_above_vwap = ltp >= typical_price
            price_vs_vwap = "ABOVE VWAP" if is_above_vwap else "BELOW VWAP"

            # ==========================
            # 🟢 BULLISH EVALUATION
            # ==========================
            if is_breakout and day_pos_pct >= 85.0 and vol_mult >= 2.0 and is_above_vwap:
                b_setup = "ULTRA INSTITUTIONAL BUYING"
                b_strength = "🔥 TOP GRADE-A+ BREAKOUT"
                b_action = "🟢 STRONG BUY CASH / DELIVERY"
                b_rank = 5
            elif is_breakout and day_pos_pct >= 80.0 and vol_mult >= 1.5 and is_above_vwap:
                b_setup = "STRONG INSTITUTIONAL BUYING"
                b_strength = "⭐ TOP GRADE-A BREAKOUT"
                b_action = "🟢 BUY CASH"
                b_rank = 4
            elif is_breakout and day_pos_pct >= 70.0 and is_above_vwap:
                b_setup = "BREAKOUT CONFIRMED"
                b_strength = "⚡ HIGH WATCH BUY"
                b_action = "🟢 BUY ON DIP"
                b_rank = 3
            elif (day_change_pct >= 1.0 or is_breakout) and vol_mult >= 1.2:
                b_setup = "GOOD ACCUMULATION"
                b_strength = "⚡ HIGH WATCH BUY"
                b_action = "👀 MONITOR FOR CASH ENTRY"
                b_rank = 2
            else:
                b_setup = "CONSOLIDATION"
                b_strength = "NEUTRAL"
                b_action = "HOLD / WAIT"
                b_rank = 1

            if b_rank > 1:  # Only add qualified or active bullish setups
                target_price = round(ltp * 1.03, 2)
                stop_loss = round(ltp * 0.985, 2)
                bullish_results.append({
                    "data": [
                        raw_sym, ltp, f"{day_change_pct:.2f}%", weekly_breakout, f"{day_pos_pct:.2f}%",
                        vol_mult, vol_status, typical_price, price_vs_vwap, target_price, stop_loss,
                        b_setup, b_strength, b_action, time_str
                    ],
                    "rank": b_rank, "day_pos": day_pos_pct, "vol": vol_mult, "day_change": day_change_pct
                })

            # ==========================
            # 🔴 BEARISH EVALUATION
            # ==========================
            if is_bearish_breakdown and day_pos_pct <= 15.0 and vol_mult >= 2.0 and not is_above_vwap:
                bear_setup = "ULTRA INSTITUTIONAL SELLING"
                bear_strength = "🔥 TOP GRADE-A+ BREAKDOWN"
                bear_action = "🔴 STRONG SHORT / EXIT CASH"
                bear_rank = 5
            elif is_bearish_breakdown and day_pos_pct <= 20.0 and vol_mult >= 1.5 and not is_above_vwap:
                bear_setup = "HEAVY DISTRIBUTION"
                bear_strength = "⭐ TOP GRADE-A BREAKDOWN"
                bear_action = "🔴 SHORT / SELL"
                bear_rank = 4
            elif is_bearish_breakdown and day_pos_pct <= 30.0 and not is_above_vwap:
                bear_setup = "BREAKDOWN CONFIRMED"
                bear_strength = "⚡ HIGH WATCH SHORT"
                bear_action = "🔴 SELL ON RALLY"
                bear_rank = 3
            elif (day_change_pct <= -1.0 or is_bearish_breakdown) and vol_mult >= 1.2:
                bear_setup = "WEAKNESS / UNLOADING"
                bear_strength = "⚡ HIGH WATCH SHORT"
                bear_action = "👀 MONITOR FOR SHORT ENTRY"
                bear_rank = 2
            else:
                bear_setup = "CONSOLIDATION"
                bear_strength = "NEUTRAL"
                bear_action = "HOLD / WAIT"
                bear_rank = 1

            if bear_rank > 1:  # Only add qualified bearish setups
                target_down = round(ltp * 0.97, 2)
                stop_loss_up = round(ltp * 1.015, 2)
                bearish_results.append({
                    "data": [
                        raw_sym, ltp, f"{day_change_pct:.2f}%", bearish_weekly_status, f"{day_pos_pct:.2f}%",
                        vol_mult, vol_status, typical_price, price_vs_vwap, target_down, stop_loss_up,
                        bear_setup, bear_strength, bear_action, time_str
                    ],
                    "rank": bear_rank, "day_pos": day_pos_pct, "vol": vol_mult, "day_change": day_change_pct
                })

        except Exception as e:
            continue

    # Sorting
    sorted_bullish = sorted(bullish_results, key=lambda x: (x["rank"], x["day_pos"], x["vol"], x["day_change"]), reverse=True)
    sorted_bearish = sorted(bearish_results, key=lambda x: (x["rank"], -x["day_pos"], x["vol"], -x["day_change"]), reverse=True)
    
    return [item["data"] for item in sorted_bullish], [item["data"] for item in sorted_bearish]


def run_live_dashboards_sync(max_retries=3, delay=5):
    bullish_data, bearish_data = analyze_market_data()
    
    headers = [
        "STOCK TICKER", "CASH LTP", "DAY CHANGE %", "WEEKLY HIGH BREAKOUT",
        "DAY RANGE POS %", "VOLUME MULTIPLIER", "VOLUME SPIKE STATUS", "VWAP",
        "PRICE vs VWAP", "TARGET PRICE", "STOP LOSS", 
        "CASH BREAKOUT SETUP", "SIGNAL STRENGTH", "ACTION TRIGGER", "LAST UPDATED"
    ]

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Attempt {attempt}/{max_retries}: Connecting to Google Sheets...")
            client = get_gspread_client()
            
            target_sheet_id = os.environ.get("SHEET_ID", SHEET_ID)
            print(f"📌 Targeting Sheet ID: {target_sheet_id}")

            sheet = client.open_by_key(target_sheet_id)

            # 1. Update Bullish Dashboard Tab
            try:
                ws_bull = sheet.worksheet(BULLISH_TAB_NAME)
            except Exception:
                ws_bull = sheet.add_worksheet(title=BULLISH_TAB_NAME, rows="500", cols="20")

            ws_bull.clear()
            ws_bull.update(values=[headers] + bullish_data, range_name="A1")
            print(f"✅ Updated {len(bullish_data)} rows to '{BULLISH_TAB_NAME}'!")

            # 2. Update Bearish Dashboard Tab
            try:
                ws_bear = sheet.worksheet(BEARISH_TAB_NAME)
            except Exception:
                ws_bear = sheet.add_worksheet(title=BEARISH_TAB_NAME, rows="500", cols="20")

            ws_bear.clear()
            ws_bear.update(values=[headers] + bearish_data, range_name="A1")
            print(f"✅ Updated {len(bearish_data)} rows to '{BEARISH_TAB_NAME}'!")
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
    run_live_dashboards_sync()
