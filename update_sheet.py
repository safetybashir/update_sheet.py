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
# SECTION 2: UPDATED FnO WATCHLIST
# ==============================================================================
INDEX_TICKER = "^NSEI"

STOCKS = [
    INDEX_TICKER, "CROMPTON.NS", "HINDZINC.NS", "LODHA.NS", "BLUESTARCO.NS", "BEL.NS",
    "JUBLFOOD.NS", "PREMIERENE.NS", "GMRAIRPORT.NS", "VEDL.NS", "CONCOR.NS",
    "PIIND.NS", "EICHERMOT.NS", "TIINDIA.NS", "ETERNAL.NS", "SUNPHARMA.NS",
    "SWIGGY.NS", "BHEL.NS", "NATIONALUM.NS", "NBCC.NS", "GVT&D.NS",
    "NAUKRI.NS", "DMART.NS", "CAMS.NS", "MOTHERSON.NS", "TATASTEEL.NS",
    "NESTLEIND.NS", "INOXWIND.NS", "SOLARINDS.NS", "KEI.NS", "MARICO.NS",
    "BHARTIARTL.NS", "COFORGE.NS", "PRESTIGE.NS", "TMPV.NS", "DIVISLAB.NS",
    "TATACONSUM.NS", "VOLTAS.NS", "NMDC.NS", "JINDALSTEL.NS", "INFY.NS",
    "PAGEIND.NS", "INDUSTOWER.NS", "SUPREMEIND.NS", "HINDPETRO.NS", "POLYCAB.NS",
    "KFINTECH.NS", "MAXHEALTH.NS", "SUZLON.NS", "NYKAA.NS", "OFSS.NS",
    "M&M.NS", "PERSISTENT.NS", "RADICO.NS", "KAYNES.NS", "ZYDUSLIFE.NS",
    "DLF.NS", "PGEL.NS", "TATAELXSI.NS", "IREDA.NS", "RECLTD.NS",
    "TATAPOWER.NS", "HCLTECH.NS", "DIXON.NS", "LTF.NS", "LUPIN.NS",
    "MPHASIS.NS", "ONGC.NS", "AUROPHARMA.NS", "GLENMARK.NS", "JSWENERGY.NS",
    "SRF.NS", "MOTILALOFS.NS", "RELIANCE.NS", "APLAPOLLO.NS", "NAM-INDIA.NS",
    "UNOMINDA.NS", "POWERINDIA.NS", "COALINDIA.NS", "DABUR.NS", "IRFC.NS",
    "OBEROIRLTY.NS", "PHOENIXLTD.NS", "TORNTPHARM.NS", "ALKEM.NS", "AMBER.NS",
    "ANGELONE.NS", "ASTRAL.NS", "BDL.NS", "BIOCON.NS", "BPCL.NS",
    "CDSL.NS", "CGPOWER.NS", "DALBHARAT.NS", "DELHIVERY.NS", "FORCEMOT.NS",
    "GODREJPROP.NS", "HINDALCO.NS", "HINDUNILVR.NS", "KALYANKJIL.NS", "KPITTECH.NS",
    "LAURUSLABS.NS", "LT.NS", "MANKIND.NS", "MARUTI.NS", "MAZDOCK.NS",
    "RVNL.NS", "SIEMENS.NS", "TECHM.NS", "TITAN.NS", "TRENT.NS",
    "VMM.NS", "TVSMOTOR.NS", "PAYTM.NS", "SHREECEM.NS", "BAJAJ-AUTO.NS",
    "ABB.NS", "DRREDDY.NS", "POWERGRID.NS", "WAAREEENER.NS", "APOLLOHOSP.NS",
    "COLPAL.NS", "JSWSTEEL.NS", "GAIL.NS", "UPL.NS", "FORTIS.NS",
    "ASIANPAINT.NS", "INDIGO.NS", "HYUNDAI.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "HAVELLS.NS", "SONACOMS.NS", "AMBUJACEM.NS", "BOSCHLTD.NS", "HAL.NS",
    "COCHINSHIP.NS", "GODREJCP.NS", "HEROMOTOCO.NS", "IOC.NS", "CIPLA.NS",
    "TCS.NS", "ASHOKLEY.NS", "BRITANNIA.NS", "BHARATFORG.NS", "PETRONET.NS",
    "GRASIM.NS", "PIDILITIND.NS", "LTM.NS", "BSE.NS", "CUMMINSIND.NS"
]

