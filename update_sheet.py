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
# SECTION 2: WATCHLIST
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
# SECTION 3: SMART SELECTION DATA PROCESSOR
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

                ema20 = df['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                
                price_chg = round(((ltp - open_p) / open_p) * 100, 2)
                vol_mult = round(volume / avg_vol, 2) if avg_vol > 0 else 1.0
                vol_display = f"{vol_mult}x ⚡" if vol_mult >= 1.0 else f"{vol_mult}x 💧"
                clean_sym = symbol.replace('.NS', '').replace('^NSEI', 'NIFTY 50')

                # DISTANCE FILTERS (SMART SELECTION ENGINE)
                dist_ema20_pct = round(((ltp - ema20) / ema20) * 100, 2)
                dist_vwap_pct = round(((ltp - vwap) / vwap) * 100, 2)

                is_extended_ce = dist_ema20_pct > 1.8 or price_chg > 2.8
                is_sweet_ce = (0.05 <= dist_ema20_pct <= 1.2) and (ltp > vwap)

                is_extended_pe = dist_ema20_pct < -1.8 or price_chg < -2.8
                is_sweet_pe = (-1.2 <= dist_ema20_pct <= -0.05) and (ltp < vwap)

                # Trend Alignment
                if ltp > ema20 and price_chg > 0.05:
                    trend = "🟢 UPTREND"
                elif ltp < ema20 and price_chg < -0.05:
                    trend = "🔴 DOWNTREND"
                else:
                    trend = "🟡 SIDEWAYS"

                # --------------------------------------------------------------
                # CE DASHBOARD LOGIC
                # --------------------------------------------------------------
                ce_score = round(min((vol_mult * 2.5) + (max(0, price_chg) * 1.5), 10.0), 1)
                if is_sweet_ce:
                    ce_score = min(10.0, ce_score + 2.0)
                elif is_extended_ce:
                    ce_score = max(0.0, ce_score - 3.0)

                if symbol == INDEX_TICKER:
                    ce_priority = 0
                    if trend == "🟢 UPTREND":
                        ce_action = "BUY CE NOW 🟢"
                        ce_plan = f"BUY > {round(ltp, 1)} (SL: {round(vwap, 1)})"
                    elif trend == "🔴 DOWNTREND":
                        ce_action = "🔴 DOWNTREND"
                        ce_plan = "NO CE SETUP 🚫"
                    else:
                        ce_action = "🟡 SIDEWAYS"
                        ce_plan = "NO TRADE 🚫"
                elif trend == "🟢 UPTREND" and is_sweet_ce and vol_mult >= 1.2:
                    ce_action = "BUY CE (SWEET SPOT) 🟢"
                    ce_plan = f"BUY > {round(ltp, 1)} | T1: {round(ltp + (ltp-vwap)*1.5, 1)} (SL: {round(vwap, 1)})"
                    ce_priority = 1
                elif trend == "🟢 UPTREND" and ltp > vwap and price_chg > 0.15 and not is_extended_ce:
                    ce_action = "BUY CE NOW 🟢" if vol_mult >= 1.0 else "WATCH CE 👀"
                    ce_plan = f"BUY > {round(ltp, 1)} (SL: {round(vwap, 1)})" if vol_mult >= 1.0 else "WAIT FOR VOL SPIKE"
                    ce_priority = 2 if vol_mult >= 1.0 else 3
                elif is_extended_ce:
                    ce_action = "EXTENDED TOP ⚠️"
                    ce_plan = "FOMO HIGH / WAIT PULLBACK"
                    ce_priority = 4
                else:
                    ce_action = "NO CE SETUP 🚫"
                    ce_plan = "NO UPTREND"
                    ce_priority = 5

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
                # PE DASHBOARD LOGIC
                # --------------------------------------------------------------
                pe_score = round(min((vol_mult * 2.5) + (abs(min(0, price_chg)) * 1.5), 10.0), 1)
                if is_sweet_pe:
                    pe_score = min(10.0, pe_score + 2.0)
                elif is_extended_pe:
                    pe_score = max(0.0, pe_score - 3.0)

                if symbol == INDEX_TICKER:
                    pe_priority = 0
                    if trend == "🔴 DOWNTREND":
                        pe_action = "BUY PE NOW 🔴"
                        pe_plan = f"BUY < {round(ltp, 1)} (SL: {round(vwap, 1)})"
                    elif trend == "🟢 UPTREND":
                        pe_action = "🟢 UPTREND"
                        pe_plan = "NO PE SETUP 🚫"
                    else:
                        pe_action = "🟡 SIDEWAYS"
                        pe_plan = "NO TRADE 🚫"
                elif trend == "🔴 DOWNTREND" and is_sweet_pe and vol_mult >= 1.2:
                    pe_action = "BUY PE (SWEET SPOT) 🔴"
                    pe_plan = f"BUY < {round(ltp, 1)} | T1: {round(ltp - (vwap-ltp)*1.5, 1)} (SL: {round(vwap, 1)})"
                    pe_priority = 1
                elif trend == "🔴 DOWNTREND" and ltp < vwap and price_chg < -0.15 and not is_extended_pe:
                    pe_action = "BUY PE NOW 🔴" if vol_mult >= 1.0 else "WATCH PE 👀"
                    pe_plan = f"BUY < {round(ltp, 1)} (SL: {round(vwap, 1)})" if vol_mult >= 1.0 else "WAIT FOR VOL SPIKE"
                    pe_priority = 2 if vol_mult >= 1.0 else 3
                elif is_extended_pe:
                    pe_action = "EXTENDED BOTTOM ⚠️"
                    pe_plan = "OVERBOUGHT / WAIT PULLBACK"
                    pe_priority = 4
                else:
                    pe_action = "NO PE SETUP 🚫"
                    pe_plan = "NO DOWNTREND"
                    pe_priority = 5

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

        # Sorting CE
        df_ce = pd.DataFrame(ce_records)
        if not df_ce.empty:
            df_ce = df_ce.sort_values(by=['Priority', 'CE Strength Score', 'Vol_Raw'], ascending=[True, False, False]).reset_index(drop=True)
            df_ce['Rank'] = [f"#{i+1}" for i in range(len(df_ce))]
            df_ce = df_ce[['Rank', 'Trend', 'Clean Symbol', 'LTP', 'Action / Entry Trigger', 'CE Entry Plan', 'Volume Spike', 'CE Strength Score', 'Execution Time']]

        # Sorting PE
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
        return
    try:
        try:
            worksheet = sh.worksheet(target_tab_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=target_tab_name, rows="200", cols="10")

        headers = df.columns.tolist()
        values = [headers] + df.astype(str).values.tolist()

        worksheet.clear()
        worksheet.update('A1', values)
        print(f"✅ Successfully updated '{target_tab_name}'! Total Rows: {len(df)}")
    except Exception as e:
        print(f"❌ Update Failed for '{target_tab_name}': {e}")

# ==============================================================================
# SECTION 5: MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    df_ce, df_pe = fetch_and_process_data()

    sheet_id = os.environ.get("SHEET_ID")
    if sheet_id:
        try:
            gc = get_gspread_client()
            sh = gc.open_by_key(sheet_id)
            update_tab(sh, df_ce, "LIVE_CE_DASHBOARD")
            update_tab(sh, df_pe, "LIVE_PE_DASHBOARD")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
