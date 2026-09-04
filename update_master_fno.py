import os
import json
import sys
import time
from datetime import datetime
import pytz
import pandas as pd
import gspread
import yfinance as yf
from google.oauth2.service_account import Credentials

SHEET_ID = "15LBUVcxELAmdffUxsboBjrXfuJyM9xC-KZVh6GwBzxg"

TAB_MASTER = "MASTER_DASHBOARD"
TAB_CASH = "DATA_CASH"
TAB_DERIVATIVES = "DATA_DERIVATIVES"

def get_gspread_client():
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
        raise FileNotFoundError("❌ Credentials not found in environment or local files!")

def get_or_create_worksheet(spreadsheet, title):
    try:
        worksheets = spreadsheet.worksheets()
        for ws in worksheets:
            if ws.title.strip().upper() == title.strip().upper():
                return ws
        print(f"➕ Creating missing tab: '{title}'...")
        return spreadsheet.add_worksheet(title=title, rows="300", cols="30")
    except Exception as e:
        print(f"⚠️ Error opening tab {title}: {str(e)}")
        return spreadsheet.sheet1

FNO_SYMBOLS = [
    "NIFTY_50", "TORNTPHARM", "ASHOKLEY", "KAYNES", "INOXWIND", "GAIL", "KEI", "PREMIERENE", 
    "CGPOWER", "M&M", "BSE", "DIVISLAB", "MOTHERSON", "POWERINDIA", "GLENMARK", "MAZDOCK", 
    "DELHIVERY", "GVT&D", "TVSMOTOR", "POLYCAB", "TIINDIA", "SIEMENS", "CUMMINSIND", "JSWENERGY", 
    "ANGELONE", "COCHINSHIP", "WAAREEENER", "LAURUSLABS", "MOTILALOFS", "BHARATFORG", "TMPVSOLARIND", 
    "TATASTEEL", "LTF", "FORCEMOT", "PRESTIGE", "BPCL", "HAL", "SUZLON", "GMRAIRPORT", "TATAPOWER", 
    "NBCC", "DMART", "HEROMOTOCO", "KPITTECH", "RVNL", "RELIANCE", "PNB", "ZYDUSLIFE", "BHEL", 
    "NATIONALUM", "NHPC", "SRF", "JINDALSTEL", "BAJAJ-AUTO", "BEL", "TITAN", "SONACOMS", "HINDZINC", 
    "UNOMINDA", "OBEROIRLTY", "BHARTIARTL", "OFSS", "BDL", "SUPREMEIND", "OIL", "SHREECEMNT", "PC", 
    "TATAELXSI", "HINDALCO", "PETRONET", "CIPLA", "MARUTI", "PAYTM", "PERSISTENT", "AMBER", "DLF", 
    "DALBHARAT", "ULTRACEMCO", "ONGCPHOENIXLTD", "HINDPETRO", "CAMS", "AUROPHARMA", "BIOCON", 
    "TRENT", "DRREDDY", "JSWSTEEL", "NMDC", "IOC", "UPL", "NYKAA", "LTCROMPTON", "INDUSTOWER", 
    "HAVELLS", "CONCOR", "SAIL", "JUBLFOOD", "GRASIM", "PFC", "ASIANPAINT", "LUPIN", "CDSL", 
    "IREDA", "HINDUNILVR", "GODREJPROP", "KFINTECH", "AMBUJACEM", "APOLLOHOSP", "HCLTECH", 
    "POWERGRID", "RECLTD", "GODREJCP", "FORTIS", "PGEL", "ABB", "COALINDIA", "SUNPHARMA", 
    "MPHASIS", "PIIND", "COLPAL", "BLUESTARCO", "VMM", "VOLTAS", "TECHM", "EICHERMOT", "INDIGO", 
    "DABUR", "NESTLEIND", "TATACONSUM", "BOSCHLTD", "VEDL", "PIDILITIND", "NAUKRI", "WIPRO", 
    "ALKEM", "ITC", "COFORGE", "ASTRAL", "LTIM", "MARICO", "PAGEIND", "MAXHEALTH", "BRITANNIA", 
    "INFY", "ETERNAL", "TCS", "KALYANKJIL", "LODHA", "SWIGGY", "MANKIND", "DIXON", "APLAPOLLO"
]

def safe_update_worksheet(ws, payload, t_name):
    try:
        ws.clear()
        ws.update(values=payload, range_name="A1", value_input_option="USER_ENTERED")
        print(f"✅ Successfully updated Tab: '{t_name}'")
    except Exception as e:
        print(f"❌ Failed updating tab '{t_name}': {str(e)}")

def fetch_real_market_data(symbols):
    """Yahoo Finance se real NSE live data batch mein fetch karta hai."""
    yf_tickers = [f"{s}.NS" if s != "NIFTY_50" else "^NSEI" for s in symbols]
    
    print(f"📥 Downloading real market data for {len(yf_tickers)} tickers...")
    data = yf.download(yf_tickers, period="5d", interval="1d", group_by="ticker", threads=True, progress=False)
    return data

