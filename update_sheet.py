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
# Exact Native Google Sheet ID hardcoded as default
SHEET_ID = os.environ.get("SHEET_ID", "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg")
BULLISH_TAB_NAME = "BULLISH_CASH_BREAKOUTS"
CREDENTIALS_FILE = "credentials.json"

# Scanned Cash Tickers List
CASH_STOCKS = [
    "ANGELONE", "RVNL", "HAL", "BSE", "TATASTEEL", 
    "KAYNES", "ULTRACEMCO", "DIXON", "POLYCAB", "TRENT"
]


def clean_and_parse_json(raw_str):
    """
    Cleans raw string inputs and safely parses JSON content.
    Handles escaped quotes and double-escaped newlines.
    """
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
        raise ValueError(
            f"Failed to parse JSON string. Ensure keys are enclosed in double quotes.\nDetails: {e}"
        )


def get_gspread_client():
    """
    Authenticate and return gspread client handling:
    1. GitHub Actions ENV Variable ('GCP_CREDENTIALS_JSON')
    2. Local file fallback ('credentials.json')
    """
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Direct ENV handling for GitHub Actions
    if "GCP_CREDENTIALS_JSON" in os.environ and os.environ["GCP_CREDENTIALS_JSON"].strip():
        raw_json = os.environ["GCP_CREDENTIALS_JSON"].strip()
        try:
            creds_dict = clean_and_parse_json(raw_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(
                f"❌ Error in GitHub Secret 'GCP_CREDENTIALS_JSON'. "
                f"Please verify secret content in GitHub Repository Settings.\n{e}"
            )
            
    # 2. Local File Fallback
    elif os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            creds_dict = clean_and_parse_json(content)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(
                f"❌ Invalid JSON format inside local '{CREDENTIALS_FILE}'.\n{e}"
            )
            
    else:
        raise FileNotFoundError(
            "Neither 'GCP_CREDENTIALS_JSON' secret env nor 'credentials.json' file was found."
        )


def analyze_cash_breakouts():
    """
    Scans stocks and ranks them based on Institutional Breakout Criteria:
    - Rank 5 (Ultra Grade-A+): Day Range Pos >= 85%, Vol >= 2.0x, Above VWAP
    - Rank 4 (Top Grade-A):   Day Range Pos >= 80%, Vol >= 1.8x, Above VWAP
    - Rank 3 (Confirmed):     Day Range Pos >= 70%, Above VWAP
    - Rank 2 (Accumulation):  Vol >= 1.2x
    - Rank 1 (Consolidation): Weak setups
    """
    print("⏳ Running Dual-Threshold (85% & 80%) Institutional Breakout Scan...")
    tickers = [f"{sym}.NS" for sym in CASH_STOCKS]
    data = yf.download(tickers, period="60d", interval="1d", group_by="ticker", progress=False)
    
    ist = pytz.timezone("Asia/Kolkata")
    time_str = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
    results = []

    for sym in CASH_STOCKS:
        try:
            t_str = f"{sym}.NS"
            df = data[t_str].dropna() if len(CASH_STOCKS) > 1 else data.dropna()
            if len(df) < 10:
                continue

            ltp = round(float(df['Close'].iloc[-1]), 2)
            prev_close = float(df['Close'].iloc[-2])
            day_change_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
            
            high_day = float(df['High'].iloc[-1])
            low_day = float(df['Low'].iloc[-1])
            vol_today = float(df['Volume'].iloc[-1])
            
            # 5-Day High Breakout Verification
            five_day_high = float(df['High'].iloc[-6:-1].max())
            is_breakout = ltp >= five_day_high
            weekly_breakout = "YES (5-DAY HIGH)" if is_breakout else "NO"
            
            # Day Range Position % Calculation
            day_range = high_day - low_day
            day_pos_pct = round(((ltp - low_day) / day_range) * 100, 2) if day_range > 0 else 50.0
            
            # Volume Multiplier vs 10-day Average
            vol_avg_10 = float(df['Volume'].iloc[-11:-1].mean())
            vol_mult = round(vol_today / vol_avg_10, 2) if vol_avg_10 > 0 else 1.0
            
            vol_status = "🔥 MASSIVE DELIVERY" if vol_mult >= 2.0 else ("⚡ MODERATE VOLUME" if vol_mult >= 1.3 else "NORMAL VOLUME")
            vwap = round((high_day + low_day + ltp) / 3, 2)
            is_above_vwap = ltp >= vwap
            price_vs_vwap = "ABOVE VWAP" if is_above_vwap else "BELOW VWAP"
            
            target_price = round(ltp * 1.03, 2)
            stop_loss = round(ltp * 0.985, 2)

            # 🎯 5-TIER MULTI-THRESHOLD RANKING LOGIC
            if is_breakout and day_pos_pct >= 85.0 and vol_mult >= 2.0 and is_above_vwap:
                setup = "ULTRA INSTITUTIONAL BUYING"
                strength = "🔥 TOP GRADE-A+ BREAKOUT"
                action = "🟢 STRONG BUY CASH / DELIVERY"
                setup_rank = 5

            elif is_breakout and day_pos_pct >= 80.0 and vol_mult >= 1.8 and is_above_vwap:
                setup = "STRONG INSTITUTIONAL BUYING"
                strength = "⭐ TOP GRADE-A BREAKOUT"
                action = "🟢 STRONG BUY CASH"
                setup_rank = 4

            elif is_breakout and day_pos_pct >= 70.0 and is_above_vwap:
                setup = "BREAKOUT CONFIRMED"
                strength = "⚡ HIGH WATCH BUY"
                action = "🟢 BUY ON DIP"
                setup_rank = 3

            elif (day_change_pct >= 1.0 or is_breakout) and vol_mult >= 1.2:
                setup = "GOOD ACCUMULATION"
                strength = "⚡ HIGH WATCH BUY"
                action = "👀 MONITOR FOR CASH ENTRY"
                setup_rank = 2

            else:
                setup = "CONSOLIDATION"
                strength = "NEUTRAL"
                action = "HOLD / WAIT"
                setup_rank = 1

            results.append({
                "data": [
                    sym, ltp, f"{day_change_pct:.2f}%", weekly_breakout, f"{day_pos_pct:.2f}%",
                    vol_mult, vol_status, vwap, price_vs_vwap, target_price, stop_loss,
                    setup, strength, action, time_str
                ],
                "rank": setup_rank,
                "day_pos": day_pos_pct,
                "vol": vol_mult,
                "day_change": day_change_pct
            })
        except Exception as e:
            print(f"⚠️ Error processing {sym}: {e}")
            continue

    # Multi-Level Priority Sorting
    sorted_results = sorted(
        results, 
        key=lambda x: (x["rank"], x["day_pos"], x["vol"], x["day_change"]), 
        reverse=True
    )
    
    return [item["data"] for item in sorted_results]


def run_live_cash_sync(max_retries=3, delay=5):
    """
    Executes live scan and updates Google Sheets with exponential backoff for API robustness.
    """
    scanned_data = analyze_cash_breakouts()
    headers = [
        "STOCK TICKER", "CASH LTP", "DAY CHANGE %", "WEEKLY HIGH BREAKOUT",
        "DAY RANGE POS %", "VOLUME MULTIPLIER", "VOLUME SPIKE STATUS", "VWAP",
        "PRICE vs VWAP", "TARGET PRICE (+3%)", "STOP LOSS (-1.5%)", 
        "CASH BREAKOUT SETUP", "SIGNAL STRENGTH", "ACTION TRIGGER", "LAST UPDATED"
    ]

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Attempt {attempt}/{max_retries}: Connecting to Google Sheets...")
            client = get_gspread_client()
            
            target_sheet_id = os.environ.get("SHEET_ID", SHEET_ID)
            print(f"📌 Using Sheet ID: {target_sheet_id}")

            sheet = client.open_by_key(target_sheet_id)

            try:
                worksheet = sheet.worksheet(BULLISH_TAB_NAME)
            except Exception:
                worksheet = sheet.add_worksheet(title=BULLISH_TAB_NAME, rows="100", cols="20")

            worksheet.clear()
            worksheet.update(values=[headers] + scanned_data, range_name="A1")
            print(f"✅ Successfully Updated {len(scanned_data)} Institutional Signals!")
            break

        except APIError as e:
            print(f"⚠️ Google API Error on attempt {attempt}: {e}")
            if attempt < max_retries:
                print(f"⏳ Waiting {delay} seconds before retrying...")
                time.sleep(delay)
                delay *= 2
            else:
                print("❌ Max retries reached. Google Sheets API remains unavailable.")
                raise e
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            raise e


if __name__ == "__main__":
    run_live_cash_sync()
