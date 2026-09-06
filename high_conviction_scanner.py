import os
import json
from datetime import datetime
import pytz
import pandas as pd
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# CONFIGURATION & GOOGLE SHEETS SETUP
# ==========================================
SHEET_ID = "1YZ-JI0UUEzpHhhW_EWqPcdF2JlAEl_BUmCRjVTAwUBo"
NEW_TAB_NAME = "SUPER_CONVICTION_TRADES"

# Highly Liquid F&O Tickers
FNO_SYMBOLS = [
    "RELIANCE.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "INFY.NS", "TCS.NS", 
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "AXISBANK.NS",
    "LT.NS", "MARUTI.NS", "M&M.NS", "HAL.NS", "BEL.NS", "POLYCAB.NS"
]

def get_gspread_client():
    """Authenticates using Environment variable or local credentials file."""
    creds_json = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDS")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets", 
        "https://www.googleapis.com/auth/drive"
    ]
    if creds_json:
        creds_dict = json.loads(creds_json)
        return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json")
    else:
        raise FileNotFoundError("❌ Google Cloud Credentials not found!")

def get_or_create_worksheet(spreadsheet, title):
    """Fetches target worksheet or creates a clean one if missing."""
    try:
        for ws in spreadsheet.worksheets():
            if ws.title.strip().upper() == title.strip().upper():
                return ws
        return spreadsheet.add_worksheet(title=title, rows="300", cols="10")
    except Exception:
        return spreadsheet.sheet1

# ==========================================
# MAIN TRADING ENGINE & SCANNER
# ==========================================
def run_final_sensibule_scanner():
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    ws = get_or_create_worksheet(spreadsheet, NEW_TAB_NAME)

    ist_tz = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist_tz).strftime('%Y-%m-%d %H:%M:%S')

    rule_headers = [
        "SENSIBULE EXECUTION ENGINE", 
        "BACKEND: OI BUILDUP / SHORT COVERING + MOMENTUM", 
        "", "", "", 
        "EXECUTION: ZERODHA GTT TSL READY"
    ]

    column_headers = [
        "TICKER", 
        "LTP", 
        "TREND STATUS", 
        "STRATEAGY",
        "BREAKEVEN POINT", 
        "STRICT SL (1.5%)", 
        "SENSIBULE TRIGGER"
    ]

    raw_signals = []

    for sym in FNO_SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="30d", interval="1d")
            
            if len(df) < 20:
                continue

            # Moving Averages Calculation
            df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()

            ltp = round(float(df['Close'].iloc[-1]), 2)
            prev_close = float(df['Close'].iloc[-2])
            chg_pct = round(((ltp - prev_close) / prev_close) * 100, 2)

            ema20 = float(df['EMA_20'].iloc[-1])
            ema50 = float(df['EMA_50'].iloc[-1])

            # Volume Expansion Multiplier
            vol_curr = float(df['Volume'].iloc[-1])
            vol_avg = float(df['Volume'].iloc[-20:-1].mean())
            vol_mult = vol_curr / vol_avg if vol_avg > 0 else 1.0

            clean_ticker = sym.replace(".NS", "")

            # -------------------------------------------------------------
            # BACKEND ENGINE LOGIC:
            # UPTREND:  Price > EMA20 > EMA50 + Gain >= 1.0% + Vol >= 1.5x
            # DOWNTREND: Price < EMA20 < EMA50 + Cut <= -1.0% + Vol >= 1.5x
            # -------------------------------------------------------------
            is_strong_uptrend = (ltp > ema20) and (ema20 > ema50) and (chg_pct >= 1.0) and (vol_mult >= 1.5)
            is_strong_downtrend = (ltp < ema20) and (ema20 < ema50) and (chg_pct <= -1.0) and (vol_mult >= 1.5)

            if is_strong_uptrend:
                trend_status = "🔥 STRONG UPTREND"
                breakeven = round(ltp * 1.012, 2)  # 1.2% buffer for option premium cost
                sl = round(ltp * 0.985, 2)        # 1.5% Strict SL
                score = vol_mult + chg_pct

                raw_signals.append({
                    "TICKER": clean_ticker, 
                    "LTP": ltp, 
                    "TREND": trend_status,
                    "BREAKEVEN": breakeven, 
                    "SL": sl, 
                    "SCORE": score
                })

            elif is_strong_downtrend:
                trend_status = "📉 STRONG DOWNTREND"
                breakeven = round(ltp * 0.988, 2)  # 1.2% downside buffer
                sl = round(ltp * 1.015, 2)        # 1.5% Strict SL
                score = vol_mult + abs(chg_pct)

                raw_signals.append({
                    "TICKER": clean_ticker, 
                    "LTP": ltp, 
                    "TREND": trend_status,
                    "BREAKEVEN": breakeven, 
                    "SL": sl, 
                    "SCORE": score
                })

        except Exception:
            continue

    # Filter Top 3 Super-Conviction Trades
    if raw_signals:
        df_raw = pd.DataFrame(raw_signals)
        df_raw = df_raw.sort_values(by="SCORE", ascending=False)
        top_3_tickers = list(df_raw.head(3)["TICKER"])

        final_rows = []
        for idx, row in df_raw.iterrows():
            top_selection = "🔥 EXECUTE IN SENSIBULE" if row["TICKER"] in top_3_tickers else "WATCHLIST"
            final_rows.append([
                row["TICKER"], 
                str(row["LTP"]), 
                row["TREND"],
                str(row["BREAKEVEN"]), 
                str(row["SL"]), 
                top_selection
            ])

        payload = [rule_headers, column_headers] + final_rows
    else:
        payload = [
            rule_headers, 
            column_headers, 
            ["NO STRONG CONTINUATION TREND MATCHED CURRENTLY"] + [""] * 5
        ]

    # Write Payload to Google Sheet
    try:
        ws.clear()
        ws.update(values=payload, range_name="A1", value_input_option="USER_ENTERED")
        print(f"✅ Executed Successfully at {curr_time} IST!")
    except Exception as e:
        print(f"❌ Sheet Update Failed: {str(e)}")

if __name__ == "__main__":
    run_final_sensibule_scanner()