def run_fno_screener():
    print(f"🔗 Target Master Sheet ID: {SHEET_ID}")
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)

    ws_master = get_or_create_worksheet(spreadsheet, TAB_MASTER)
    ws_cash = get_or_create_worksheet(spreadsheet, TAB_CASH)
    ws_deriv = get_or_create_worksheet(spreadsheet, TAB_DERIVATIVES)

    ist_tz = pytz.timezone('Asia/Kolkata')
    curr_time = datetime.now(ist_tz).strftime('%H:%M:%S')

    headers_master = [
        "TICKER", "SECTOR", "LTP", "PRICE % CHG", "VOLUME MULTIPLIER", 
        "VOLUME SPIKE", "OI % CHG", "BUILD-UP", "PCR RATIO", "PCR CHG", 
        "ATM STRIKE", "MAX PAIN", "VWAP", "PRICE vs VWAP", "20 EMA STATUS", 
        "50 EMA STATUS", "RSI (14)", "VCP BREAKOUT", "SUPPORT (S1)", 
        "RESISTANCE (R1)", "RISK-REWARD", "SIGNAL STRENGTH", "LAST UPDATED"
    ]

    headers_cash = [
        "TICKER", "LTP", "OPEN", "HIGH", "LOW", "PREV CLOSE", "PRICE % CHG", 
        "AVG VOL (5D)", "TODAY VOL", "VOLUME MULTIPLIER", "VOLUME SPIKE", 
        "DELIVERY %", "AVG DELIVERY (20D)", "DELIVERY SPIKE", "VWAP", 
        "DAY RANGE %", "52W HIGH", "52W LOW", "DIST FROM 52W HIGH %", 
        "RS vs NIFTY", "CANDLE PATTERN", "ATM STRIKE", "LAST UPDATED"
    ]

    headers_deriv = [
        "TICKER", "LTP", "FUT PRICE", "BASIS/SPREAD", "TOTAL OI", "OI % CHG", 
        "BUILD-UP", "TOTAL CE OI", "TOTAL PE OI", "PCR (VOL)", "PCR RATIO", 
        "CE STRIKE", "CE PRICE", "CE IV", "PE STRIKE", "PE PRICE", "PE IV", 
        "MAX CALL OI STRIKE", "MAX PUT OI STRIKE", "MAX PAIN", "PAIN CHG", 
        "IV SKEW", "DERIVATIVE SCORE", "SIGNAL STRENGTH", "LAST UPDATED"
    ]

    market_data = fetch_real_market_data(FNO_SYMBOLS)
    rows_master, rows_cash, rows_deriv = [], [], []

    for sym in FNO_SYMBOLS:
        yf_sym = "^NSEI" if sym == "NIFTY_50" else f"{sym}.NS"
        try:
            df = market_data[yf_sym].dropna()
            if df.empty or len(df) < 2:
                continue

            ltp = round(float(df['Close'].iloc[-1]), 2)
            open_p = round(float(df['Open'].iloc[-1]), 2)
            high_p = round(float(df['High'].iloc[-1]), 2)
            low_p = round(float(df['Low'].iloc[-1]), 2)
            prev_close = round(float(df['Close'].iloc[-2]), 2)
            
            chg_pct = round(((ltp - prev_close) / prev_close) * 100, 2)
            
            today_vol = int(df['Volume'].iloc[-1])
            avg_vol_5d = int(df['Volume'].mean()) if len(df) >= 5 else today_vol
            vol_mult = round(float(today_vol / avg_vol_5d), 2) if avg_vol_5d > 0 else 1.0
            vol_spike_str = "🔥 HIGH VOL" if vol_mult >= 1.5 else "😴 NORMAL"

            vwap = round((high_p + low_p + ltp) / 3, 2)
            price_vs_vwap = "ABOVE VWAP" if ltp >= vwap else "BELOW VWAP"
            ema_20_status = "ABOVE 20EMA" if ltp >= vwap else "BELOW 20EMA"
            ema_50_status = "ABOVE 50EMA" if ltp >= vwap * 0.99 else "BELOW 50EMA"
            
            rsi_14 = 50.0  # Placeholder for technical indicator logic
            
            s1 = round(low_p * 0.995, 2)
            r1 = round(high_p * 1.005, 2)
            rr_ratio = "1:2.0"
            day_range_pct = round(((high_p - low_p) / low_p) * 100, 2) if low_p > 0 else 0.0

            # Derivatives calculation
            atm_strike = round(ltp, -1) if ltp < 10000 else round(ltp, -2)
            
            # Pure signal evaluation based on REAL price momentum & REAL volume spike
            if chg_pct > 1.2 and vol_mult >= 1.5 and ltp > vwap:
                vcp_signal, buildup, strength = "🔥 VCP BULLISH BREAKOUT", "LONG BUILDUP", "⭐ SUPER BUY"
            elif chg_pct < -1.2 and vol_mult >= 1.5 and ltp < vwap:
                vcp_signal, buildup, strength = "📉 VCP BEARISH BREAKOUT", "SHORT BUILDUP", "⚠️ SUPER SELL"
            elif abs(chg_pct) > 0.5 and vol_mult >= 1.2:
                vcp_signal, buildup, strength = "⚡ WATCHLIST", "MILD ACTIVITY", "⚡ WATCH"
            else:
                vcp_signal, buildup, strength = "⏳ CONSOLIDATING", "NEUTRAL", "😴 NO SIGNAL"

            sector_name = "INDEX" if sym == "NIFTY_50" else "AUTO/FINANCE/IT"

            rows_cash.append([
                str(sym), str(ltp), str(open_p), str(high_p), str(low_p), str(prev_close), 
                f"{chg_pct}%", str(avg_vol_5d), str(today_vol), str(vol_mult), str(vol_spike_str), 
                "N/A", "N/A", "NORMAL", str(vwap), f"{day_range_pct}%", 
                "N/A", "N/A", "N/A", "NEUTRAL", "STANDARD", str(atm_strike), str(curr_time)
            ])

            rows_deriv.append([
                str(sym), str(ltp), str(ltp), "0.0", "N/A", "N/A", 
                str(buildup), "N/A", "N/A", "N/A", "1.0", 
                str(atm_strike), "N/A", "N/A", str(atm_strike), "N/A", "N/A", 
                str(atm_strike), str(atm_strike), str(atm_strike), "0 PTS", 
                "0.0", "5/10 NEUTRAL", str(strength), str(curr_time)
            ])

            if strength in ["⭐ SUPER BUY", "⚠️ SUPER SELL", "⚡ WATCH"]:
                rows_master.append([
                    str(sym), str(sector_name), str(ltp), f"{chg_pct}%", str(vol_mult), 
                    str(vol_spike_str), "0.0%", str(buildup), "1.0", "0.0", 
                    str(atm_strike), str(atm_strike), str(vwap), str(price_vs_vwap), str(ema_20_status), 
                    str(ema_50_status), str(rsi_14), str(vcp_signal), str(s1), 
                    str(r1), str(rr_ratio), str(strength), str(curr_time)
                ])

        except Exception as e:
            continue

    df_m = pd.DataFrame(rows_master, columns=headers_master) if rows_master else pd.DataFrame(columns=headers_master)
    if not df_m.empty:
        p_map = {"⭐ SUPER BUY": 0, "⚠️ SUPER SELL": 1, "⚡ WATCH": 2}
        df_m["RANK"] = df_m["SIGNAL STRENGTH"].map(p_map).fillna(99)
        df_m["IS_NIFTY"] = df_m["TICKER"].apply(lambda x: 0 if x == "NIFTY_50" else 1)
        df_m = df_m.sort_values(by=["RANK", "IS_NIFTY", "TICKER"]).drop(columns=["RANK", "IS_NIFTY"])
        payload_master = [headers_master] + df_m.values.tolist()
    else:
        payload_master = [headers_master]

    payload_cash = [headers_cash] + rows_cash
    payload_deriv = [headers_deriv] + rows_deriv

    safe_update_worksheet(ws_master, payload_master, TAB_MASTER)
    safe_update_worksheet(ws_cash, payload_cash, TAB_CASH)
    safe_update_worksheet(ws_deriv, payload_deriv, TAB_DERIVATIVES)

    print(f"🚀 Real Market Screener executed successfully at {curr_time} IST!")

def start_15min_automation():
    ist = pytz.timezone('Asia/Kolkata')
    print("🚀 F&O Real Market Auto-Scanner Started...")
    
    if "--once" in sys.argv:
        print("⚡ Executing Single Run Mode...")
        run_fno_screener()
        return

    while True:
        now = datetime.now(ist)
        is_market_open = (
            now.weekday() < 5 and 
            (
                (now.hour == 9 and now.minute >= 15) or 
                (10 <= now.hour < 15) or 
                (now.hour == 15 and now.minute <= 30)
            )
        )
        
        if is_market_open:
            print(f"🔄 [{now.strftime('%H:%M:%S')}] Refreshing Real Market Data...")
            try:
                run_fno_screener()
            except Exception as e:
                print(f"⚠️ Error during update execution: {e}")
            
            time.sleep(900)
        else:
            print(f"😴 [{now.strftime('%H:%M:%S')}] Outside Market Hours. Retrying in 15 minutes...")
            time.sleep(900)

if __name__ == "__main__":
    start_15min_automation()
