import os
import json
from datetime import datetime
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# CONFIGURATION & GOOGLE SHEETS SETUP
# ==========================================
SHEET_ID = "1YZ-JI0UUEzpHhhW_EWqPcdF2JlAEl_BUmCRjVTAwUBo"
NEW_TAB_NAME = "SUPER_CONVICTION_TRADES"

# High Conviction Ticker Universe
LARGECAP_SYMBOLS = [
    "ULTRACEMCO.NS", "RELIANCE.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "INFY.NS", 
    "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", 
    "AXISBANK.NS", "LT.NS", "MARUTI.NS", "M&M.NS"
]

MIDCAP_SYMBOLS = [
    "KAYNES.NS", "BSE.NS", "HAL.NS", "BEL.NS", "POLYCAB.NS", "DIXON.NS"
]

FNO_SYMBOLS = list(set(LARGECAP_SYMBOLS + MIDCAP_SYMBOLS))

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
        "BACKEND: ABSOLUTE MOMENTUM & BREAKOUT SCANNER", 
        "", "", "", "", 
        f"LAST UPDATED: {curr_time} IST"
    ]

    column_headers = [
        "TICKER", 
        "LTP", 
        "TREND STATUS", 
        "STRATEGY",
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

            # Multi-Index Column Flattening (Fixes yfinance parsing drops)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            ltp = round(float(df['Close'].iloc[-1]), 2)
            prev_close = float(df['Close'].iloc[-2])
            chg_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
            point_move = abs(ltp - prev_close)

            day_high = float(df['High'].iloc[-1])
            day_low = float(df['Low'].iloc[-1])
            day_range = day_high - day_low
            
            close_pos = (ltp - day_low) / day_range if day_range > 0 else 0

            vol_curr = float(df['Volume'].iloc[-1])
            vol_avg = float(df['Volume'].iloc[-20:-1].mean())
            vol_mult = vol_curr / vol_avg if vol_avg > 0 else 1.0

            five_day_high = float(df['High'].tail(6).iloc[:-1].max())
            is_bullish_breakout = ltp > five_day_high

            clean_ticker = sym.replace(".NS", "")
            is_largecap = sym in LARGECAP_SYMBOLS

            detected = False
            trend_status = ""
            strategy = ""

            # Strategy Selection Logic
            if is_largecap:
                # Case 1: LargeCap Steady Accumulation (e.g. ULTRACEMCO)
                if vol_mult >= 1.10 and close_pos >= 0.60 and is_bullish_breakout:
                    detected = True
                    trend_status = "🔥 LARGECAP ACCUMULATION"
                    strategy = "BULL CALL SPREAD"
            else:
                # Case 2: High-Beta Momentum Breakout (e.g. BSE, KAYNES)
                if (vol_mult >= 1.30 or is_bullish_breakout) and close_pos >= 0.65 and chg_pct >= 2.0:
                    detected = True
                    trend_status = "🚀 MOMENTUM BREAKOUT"
                    strategy = "BUY CALL OPTION (CE)"

            # Filter for Pure Positive Breakouts & Calculate Weighted Ranking
            if detected and chg_pct > 0:
                breakeven = round(ltp * 1.012, 2)
                sl = round(ltp * 0.985, 2)

                # Adjusted Scoring: Point Move + % Gain + Breakout Bonus
                breakout_bonus = 10.0 if is_bullish_breakout else 0.0
                score = (chg_pct * 5.0) + (point_move * 0.1) + (vol_mult * 2.0) + breakout_bonus

                raw_signals.append({
                    "TICKER": clean_ticker, 
                    "LTP": ltp, 
                    "TREND": trend_status,
                    "STRATEGY": strategy,
                    "BREAKEVEN": breakeven, 
                    "SL": sl, 
                    "SCORE": score
                })

        except Exception as e:
            print(f"Error processing {sym}: {e}")
            continue

    # Process and Write Top Ranked Signals to Google Sheet
    if raw_signals:
        df_raw = pd.DataFrame(raw_signals)
        df_raw = df_raw.sort_values(by="SCORE", ascending=False)

        final_rows = []
        for idx, row in df_raw.reset_index(drop=True).iterrows():
            top_selection = "🔥 EXECUTE IN SENSIBULE" if idx < 3 else "WATCHLIST SIGNAL"
            final_rows.append([
                row["TICKER"], 
                str(row["LTP"]), 
                row["TREND"],
                row["STRATEGY"],
                str(row["BREAKEVEN"]), 
                str(row["SL"]), 
                top_selection
            ])

        payload = [rule_headers, column_headers] + final_rows
    else:
        payload = [
            rule_headers, 
            column_headers, 
            ["NO STRONG BREAKOUT MATCHED CURRENTLY"] + [""] * 6
        ]

    # Write Payload to Target Sheet Tab
    try:
        ws.clear()
        ws.update(values=payload, range_name="A1", value_input_option="USER_ENTERED")
        print(f"✅ Executed Successfully at {curr_time} IST!")
    except Exception as e:
        print(f"❌ Sheet Update Failed: {str(e)}")

if __name__ == "__main__":
    run_final_sensibule_scanner()
