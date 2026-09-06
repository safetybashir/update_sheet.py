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

# 1. LARGECAP F&O STOCKS (~50 Heavyweights)
LARGECAP_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", 
    "BHARTIARTL.NS", "SBIN.NS", "LTIM.NS", "LT.NS", "ITC.NS", 
    "HINDUNILVR.NS", "AXISBANK.NS", "KOTAKBANK.NS", "M&M.NS", "MARUTI.NS", 
    "SUNPHARMA.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "NTPC.NS", "POWERGRID.NS", 
    "ULTRACEMCO.NS", "TITAN.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "ADANIENT.NS", 
    "ADANIPORTS.NS", "COALINDIA.NS", "ONGC.NS", "GRASIM.NS", "JSWSTEEL.NS", 
    "HCLTECH.NS", "TECHM.NS", "WIPRO.NS", "ASIANPAINT.NS", "NESTLEIND.NS", 
    "DLF.NS", "IOC.NS", "BPCL.NS", "GAIL.NS", "REC.NS", 
    "PFC.NS", "HAL.NS", "BEL.NS", "SIEMENS.NS", "ABB.NS", 
    "HDFCLIFE.NS", "SBILIFE.NS", "ICICIPRULI.NS", "PIDILITIND.NS", "INDIGO.NS"
]

# 2. MIDCAP / HIGH-BETA F&O STOCKS (~130+ Active Movers)
MIDCAP_SYMBOLS = [
    "BSE.NS", "KAYNES.NS", "POLYCAB.NS", "DIXON.NS", "PERSISTENT.NS", 
    "COFORGE.NS", "MCX.NS", "TRENT.NS", "MUTHOOTFIN.NS", "CHOLAFIN.NS", 
    "MANAPPURAM.NS", "AUROPHARMA.NS", "LUPIN.NS", "BIOCON.NS", "DRREDDY.NS", 
    "CIPLA.NS", "GLENMARK.NS", "TORNTPHARM.NS", "DIVISLAB.NS", "SYNGENE.NS", 
    "APOLLOHOSP.NS", "MAXHEALTH.NS", "FORTIS.NS", "ABBOTINDIA.NS", "IPCALAB.NS", 
    "VOLTAS.NS", "BLUESTARCO.NS", "HAVELLS.NS", "CUMMINSIND.NS", "ASTRAL.NS", 
    "KEI.NS", "SUPREMEIND.NS", "PIIND.NS", "UPL.NS", "SRF.NS", 
    "ATUL.NS", "DEEPAKNTR.NS", "NAVINFLUOR.NS", "CHEMICALS.NS", "CONCOR.NS", 
    "EXIDEIND.NS", "AMARAJABAT.NS", "BOSCHLTD.NS", "BHARATFORG.NS", "BALKRISIND.NS", 
    "TIINDIA.NS", "ASHOKLEY.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "TVSMOTOR.NS", 
    "ESCORTS.NS", "MRF.NS", "MOTHERSON.NS", "APOLLOTYRE.NS", "CANBK.NS", 
    "UNIONBANK.NS", "BANKBARODA.NS", "PNB.NS", "IDFCFIRSTB.NS", "FEDERALBNK.NS", 
    "BANDHANBNK.NS", "AUBANK.NS", "INDUSINDBK.NS", "RBLBANK.NS", "MFSL.NS", 
    "LICHSGFIN.NS", "PEL.NS", "L&TFH.NS", "SHRIRAMFIN.NS", "PIRAMAL.NS", 
    "M&MFIN.NS", "CREDITACC.NS", "ISEC.NS", "ANGELONE.NS", 
    "CDSL.NS", "CAMS.NS", "OBEROIRTY.NS", 
    "GODREJPROP.NS", "PHOENIXLTD.NS", "LODHA.NS", "PRESTIGE.NS", "SOBHA.NS", 
    "NATIONALUM.NS", "HINDALCO.NS", "VEDL.NS", "NMDC.NS", "SAIL.NS", 
    "JINDALSTEL.NS", "HINDCOPPER.NS", "APLAPOLLO.NS", "RATNAMANI.NS", "IRCTC.NS", 
    "IRFC.NS", "RVNL.NS", "RAILTEL.NS", "TITAGARH.NS", "BHEL.NS", 
    "NHPC.NS", "SJVN.NS", "NLCINDIA.NS", "TORNTPOWER.NS", 
    "TATAPOWER.NS", "ADANIPOWER.NS", "ADANIGREEN.NS", "CESC.NS", "SUZLON.NS", 
    "INOXWIND.NS", "ZOMATO.NS", "PAYTM.NS", "POLICYBZR.NS", "NYKAA.NS", 
    "DELHIVERY.NS", "NAUKRI.NS", "INDAMART.NS", "JUSTDIAL.NS", "MAPMYINDIA.NS", 
    "PVRINOX.NS", "DEVYANI.NS", "JUBLFOOD.NS", "WESTLIFE.NS", "TATACONSUM.NS", 
    "VBL.NS", "UBL.NS", "MCDOWELL-N.NS", "RADICO.NS", "COLPAL.NS", 
    "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "BRITANNIA.NS", "BALRAMCHIN.NS"
]

