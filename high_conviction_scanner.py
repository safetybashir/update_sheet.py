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

# Master FnO (Futures & Options) Stocks List
FNO_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL", 
    "LTIM", "ITC", "HINDUNILVR", "LT", "BAJFINANCE", "AXISBANK", "MARUTI", 
    "SUNPHARMA", "TITAN", "ASIANPAINT", "KOTAKBANK", "ULTRACEMCO", "TITAGARH", 
    "NTPC", "ONGC", "TITAN", "ADANIENT", "ADANIPORTS", "COALINDIA", "POWERGRID", 
    "BAJAJFINSV", "TATASTEEL", "JSWSTEEL", "GRASIM", "TECHM", "WIPRO", "HCLTECH", 
    "NESTLEIND", "INDIGO", "DIVISLAB", "TATACONSUM", "BPCL", "SBILIFE", "HDFCLIFE", 
    "BRITANNIA", "EICHERMOT", "DRREDDY", "BAJAJ-AUTO", "APOLLOHOSP", "HEROMOTOCO", 
    "HAL", "BEL", "CHOLAFIN", "DABUR", "PIDILITIND", "SIEMENS", "ABB", "TORNTPHARM", 
    "VEDL", "IOC", "GAIL", "PNB", "BANKBARODA", "CANBK", "IDFCFIRSTB", "TVSMOTOR", 
    "M&M", "BOSCHLTD", "AMBUJACEM", "SHREECEM", "ICICIGI", "ICICIPRULI", "SRF", 
    "MUTHOOTFIN", "PERSISTENT", "LUPIN", "AUROPHARMA", "CIPLA", "DLF", "OBEROIRLTY", 
    "GODREJPROP", "PEL", "POLYCAB", "NAUKRI", "ZOMATO", "PAYTM", "NYKAA", "DELHIVERY"
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


def analyze_fno_options():
    print(f"⏳ Running Live FnO Traded Value & Options Scan across {len(FNO_STOCKS)} Derivative Stocks...")
    
    tickers = [f"{sym.strip().replace('&', '%26')}.NS" for sym in FNO_STOCKS]
    data = yf.download(tickers, period="5d", interval="5m", group_by="ticker", progress=False)
    
    ist = pytz.timezone("Asia/Kolkata")
    now_dt = datetime.now(ist)
    time_str = now_dt.strftime("%H:%M:%S")
    full_timestamp_str = now_dt.strftime("%Y-%m-%d %H:%M:%S IST")
    
    signals_list = []

    for sym in FNO_STOCKS:
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
            
            # Traded Value / Turnover approximation (Volume * Close price proxy for liquidity & momentum check)
            avg_volume = float(recent_session_df['Volume'].mean())
            approx_traded_value_cr = round((avg_volume * ltp * 75) / 10000000, 2) # Lot size weighted estimation or scale

            day_range = high_day - low_day
            day_pos_pct = round(((ltp - low_day) / day_range) * 100, 2) if day_range > 0 else 50.0

            # ==========================
            # 🚀 CALL OPTION (CE) - FNO MOMENTUM
            # ==========================
            if day_change_pct >= 0.6 and day_pos_pct >= 55.0:
                breakeven_trigger = round(high_day * 1.002, 2)
                strict_sl = round(ltp * 0.985, 2)
                
                # High weightage for top FnO leaders
                priority_boost = 15.0 if raw_sym in ["RELIANCE", "TCS", "HDFCBANK", "INFY", "BAJFINANCE"] else 0.0
                total_score = day_change_pct + (approx_traded_value_cr * 0.1) + priority_boost

                signals_list.append({
                    "data": [
                        raw_sym, ltp, f"{day_change_pct}%", "🚀 FNO MOMENTUM CE", "BUY CALL OPTION (CE)",
                        f"🟢 ABOVE {breakeven_trigger}", f"🔴 BELOW {strict_sl}", 
                        f"₹{approx_traded_value_cr} Cr", "🔥 EXECUTE IN SENSIBULE", time_str
                    ],
                    "score": total_score
                })

            # ==========================
            # 💥 PUT OPTION (PE) - FNO DISTRIBUTION
            # ==========================
            elif day_change_pct <= -0.6 and day_pos_pct <= 45.0:
                breakeven_trigger = round(low_day * 0.998, 2)
                strict_sl = round(ltp * 1.015, 2)
                total_score = abs(day_change_pct) + (approx_traded_value_cr * 0.1)

                signals_list.append({
                    "data": [
                        raw_sym, ltp, f"{day_change_pct}%", "💥 FNO BEARISH PE", "BUY PUT OPTION (PE)",
                        f"🟢 BELOW {breakeven_trigger}", f"🔴 ABOVE {strict_sl}", 
                        f"₹{approx_traded_value_cr} Cr", "🔥 EXECUTE IN SENSIBULE", time_str
                    ],
                    "score": total_score
                })

        except Exception as e:
            continue

    # Sort strictly by highest conviction score & liquidity traded value
    sorted_signals = sorted(signals_list, key=lambda x: x["score"], reverse=True)[:15]
    return [item["data"] for item in sorted_signals], full_timestamp_str


def run_fno_sync(max_retries=3, delay=5):
    signals_data, full_timestamp_str = analyze_fno_options()
    
    headers = [
        "TICKER", "LTP", "CHANGE %", "TREND STATUS", "STRATEGY", 
        "🎯 TARGET / BREAKEVEN", "🛑 STRICT SL", "EST. TRADED VALUE", "SENSIBULE TRIGGER", "LAST UPDATED"
    ]

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🔄 Attempt {attempt}/{max_retries}: Pushing FnO Traded Value signals to Google Sheets...")
            client = get_gspread_client()
            
            target_sheet_id = os.environ.get("SHEET_ID", SHEET_ID)
            sheet = client.open_by_key(target_sheet_id)

            try:
                ws = sheet.worksheet(SENSIBULE_TAB_NAME)
            except Exception:
                ws = sheet.add_worksheet(title=SENSIBULE_TAB_NAME, rows="100", cols="12")

            ws.clear()
            ws.update(values=[headers] + signals_data, range_name="A1")
            print(f"✅ Successfully pushed {len(signals_data)} FnO option triggers to '{SENSIBULE_TAB_NAME}'!")
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
    run_fno_sync()
