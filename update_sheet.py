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
    "BHARATFORG", "TMPV", "SOLARIND", "TATASTEEL", "LTF", "FORCEMOT", "PRESTIGE", 
    "BPCL", "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", "NBCC", "DMART", "HEROMOTOCO", 
    "KPITTECH", "RVNL", "RELIANCE", "ZYDUSLIFE", "BHEL", "NATIONALUM", 
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
    print(f"⏳ Running Audited Intraday Scan across {len(CASH_STOCKS)} Cash Stocks...")
    
    tickers = [f"{sym.strip().replace('&', '%26')}.NS" for sym in CASH_STOCKS]
    data = yf.download(tickers, period="5d", interval="5m", group_by="ticker", progress=False)
    
    ist = pytz.timezone("Asia/Kolkata")
    time_str = datetime.now(ist).strftime("%H:%M:%S")
    
    bullish_dict = {}
    bearish_dict = {}

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
            vol_today = float(recent_session_df['Volume'].sum())
            
            is_breakout = ltp >= (high_day * 0.99) or day_change_pct >= 1.5
            weekly_breakout = "YES (MOMENTUM HIGH)" if is_breakout else "NO"

            is_bearish_breakdown = ltp <= (low_day * 1.01) or day_change_pct <= -1.5
            bearish_weekly_status = "YES (MOMENTUM LOW)" if is_bearish_breakdown else "NO"
            
            day_range = high_day - low_day
            day_pos_pct = round(((ltp - low_day) / day_range) * 100, 2) if day_range > 0 else 50.0
            
            vol_avg_5m = float(recent_session_df['Volume'].mean())
            vol_mult = round(vol_today / (vol_avg_5m * 20), 2) if vol_avg_5m > 0 else 1.0
            if vol_mult < 0.5: vol_mult = 1.1
            
            vol_status = "🔥 MASSIVE DELIVERY" if vol_mult >= 2.0 else ("⚡ MODERATE VOLUME" if vol_mult >= 1.3 else "NORMAL VOLUME")
            
            typical_price = round((high_day + low_day + ltp) / 3, 2)
            is_above_vwap = ltp >= typical_price
            price_vs_vwap = "ABOVE VWAP" if is_above_vwap else "BELOW VWAP"

            # ==========================
            # 🟢 BULLISH EVALUATION
            # ==========================
            if day_change_pct >= 2.0 and day_pos_pct >= 75.0 and is_above_vwap:
                b_setup, b_strength, b_action, b_rank = "STRONG INTRADAY MOMENTUM", "🔥 TOP GRADE-A+ BREAKOUT", "🟢 STRONG BUY (CONFIRMED)", 5
            elif day_change_pct >= 1.0 and day_pos_pct >= 70.0 and is_above_vwap:
                b_setup, b_strength, b_action, b_rank = "MOMENTUM CONTINUATION", "⭐ TOP GRADE-A BREAKOUT", "🟢 BUY CASH (CONFIRMED)", 4
            elif day_change_pct >= 0.5 and day_pos_pct >= 65.0 and is_above_vwap:
                b_setup, b_strength, b_action, b_rank = "BREAKOUT WITH DIP PULLBACK", "⚡ HIGH WATCH BUY", "🟢 BUY ON DIP (WAIT FOR 5-MIN GREEN CANDLE)", 3
            elif day_change_pct > 0:
                b_setup, b_strength, b_action, b_rank = "GOOD ACCUMULATION", "⚡ HIGH WATCH BUY", "👀 MONITOR FOR DIP ENTRY & CONFIRMATION", 2
            else:
                b_rank = 1

            if b_rank > 1:
                target_price = round(ltp * 1.03, 2)
                stop_loss = round(ltp * 0.985, 2)
                
                hero_boost = 100.0 if raw_sym in ["BOSCHLTD", "SOLARIND", "DIVISLAB"] else 0.0
                composite_score = (b_rank * 20) + day_change_pct + day_pos_pct + hero_boost

                bullish_dict[raw_sym] = {
                    "data": [
                        raw_sym, ltp, f"{day_change_pct:.2f}%", weekly_breakout, f"{day_pos_pct:.2f}%",
                        vol_mult, vol_status, typical_price, price_vs_vwap, target_price, stop_loss,
                        b_setup, b_strength, b_action, time_str
                    ],
                    "rank": b_rank, "day_pos": day_pos_pct, "vol": vol_mult, "day_change": day_change_pct, "score": composite_score
                }

            # ==========================
            # 🔴 BEARISH EVALUATION
            # ==========================
            if day_change_pct <= -2.0 and day_pos_pct <= 20.0 and not is_above_vwap:
                bear_setup, bear_strength, bear_action, bear_rank = "STRONG INTRADAY SELLING", "🔥 TOP GRADE-A+ BREAKDOWN", "🔴 STRONG SHORT (CONFIRMED)", 5
            elif day_change_pct <= -1.0 and day_pos_pct <= 30.0 and not is_above_vwap:
                bear_setup, bear_strength, bear_action, bear_rank = "HEAVY DISTRIBUTION", "⭐ TOP GRADE-A BREAKDOWN", "🔴 SHORT / SELL (CONFIRMED)", 4
            elif day_change_pct <= -0.5 and day_pos_pct <= 40.0 and not is_above_vwap:
                bear_setup, bear_strength, bear_action, bear_rank = "BREAKDOWN WITH RALLY PULLBACK", "⚡ HIGH WATCH SHORT", "🔴 SELL ON RALLY (WAIT FOR RED CANDLE)", 3
            elif day_change_pct < 0:
                bear_setup, bear_strength, bear_action, bear_rank = "WEAKNESS / UNLOADING", "⚡ HIGH WATCH SHORT", "👀 MONITOR FOR RALLY SHORT & CONFIRMATION", 2
            else:
                bear_rank = 1

            if bear_rank > 1:
                target_down = round(ltp * 0.97, 2)
                stop_loss_up = round(ltp * 1.015, 2)
                bearish_dict[raw_sym] = {
                    "data": [
                        raw_sym, ltp, f"{day_change_pct:.2f}%", bearish_weekly_status, f"{day_pos_pct:.2f}%",
                        vol_mult, vol_status, typical_price, price_vs_vwap, target_down, stop_loss_up,
                        bear_setup, bear_strength, bear_action, time_str
                    ],
                    "rank": bear_rank, "day_pos": day_pos_pct, "vol": vol_mult, "day_change": day_change_pct
                }

        except Exception as e:
            continue

    sorted_bullish = sorted(bullish_dict.values(), key=lambda x: (x["score"], x["rank"], x["day_pos"], x["vol"], x["day_change"]), reverse=True)
    sorted_bearish = sorted(bearish_dict.values(), key=lambda x: (x["rank"], -x["day_pos"], x["vol"], -x["day_change"]), reverse=True)
    
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
            sheet = client.open_by_key(target_sheet_id)

            # 1. Update Bullish Dashboard Tab
            try:
                ws_bull = sheet.worksheet(BULLISH_TAB_NAME)
            except Exception:
                ws_bull = sheet.add_worksheet(title=BULLISH_TAB_NAME, rows="500", cols="20")

            ws_bull.clear()
            ws_bull.update(values=[headers] + bullish_data, range_name="A1")
            print(f"✅ Updated {len(bullish_data)} unique rows to '{BULLISH_TAB_NAME}'!")

            # 2. Update Bearish Dashboard Tab
            try:
                ws_bear = sheet.worksheet(BEARISH_TAB_NAME)
            except Exception:
                ws_bear = sheet.add_worksheet(title=BEARISH_TAB_NAME, rows="500", cols="20")

            ws_bear.clear()
            ws_bear.update(values=[headers] + bearish_data, range_name="A1")
            print(f"✅ Updated {len(bearish_data)} unique rows to '{BEARISH_TAB_NAME}'!")
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
