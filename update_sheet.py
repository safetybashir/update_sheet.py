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
# 1. SETUP GOOGLE SHEETS AUTHENTICATION
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
# 2. WATCHLIST (140+ STOCKS)
# ==============================================================================
INDEX_TICKER = "^NSEI"

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
# 3. FETCH MARKET DATA WITH REAL-TIME IST TIMESTAMP
# ==============================================================================
def fetch_stock_data():
    ist = pytz.timezone('Asia/Kolkata')
    current_time_ist = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"⏳ Fetching market data for {len(STOCKS)} stocks at {current_time_ist} IST...")
    
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

        records = []
        for symbol in STOCKS:
            try:
                if symbol in raw_data:
                    df = raw_data[symbol].dropna()
                else:
                    df = raw_data.dropna()

                if df.empty:
                    continue

                ltp = float(df['Close'].iloc[-1])
                prev_close = float(df['Open'].iloc[0])
                volume = float(df['Volume'].iloc[-1])
                avg_vol = float(df['Volume'].mean())

                high = float(df['High'].iloc[-1])
                low = float(df['Low'].iloc[-1])
                vwap = (high + low + ltp) / 3

                vol_mult = round(volume / avg_vol, 2) if avg_vol > 0 else 1.0
                price_chg = round(((ltp - prev_close) / prev_close) * 100, 2)

                vcp_signal = "YES" if (vol_mult >= 1.5 and ltp > vwap) else "NO"
                
                if symbol == INDEX_TICKER:
                    action = "BENCHMARK 🏛️"
                elif ltp > vwap and vol_mult >= 1.5 and vcp_signal == "YES":
                    action = "BUY CE (15M CONFIRMED) 🟢"
                elif ltp < vwap and vol_mult >= 1.5 and vcp_signal == "YES":
                    action = "BUY PE (15M CONFIRMED) 🔴"
                else:
                    action = "NO ENTRY 🚫"

                records.append({
                    'Clean Symbol': symbol.replace('.NS', ''),
                    'LTP': round(ltp, 2),
                    'Price % Change': price_chg,
                    'Volume Status': f"{vol_mult}x SPIKE ⚡" if vol_mult >= 1.5 else "DRY-UP 💧",
                    'VWAP': round(vwap, 2),
                    'Action / Entry Trigger': action,
                    'Execution Time (IST)': current_time_ist
                })
            except Exception:
                continue

        return pd.DataFrame(records)

    except Exception as e:
        print(f"❌ YFinance Fetch Error: {e}")
        return pd.DataFrame()

# ==============================================================================
# 4. DIRECT UPDATE TO "LIVE_DASHBOARD" TAB
# ==============================================================================
def update_google_sheet(df):
    if df.empty:
        print("⚠️ DataFrame empty. Skipping Google Sheets update.")
        return

    sheet_id = os.environ.get("SHEET_ID")
    if not sheet_id:
        print("❌ Error: SHEET_ID Secret is missing!")
        return

    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(sheet_id)

        # Specifically Target "LIVE_DASHBOARD" Tab
        target_tab_name = "LIVE_DASHBOARD"
        try:
            worksheet = sh.worksheet(target_tab_name)
        except gspread.exceptions.WorksheetNotFound:
            print(f"⚠️ Tab '{target_tab_name}' not found. Creating it now...")
            worksheet = sh.add_worksheet(title=target_tab_name, rows="200", cols="20")

        # Sorting: Priority signals on top
        df_confirmed = df[df['Action / Entry Trigger'].str.contains('CONFIRMED', na=False)]
        df_others = df[~df['Action / Entry Trigger'].str.contains('CONFIRMED', na=False)]
        final_df = pd.concat([df_confirmed, df_others]).reset_index(drop=True)

        headers = final_df.columns.tolist()
        values = [headers] + final_df.astype(str).values.tolist()

        worksheet.clear()
        worksheet.update('A1', values)
        print(f"✅ Successfully updated tab '{target_tab_name}'! Total Rows: {len(final_df)}")

    except Exception as e:
        print(f"❌ Google Sheets Update Failed: {e}")

if __name__ == "__main__":
    df_result = fetch_stock_data()
    update_google_sheet(df_result)
