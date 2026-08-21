import os
import json
import time
import pandas as pd
import yfinance as yf
import gspread
from datetime import datetime
import pytz
from google.oauth2.service_account import Credentials

# ==============================================================================
# SECTION 1: GOOGLE SHEETS AUTHENTICATION
# ==============================================================================
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client():
    gcp_creds_json = os.environ.get("GCP_CREDENTIALS_JSON")
    
    if gcp_creds_json:
        creds_dict = json.loads(gcp_creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
        
    return gspread.authorize(creds)

# ==============================================================================
# 1. AAPKI EXACT SELECTED STOCKS WATCHLIST (YFinance / NSE Tickers)
# ==============================================================================
INDEX_TICKER = "^NSEI"  # Nifty 50 Index Ticker

STOCKS = [
    INDEX_TICKER, "TCS.NS", "HINDPETRO.NS", "IREDA.NS", "SUNPHARMA.NS", "ITC.NS",
    "TITAN.NS", "LAURUSLABS.NS", "JSWENERGY.NS", "VEDL.NS", "COALINDIA.NS",
    "HINDZINC.NS", "ZYDUSLIFE.NS", "GODREJPROP.NS", "PERSISTENT.NS", "DMART.NS",
    "WIPRO.NS", "PAGEIND.NS", "PAYTM.NS", "MPHASIS.NS", "SBIN.NS", "MARUTI.NS",
    "ULTRACEMCO.NS", "HINDUNILVR.NS", "CIPLA.NS", "BPCL.NS", "RVNL.NS",
    "BRITANNIA.NS", "OFSS.NS", "MARICO.NS", "BIOCON.NS", "ABB.NS",
    "TATACONSUM.NS", "CUMMINSIND.NS", "RECLTD.NS", "COCHINSHIP.NS", "MANKIND.NS",
    "INFY.NS", "HCLTECH.NS", "NBCC.NS", "ALKYLAMINE.NS", "DELHIVERY.NS",
    "KPITTECH.NS", "NATIONALUM.NS", "TATAELXSI.NS", "AMBUJACEM.NS", "JSWSTEEL.NS",
    "BALKRISIND.NS", "ASIANPAINT.NS", "ABBOTINDIA.NS", "HINDALCO.NS", "NYKAA.NS",
    "BLUESTARCO.NS", "IOC.NS", "NESTLEIND.NS", "PREMIERENE.NS", "INDIGO.NS",
    "BAJAJ-AUTO.NS", "KAYNES.NS", "DRREDDY.NS", "TVSMOTOR.NS", "UPL.NS",
    "SWIGGY.NS", "COFORGE.NS", "VOLTAS.NS", "BHARTIARTL.NS", "EICHERMOT.NS",
    "NTPC.NS", "LODHA.NS", "ETERNAL.NS", "POLYCAB.NS", "DLF.NS", "SUZLON.NS",
    "CONCOR.NS", "JINDALSTEL.NS", "ICICIPRULI.NS", "DALBHARAT.NS", "INDUSTOWER.NS",
    "ASHOKLEY.NS", "CDSL.NS", "GLENMARK.NS", "PNB.NS", "INOXWIND.NS",
    "ASTRAL.NS", "KALYANKJIL.NS", "BSE.NS", "TECHM.NS", "SHREECEM.NS",
    "PIIND.NS", "CAMSTI.NS", "IIDA.NS", "TATASTEEL.NS", "M&M.NS", "LUPIN.NS",
    "GAIL.NS", "PFC.NS", "SUPREMEIND.NS", "WAAREEENER.NS", "KEI.NS",
    "FORTIS.NS", "TORNTPHARM.NS", "ICICIBANK.NS", "SRF.NS", "DIXON.NS",
    "GRASIM.NS", "HEROMOTOCO.NS", "CROMPTON.NS", "MRF.NS", "SIEMENS.NS",
    "PHOENIXLTD.NS", "PIDILITIND.NS", "UNOMINDA.NS", "NMDC.NS", "SAIL.NS",
    "POWERGRID.NS", "MOTHERSON.NS", "NHPC.NS", "RELIANCE.NS", "JUBLFOOD.NS",
    "MAXHEALTH.NS", "MOTILALOFS.NS", "SOLARINDS.NS", "AMBER.NS", "AUROPHARMA.NS",
    "CGPOWER.NS", "PETRONET.NS", "DIVISLAB.NS", "HAVELLS.NS", "LT.NS",
    "BEL.NS", "LTF.NS", "TATAPOWER.NS", "BHARATFORG.NS", "SONACOMS.NS",
    "APOLLOHOSP.NS", "HAL.NS", "BOSCHLTD.NS", "APOLLOTYRE.NS", "BHEL.NS",
    "KFINTECH.NS", "ANGELONE.NS", "GODREJCP.NS", "BDL.NS", "NAUKRI.NS"
]

# ==============================================================================
# SECTION 3: DATA FETCHING & DUAL DASHBOARD LOGIC (STRICT TREND ALIGNMENT)
# ==============================================================================
def fetch_and_process_data():
    ist = pytz.timezone('Asia/Kolkata')
    current_time_only = datetime.now(ist).strftime('%H:%M:%S')
    
    print(f"⏳ Fetching market data for {len(STOCKS)} stocks at {current_time_only} IST...")
    
    try:
        raw_data = yf.download(
            tickers=STOCKS,
            period="5d",
            interval="15m",
            group_by='ticker',
            threads=True,
            timeout=15,
            progress=False
        )

        ce_records = []
        pe_records = []

        for symbol in STOCKS:
            try:
                if symbol in raw_data:
                    df = raw_data[symbol].dropna()
                else:
                    df = raw_data.dropna()

                if df.empty or len(df) < 5:
                    continue

                ltp = float(df['Close'].iloc[-1])
                open_p = float(df['Open'].iloc[-1])
                
                # FIXED VOLUME CALCULATION
                vol_series = df['Volume'].replace(0, pd.NA).dropna()
                if not vol_series.empty:
                    volume = float(vol_series.iloc[-1])
                    avg_vol = float(vol_series.mean())
                else:
                    volume = 1.0
                    avg_vol = 1.0

                high = float(df['High'].iloc[-1])
                low = float(df['Low'].iloc[-1])
                vwap = (high + low + ltp) / 3

                # STRICT TREND DEFINITION
                ema20 = df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                
                price_chg = round(((ltp - open_p) / open_p) * 100, 2)
                vol_mult = round(volume / avg_vol, 2) if avg_vol > 0 else 1.0
                vol_display = f"{vol_mult}x ⚡" if vol_mult >= 1.0 else f"{vol_mult}x 💧"
                clean_sym = symbol.replace('.NS', '')

                # Trend Alignment
                if ltp > ema20 and price_chg > 0.05:
                    trend = "🟢 UPTREND"
                elif ltp < ema20 and price_chg < -0.05:
                    trend = "🔴 DOWNTREND"
                else:
                    trend = "🟡 SIDEWAYS"

                # --------------------------------------------------------------
                # CE DASHBOARD LOGIC (STRICTLY REQUIRES 🟢 UPTREND)
                # --------------------------------------------------------------
                ce_score = round(min((vol_mult * 2.0) + (max(0, price_chg) * 2.5), 10.0), 1)

                if symbol == INDEX_TICKER:
                    ce_action = "BENCHMARK 🏛️"
                    ce_plan = "NIFTY INDEX"
                    ce_priority = 99
                # RULE: BUY CE ONLY IF TREND IS UPTREND!
                elif trend == "🟢 UPTREND" and ltp > vwap and price_chg > 0.15:
                    if vol_mult >= 1.0:
                        ce_action = "BUY CE NOW 🟢"
                        ce_plan = f"BUY ABOVE {round(ltp, 1)} (SL: {round(vwap, 1)})"
                        ce_priority = 1
                    else:
                        ce_action = "WATCH CE 👀"
                        ce_plan = "WAIT FOR VOL SPIKE"
                        ce_priority = 2
                elif trend == "🟢 UPTREND":
                    ce_action = "WATCH CE 👀"
                    ce_plan = "WAIT FOR BREAKOUT"
                    ce_priority = 3
                else:
                    # Downtrend / Sideways stocks automatically rejected for CE
                    ce_action = "NO CE SETUP 🚫"
                    ce_plan = "NO UPTREND"
                    ce_priority = 4

                ce_records.append({
                    'Clean Symbol': clean_sym,
                    'Trend': trend,
                    'LTP': round(ltp, 2),
                    'Action / Entry Trigger': ce_action,
                    'CE Entry Plan': ce_plan,
                    'Volume Spike': vol_display,
                    'CE Strength Score': ce_score,
                    'Priority': ce_priority,
                    'Vol_Raw': vol_mult,
                    'Execution Time': current_time_only
                })

                # --------------------------------------------------------------
                # PE DASHBOARD LOGIC (STRICTLY REQUIRES 🔴 DOWNTREND)
                # --------------------------------------------------------------
                pe_score = round(min((vol_mult * 2.0) + (abs(min(0, price_chg)) * 2.5), 10.0), 1)

                if symbol == INDEX_TICKER:
                    pe_action = "BENCHMARK 🏛️"
                    pe_plan = "NIFTY INDEX"
                    pe_priority = 99
                # RULE: BUY PE ONLY IF TREND IS DOWNTREND!
                elif trend == "🔴 DOWNTREND" and ltp < vwap and price_chg < -0.15:
                    if vol_mult >= 1.0:
                        pe_action = "BUY PE NOW 🔴"
                        pe_plan = f"BUY BELOW {round(ltp, 1)} (SL: {round(vwap, 1)})"
                        pe_priority = 1
                    else:
                        pe_action = "WATCH PE 👀"
                        pe_plan = "WAIT FOR VOL SPIKE"
                        pe_priority = 2
                elif trend == "🔴 DOWNTREND":
                    pe_action = "WATCH PE 👀"
                    pe_plan = "WAIT FOR BREAKDOWN"
                    pe_priority = 3
                else:
                    # Uptrend / Sideways stocks automatically rejected for PE
                    pe_action = "NO PE SETUP 🚫"
                    pe_plan = "NO DOWNTREND"
                    pe_priority = 4

                pe_records.append({
                    'Clean Symbol': clean_sym,
                    'Trend': trend,
                    'LTP': round(ltp, 2),
                    'Action / Entry Trigger': pe_action,
                    'PE Entry Plan': pe_plan,
                    'Volume Spike': vol_display,
                    'PE Strength Score': pe_score,
                    'Priority': pe_priority,
                    'Vol_Raw': vol_mult,
                    'Execution Time': current_time_only
                })

            except Exception:
                continue

        # Processing CE DataFrame
        df_ce = pd.DataFrame(ce_records)
        if not df_ce.empty:
            df_ce = df_ce.sort_values(by=['Priority', 'CE Strength Score', 'Vol_Raw'], ascending=[True, False, False]).reset_index(drop=True)
            df_ce['Rank'] = [f"#{i+1}" for i in range(len(df_ce))]
            df_ce = df_ce[['Rank', 'Trend', 'Clean Symbol', 'LTP', 'Action / Entry Trigger', 'CE Entry Plan', 'Volume Spike', 'CE Strength Score', 'Execution Time']]

        # Processing PE DataFrame
        df_pe = pd.DataFrame(pe_records)
        if not df_pe.empty:
            df_pe = df_pe.sort_values(by=['Priority', 'PE Strength Score', 'Vol_Raw'], ascending=[True, False, False]).reset_index(drop=True)
            df_pe['Rank'] = [f"#{i+1}" for i in range(len(df_pe))]
            df_pe = df_pe[['Rank', 'Trend', 'Clean Symbol', 'LTP', 'Action / Entry Trigger', 'PE Entry Plan', 'Volume Spike', 'PE Strength Score', 'Execution Time']]

        return df_ce, df_pe

    except Exception as e:
        print(f"❌ YFinance Fetch Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ==============================================================================
# SECTION 4: GOOGLE SHEET UPDATER
# ==============================================================================
def update_tab(sh, df, target_tab_name):
    if df.empty:
        print(f"⚠️ DataFrame empty for {target_tab_name}. Skipping update.")
        return

    try:
        try:
            worksheet = sh.worksheet(target_tab_name)
        except gspread.exceptions.WorksheetNotFound:
            print(f"⚠️ Tab '{target_tab_name}' not found. Creating it now...")
            worksheet = sh.add_worksheet(title=target_tab_name, rows="200", cols="10")

        headers = df.columns.tolist()
        values = [headers] + df.astype(str).values.tolist()

        worksheet.clear()
        worksheet.update('A1', values)
        print(f"✅ Successfully updated tab '{target_tab_name}'! Total Rows: {len(df)}")

    except Exception as e:
        print(f"❌ Google Sheets Update Failed for '{target_tab_name}': {e}")

# ==============================================================================
# SECTION 5: MAIN EXECUTION ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    df_ce, df_pe = fetch_and_process_data()

    sheet_id = os.environ.get("SHEET_ID")
    if not sheet_id:
        print("❌ Error: SHEET_ID Secret is missing!")
    else:
        try:
            gc = get_gspread_client()
            sh = gc.open_by_key(sheet_id)

            # 1. Update LIVE_CE_DASHBOARD Tab
            update_tab(sh, df_ce, "LIVE_CE_DASHBOARD")

            # 2. Update LIVE_PE_DASHBOARD Tab
            update_tab(sh, df_pe, "LIVE_PE_DASHBOARD")

        except Exception as e:
            print(f"❌ Failed to connect to Google Sheets: {e}")