# Combine and remove duplicates
FNO_SYMBOLS = list(set(LARGECAP_SYMBOLS + MIDCAP_SYMBOLS))

def get_gspread_client():
    creds_json = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDS")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if creds_json:
        creds_dict = json.loads(creds_json)
        return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json")
    else:
        raise FileNotFoundError("❌ Google Cloud Credentials not found!")

def get_or_create_worksheet(spreadsheet, title):
    try:
        for ws in spreadsheet.worksheets():
            if ws.title.strip().upper() == title.strip().upper():
                return ws
        return spreadsheet.add_worksheet(title=title, rows="300", cols="10")
    except Exception:
        return spreadsheet.sheet1

# ==========================================
# MAIN SCANNER (TOP 5 EXECUTION SELECTION)
# ==========================================
def run_final_sensibule_scanner():
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    ws = get_or_create_worksheet(spreadsheet, NEW_TAB_NAME)

    ist_tz = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist_tz).strftime('%Y-%m-%d %H:%M:%S')

    rule_headers = [
        "SENSIBULE EXECUTION ENGINE", 
        "BACKEND: DUAL-DIRECTIONAL SCANNER (TOP 5 HIGHEST CONVICTION)", 
        "", "", "", "", 
        f"LAST UPDATED: {curr_time} IST"
    ]

    column_headers = [
        "TICKER", 
        "LTP", 
        "TREND STATUS", 
        "STRATEGY",
        "🎯 TARGET / BREAKEVEN", 
        "🛑 STRICT SL (1.5%)", 
        "SENSIBULE TRIGGER"
    ]

    raw_signals = []

    for sym in FNO_SYMBOLS:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="30d", interval="1d")
            
            if len(df) < 20:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            ltp = round(float(df['Close'].iloc[-1]), 2)
            prev_close = float(df['Close'].iloc[-2])
            chg_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
            point_move = abs(ltp - prev_close)

            day_high = float(df['High'].iloc[-1])
            day_low = float(df['Low'].iloc[-1])
            day_range = day_high - day_low
            
            close_pos = (ltp - day_low) / day_range if day_range > 0 else 0.5

            vol_curr = float(df['Volume'].iloc[-1])
            vol_avg = float(df['Volume'].iloc[-20:-1].mean())
            vol_mult = vol_curr / vol_avg if vol_avg > 0 else 1.0

            five_day_high = float(df['High'].iloc[-6:-1].max())
            five_day_low = float(df['Low'].iloc[-6:-1].min())
            
            is_bullish_breakout = ltp >= five_day_high
            is_bearish_breakdown = ltp <= five_day_low

            clean_ticker = sym.replace(".NS", "")
            is_largecap = sym in LARGECAP_SYMBOLS

            detected = False
            trend_status = ""
            strategy = ""

            # 1. BULLISH SCENARIOS (CE / BULL CALL SPREAD)
            if chg_pct > 0:
                if is_largecap:
                    if (is_bullish_breakout or chg_pct >= 2.5) and close_pos >= 0.60:
                        detected = True
                        trend_status = "🔥 LARGECAP ACCUMULATION"
                        strategy = "BULL CALL SPREAD"
                else:
                    if (chg_pct >= 3.0 or (is_bullish_breakout and vol_mult >= 1.1)) and close_pos >= 0.65:
                        detected = True
                        trend_status = "🚀 MOMENTUM BREAKOUT"
                        strategy = "BUY CALL OPTION (CE)"

            # 2. BEARISH SCENARIOS (PE / BEAR PUT SPREAD)
            elif chg_pct < 0:
                if is_largecap:
                    if (is_bearish_breakdown or chg_pct <= -2.5) and close_pos <= 0.40:
                        detected = True
                        trend_status = "🔻 LARGECAP DISTRIBUTION"
                        strategy = "BEAR PUT SPREAD"
                else:
                    if (chg_pct <= -3.0 or (is_bearish_breakdown and vol_mult >= 1.1)) and close_pos <= 0.35:
                        detected = True
                        trend_status = "💥 BEARISH BREAKDOWN"
                        strategy = "BUY PUT OPTION (PE)"

            # SIMPLIFIED EMOJI & TEXT BASED TARGET & SL LOGIC
            if detected:
                if "CALL" in strategy or "CE" in strategy:
                    be_val = round(ltp * 1.012, 2)
                    sl_val = round(ltp * 0.985, 2)
                    breakeven_display = f"🟢 ABOVE {be_val}"
                    sl_display = f"🔴 BELOW {sl_val}"
                else:  # PUT / PE Strategies
                    be_val = round(ltp * 0.988, 2)
                    sl_val = round(ltp * 1.015, 2)
                    breakeven_display = f"🟢 BELOW {be_val}"
                    sl_display = f"🔴 ABOVE {sl_val}"

                breakout_bonus = 15.0 if (is_bullish_breakout or is_bearish_breakdown) else 0.0
                score = (abs(chg_pct) * 6.0) + (point_move * 0.5) + (vol_mult * 2.0) + breakout_bonus

                raw_signals.append({
                    "TICKER": clean_ticker, 
                    "LTP": ltp, 
                    "TREND": trend_status,
                    "STRATEGY": strategy,
                    "BREAKEVEN": breakeven_display, 
                    "SL": sl_display, 
                    "SCORE": score
                })

        except Exception as e:
            continue

    # Write Payload to Sheet
    if raw_signals:
        df_raw = pd.DataFrame(raw_signals)
        df_raw = df_raw.sort_values(by="SCORE", ascending=False)

        final_rows = []
        for idx, row in df_raw.reset_index(drop=True).iterrows():
            # TOP 5 TRADES ARE SET TO "🔥 EXECUTE IN SENSIBULE"
            top_selection = "🔥 EXECUTE IN SENSIBULE" if idx < 5 else "WATCHLIST SIGNAL"
            final_rows.append([
                row["TICKER"], 
                str(row["LTP"]), 
                row["TREND"],
                row["STRATEGY"],
                row["BREAKEVEN"], 
                row["SL"], 
                top_selection
            ])

        payload = [rule_headers, column_headers] + final_rows
    else:
        payload = [rule_headers, column_headers, ["NO ACTIVE BREAKOUT OR BREAKDOWN MATCHED"] + [""] * 6]

    try:
        ws.clear()
        ws.update(values=payload, range_name="A1", value_input_option="USER_ENTERED")
        print(f"✅ Executed Successfully for TOP 5 Trades at {curr_time} IST!")
    except Exception as e:
        print(f"❌ Sheet Update Failed: {str(e)}")

if __name__ == "__main__":
    run_final_sensibule_scanner()
