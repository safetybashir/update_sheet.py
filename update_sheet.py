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
# 3. FETCH MARKET DATA WITH STRATEGY SCORING & TIME ONLY
# ==============================================================================
def fetch_stock_data():
    ist = pytz.timezone('Asia/Kolkata')
    # Execution Time ONLY (No Date) -> e.g. "09:45:12"
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
                vwap_status = "ABOVE 📈" if ltp >= vwap else "BELOW 📉"

                # Calculate Strategy Strength Score (0 to 10)
                strategy_score = round(min((vol_mult * 2) + abs(price_chg), 10.0), 1)

                # Signal Logic & Priority Sorting
                if symbol == INDEX_TICKER:
                    action = "BENCHMARK 🏛️"
                    priority = 0
                elif ltp > vwap and vol_mult >= 1.5 and vcp_signal == "YES":
                    action = "BUY CE (15M CONFIRMED) 🟢"
                    priority = 1
                elif ltp < vwap and vol_mult >= 1.5 and vcp_signal == "YES":
                    action = "BUY PE (15M CONFIRMED) 🔴"
                    priority = 1
                else:
                    action = "NO ENTRY 🚫"
                    priority = 2

                records.append({
                    'Clean Symbol': symbol.replace('.NS', ''),
                    'Action / Entry Trigger': action,
                    'Priority': priority,
                    'Strategy Score': strategy_score,
                    'Volume Spike': f"{vol_mult}x ⚡" if vol_mult >= 1.5 else f"{vol_mult}x 💧",
                    'VWAP Status': vwap_status,
                    'Vol_Raw': vol_mult,
                    'Execution Time': current_time_only
                })
            except Exception:
                continue

        df_all = pd.DataFrame(records)
        if df_all.empty:
            return pd.DataFrame()

        # SORTING: Confirmed Signals Top Par -> Score ke hisab se highest Top Par
        df_all = df_all.sort_values(by=['Priority', 'Vol_Raw'], ascending=[True, False]).reset_index(drop=True)

        # Rank Assignment (#1, #2, #3...)
        df_all['Rank'] = [f"#{i+1}" for i in range(len(df_all))]

        # Selected Clean Columns
        final_df = df_all[[
            'Rank', 
            'Clean Symbol', 
            'Action / Entry Trigger', 
            'Volume Spike', 
            'VWAP Status', 
            'Strategy Score', 
            'Execution Time'
        ]]
        
        return final_df

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

        target_tab_name = "LIVE_DASHBOARD"
        try:
            worksheet = sh.worksheet(target_tab_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=target_tab_name, rows="200", cols="10")

        headers = df.columns.tolist()
        values = [headers] + df.astype(str).values.tolist()

        worksheet.clear()
        worksheet.update('A1', values)
        print(f"✅ Successfully updated tab '{target_tab_name}'! Total Ranked Stocks: {len(df)}")

    except Exception as e:
        print(f"❌ Google Sheets Update Failed: {e}")

if __name__ == "__main__":
    df_result = fetch_stock_data()
    update_google_sheet(df_result)