# ==============================================================================
# SECTION 3: DATA PROCESSOR (DYNAMIC HIGH-VALUE BUFFERS + REVERSALS)
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

                ema21 = df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
                
                price_chg = round(((ltp - open_p) / open_p) * 100, 2)
                vol_mult = round(volume / avg_vol, 2) if avg_vol > 0 else 1.0
                vol_display = f"{vol_mult}x ⚡" if vol_mult >= 1.0 else f"{vol_mult}x 💧"
                clean_sym = symbol.replace('.NS', '').replace('^NSEI', 'NIFTY 50')

                # DISTANCE & RISK FILTERS
                dist_ema21_pct = round(((ltp - ema21) / ema21) * 100, 2)
                dist_vwap_pct = round(((ltp - vwap) / vwap) * 100, 2)

                has_valid_ce_buffer = dist_vwap_pct >= 0.12
                has_valid_pe_buffer = dist_vwap_pct <= -0.12

                # Dynamic Distance Limit for High Price Stocks (like POWERINDIA, SOLARINDS)
                max_dist_limit = 2.8 if ltp > 3000 else 1.8
                max_chg_limit = 3.8 if ltp > 3000 else 2.8

                is_extended_ce = dist_ema21_pct > max_dist_limit or price_chg > max_chg_limit
                is_sweet_ce = (0.10 <= dist_ema21_pct <= (max_dist_limit - 0.6)) and has_valid_ce_buffer

                is_extended_pe = dist_ema21_pct < -max_dist_limit or price_chg < -max_chg_limit
                is_sweet_pe = (-(max_dist_limit - 0.6) <= dist_ema21_pct <= -0.10) and has_valid_pe_buffer

                # Dynamic Trend
                if ltp > ema21 and price_chg > 0.05:
                    trend = "🟢 UPTREND"
                elif ltp < ema21 and price_chg < -0.05:
                    trend = "🔴 DOWNTREND"
                else:
                    trend = "🟡 SIDEWAYS"

                # --------------------------------------------------------------
                # CE DASHBOARD LOGIC (Includes Bottom Reversal / Breakdown Fail)
                # --------------------------------------------------------------
                ce_score = round(min((vol_mult * 2.5) + (max(0, price_chg) * 1.5), 10.0), 1)
                
                # Reversal Check (Breakdown Fail)
                is_reversal_ce = dist_ema21_pct < -1.5 and ltp > vwap and price_chg > 0.0

                if is_sweet_ce:
                    ce_score = min(10.0, ce_score + 2.0)
                elif is_reversal_ce:
                    ce_score = min(10.0, ce_score + 1.5)
                elif is_extended_ce or not has_valid_ce_buffer:
                    ce_score = max(0.0, ce_score - 3.0)

                risk_ce = max(ltp * 0.0015, abs(ltp - vwap))
                target1_ce = round(ltp + (risk_ce * 1.5), 1)
                sl_ce = round(ltp - risk_ce, 1)

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
                    ce_plan = f"BUY > {round(ltp, 1)} | T1: {target1_ce} (SL: {sl_ce})"
                    ce_priority = 1
                elif is_reversal_ce and vol_mult >= 1.0:
                    ce_action = "REVERSAL CE 🟢 (B/D FAIL)"
                    ce_plan = f"BUY > {round(ltp, 1)} | T1: {round(ema21, 1)} (SL: {sl_ce})"
                    ce_priority = 1
                elif trend == "🟢 UPTREND" and ltp > vwap and price_chg > 0.15 and not is_extended_ce:
                    if not has_valid_ce_buffer:
                        ce_action = "WATCH CE 👀"
                        ce_plan = "FLAT RANGE / SL TOO TIGHT"
                        ce_priority = 3
                    elif vol_mult >= 1.0:
                        ce_action = "BUY CE NOW 🟢"
                        ce_plan = f"BUY > {round(ltp, 1)} | T1: {target1_ce} (SL: {sl_ce})"
                        ce_priority = 2
                    else:
                        ce_action = "WATCH CE 👀"
                        ce_plan = "WAIT FOR VOL SPIKE"
                        ce_priority = 3
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
                    'CE Strength Score': round(float(ce_score), 1),
                    'Priority': ce_priority,
                    'Vol_Raw': vol_mult,
                    'Execution Time': current_time_only
                })

                # --------------------------------------------------------------
                # PE DASHBOARD LOGIC (Includes Top Reversal / Breakout Fail)
                # --------------------------------------------------------------
                pe_score = round(min((vol_mult * 2.5) + (abs(min(0, price_chg)) * 1.5), 10.0), 1)

                # Reversal Check (Breakout Fail)
                is_reversal_pe = dist_ema21_pct > 1.5 and ltp < vwap and price_chg < 0.0

                if is_sweet_pe:
                    pe_score = min(10.0, pe_score + 2.0)
                elif is_reversal_pe:
                    pe_score = min(10.0, pe_score + 1.5)
                elif is_extended_pe or not has_valid_pe_buffer:
                    pe_score = max(0.0, pe_score - 3.0)

                risk_pe = max(ltp * 0.0015, abs(vwap - ltp))
                target1_pe = round(ltp - (risk_pe * 1.5), 1)
                sl_pe = round(ltp + risk_pe, 1)

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
                    pe_plan = f"BUY < {round(ltp, 1)} | T1: {target1_pe} (SL: {sl_pe})"
                    pe_priority = 1
                elif is_reversal_pe and vol_mult >= 1.0:
                    pe_action = "REVERSAL PE 🔴 (B/O FAIL)"
                    pe_plan = f"BUY < {round(ltp, 1)} | T1: {round(ema21, 1)} (SL: {sl_pe})"
                    pe_priority = 1
                elif trend == "🔴 DOWNTREND" and ltp < vwap and price_chg < -0.15 and not is_extended_pe:
                    if not has_valid_pe_buffer:
                        pe_action = "WATCH PE 👀"
                        pe_plan = "FLAT RANGE / SL TOO TIGHT"
                        pe_priority = 3
                    elif vol_mult >= 1.0:
                        pe_action = "BUY PE NOW 🔴"
                        pe_plan = f"BUY < {round(ltp, 1)} | T1: {target1_pe} (SL: {sl_pe})"
                        pe_priority = 2
                    else:
                        pe_action = "WATCH PE 👀"
                        pe_plan = "WAIT FOR VOL SPIKE"
                        pe_priority = 3
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
                    'PE Strength Score': round(float(pe_score), 1),
                    'Priority': pe_priority,
                    'Vol_Raw': vol_mult,
                    'Execution Time': current_time_only
                })

            except Exception:
                continue

        # Sorting CE
        df_ce = pd.DataFrame(ce_records)
        if not df_ce.empty:
            df_ce['CE Strength Score'] = df_ce['CE Strength Score'].apply(lambda x: round(float(x), 1))
            df_ce = df_ce.sort_values(by=['Priority', 'CE Strength Score', 'Vol_Raw'], ascending=[True, False, False]).reset_index(drop=True)
            df_ce['Rank'] = [f"#{i+1}" for i in range(len(df_ce))]
            df_ce = df_ce[['Rank', 'Trend', 'Clean Symbol', 'LTP', 'Action / Entry Trigger', 'CE Entry Plan', 'Volume Spike', 'CE Strength Score', 'Execution Time']]

        # Sorting PE
        df_pe = pd.DataFrame(pe_records)
        if not df_pe.empty:
            df_pe['PE Strength Score'] = df_pe['PE Strength Score'].apply(lambda x: round(float(x), 1))
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
            
            # 1. Update CE Raw Data Tab
            update_tab(sh, df_ce, "LIVE_CE_DASHBOARD")
            
            # 2. Update PE Raw Data Tab
            update_tab(sh, df_pe, "LIVE_PE_DASHBOARD")
            
            # NOTE: "NEW OI_VCP B/O DASHBOARD" tab is excluded from Python overwrite 
            # so that custom Google Sheet formulas (=FILTER) remain intact!
            
        except Exception as e:
            print(f"❌ Connection Error: {e}")
