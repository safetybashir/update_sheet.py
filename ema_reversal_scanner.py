import os
import json
import time
from datetime import datetime
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION (Sheet ID & Target Tabs) ---
SPREADSHEET_ID = "1Tkd_sn6Fk6i702nTHT3rm3efgZZFcTUPNmnTUJeABm0"
UNIFIED_TAB_NAME = "EMA_COMMAND_CENTER"
MOOD_TAB_NAME = "MARKET_MOOD_AND_SECTORS"

# Sector Mapping for Market Breadth & Opportunity Tracking
SECTOR_MAP = {
    "Energy, Oil & Gas, Power": ["RELIANCE", "ONGC", "BPCL", "IOC", "GAIL", "NTPC", "POWERGRID", "ATGL", "JSWENERGY", "TATAPOWER", "NHPC", "SJVN", "TORNTPOWER", "HINDPETRO", "MRPL", "OIL", "GSPL", "IGL", "PETRONET", "COALINDIA"],
    "IT & Software": ["TCS", "INFY", "HCLTECH", "TECHM", "WIPRO", "LTIM", "LTTS", "COFORGE", "MPHASIS", "PERSISTENT", "OFSS", "KPITTECH", "CYIENT"],
    "Automobile & Ancillaries": ["TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "TVSMOTOR", "HEROMOTOCO", "EICHERMOT", "ASHOKLEY", "BHARATFORG", "BALKRISIND", "APOLLOTYRE", "MRF"],
    "Metals & Mining": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL", "SAIL", "NMDC", "HINDZINC", "NATIONALUM", "JSL", "APLAPOLLO"],
    "Capital Goods & Defense": ["LT", "HAL", "BEL", "SIEMENS", "ABB", "BHEL", "MAZDOCK", "COCHINSHIP", "DIXON", "POLYCAB", "ASTRAL"],
    "Pharma & Healthcare": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA", "APOLLOHOSP", "MAXHEALTH", "GLENMARK", "ALKEM", "TORNTPHARM"],
    "FMCG & Consumer": ["HINDUNILVR", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DABUR", "MARICO", "COLPAL", "GODREJCP", "TITAN", "VOLTAS", "HAVELLS"],
    "Retail, Realty & Services": ["TRENT", "DMART", "ZOMATO", "SWIGGY", "NYKAA", "PAYTM", "IRCTC", "INDHOTEL", "DLF", "LODHA", "GODREJPROP", "AMBUJACEM", "ULTRACEMCO"]
}

STOCK_UNIVERSE = []
for sec_stocks in SECTOR_MAP.values():
    for s in sec_stocks:
        if s not in STOCK_UNIVERSE:
            STOCK_UNIVERSE.append(s)

RSI_PERIOD = 14
EMA_PERIOD = 5

def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    if "GCP_CREDENTIALS_JSON" in os.environ and os.environ["GCP_CREDENTIALS_JSON"].strip():
        raw_json = os.environ["GCP_CREDENTIALS_JSON"].strip()
        try:
            creds_dict = json.loads(raw_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(f"❌ Error in 'GCP_CREDENTIALS_JSON' secret: {e}")
    elif os.path.exists("credentials.json"):
        try:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
            return gspread.authorize(creds)
        except Exception as e:
            raise ValueError(f"❌ Invalid local 'credentials.json': {e}")
    else:
        raise FileNotFoundError("Neither 'GCP_CREDENTIALS_JSON' secret nor 'credentials.json' found.")

def fetch_data(ticker, interval, period):
    try:
        df = yf.download(ticker + ".NS", period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df
    except Exception as e:
        return None

def calculate_indicators(df):
    if df is None or len(df) < 20:
        return None
    
    df['EMA_5'] = df['Close'].ewm(span=EMA_PERIOD, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['Bullish_Alert'] = (df['Low'] > df['EMA_5']) & (df['Close'] > df['Open'])
    df['Bearish_Alert'] = (df['High'] < df['EMA_5']) & (df['Close'] < df['Open'])
    
    return df

def run_scanner():
    print(f"--- Starting Audited Market Mood & Sector Scanner for {len(STOCK_UNIVERSE)} Stocks ---")
    
    swing_results = []
    intraday_results = []
    stock_metrics = {}
    
    for stock in STOCK_UNIVERSE:
        print(f"Scanning {stock}...")
        
        df_daily = fetch_data(stock, interval="1d", period="3mo")
        if df_daily is not None and not df_daily.empty:
            close_price = float(df_daily['Close'].iloc[-1])
            prev_close = float(df_daily['Close'].iloc[-2]) if len(df_daily) > 1 else close_price
            pct_change = round(((close_price - prev_close) / prev_close) * 100, 2)
            
            stock_metrics[stock] = {
                'pct_change': pct_change,
                'is_advance': pct_change >= 0
            }
            
        df_daily = calculate_indicators(df_daily)
        if df_daily is not None and not df_daily.empty:
            latest_daily = df_daily.iloc[-1]
            if latest_daily['Bullish_Alert'] or latest_daily['Bearish_Alert']:
                is_bullish = latest_daily['Bullish_Alert']
                rsi_val = float(latest_daily['RSI'])
                swing_results.append({
                    'Stock': stock,
                    'Close': round(float(latest_daily['Close']), 2),
                    'RSI': round(rsi_val, 2),
                    'Bullish_Sig': '🟢 Bullish Reversal' if is_bullish else '',
                    'Bearish_Sig': '🔴 Bearish Reversal' if not is_bullish else '',
                    'Alert_High': round(float(latest_daily['High']), 2),
                    'Alert_Low': round(float(latest_daily['Low']), 2),
                    'Conviction_Score': abs(rsi_val - 50)
                })
        
        df_15m = fetch_data(stock, interval="15m", period="5d")
        df_15m = calculate_indicators(df_15m)
        if df_15m is not None and not df_15m.empty:
            latest_15m = df_15m.iloc[-1]
            if latest_15m['Bullish_Alert'] or latest_15m['Bearish_Alert']:
                is_bullish_15 = latest_15m['Bullish_Alert']
                rsi_val_15 = float(latest_15m['RSI'])
                intraday_results.append({
                    'Stock': stock,
                    'Close': round(float(latest_15m['Close']), 2),
                    'RSI': round(rsi_val_15, 2),
                    'Bullish_Sig': '🟢 Bullish Reversal' if is_bullish_15 else '',
                    'Bearish_Sig': '🔴 Bearish Reversal' if not is_bullish_15 else '',
                    'Alert_High': round(float(latest_15m['High']), 2),
                    'Alert_Low': round(float(latest_15m['Low']), 2),
                    'Conviction_Score': abs(rsi_val_15 - 50)
                })
                
        time.sleep(0.2)
        
    intraday_results.sort(key=lambda x: x['Conviction_Score'], reverse=True)
    swing_results.sort(key=lambda x: x['Conviction_Score'], reverse=True)
        
    print(f"Scan Complete. Updating Google Sheets cleanly...")
    update_google_sheets(swing_results, intraday_results, stock_metrics)

def update_google_sheets(swing_data, intraday_data, stock_metrics):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        ist = pytz.timezone("Asia/Kolkata")
        current_time_str = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
        
        # ==========================================
        # TAB 1: EMA_COMMAND_CENTER
        # ==========================================
        ws1 = sheet.worksheet(UNIFIED_TAB_NAME) if len(sheet.worksheets()) > 0 else sheet.add_worksheet(title=UNIFIED_TAB_NAME, rows="200", cols="25")
        ws1.clear()
        
        intra_headers = ["INTRA STOCK", "CLOSE", "RSI", "BULLISH SIG", "BEARISH SIG", "HIGH", "LOW"]
        swing_headers = ["SWING STOCK", "CLOSE", "RSI", "BULLISH SIG", "BEARISH SIG", "HIGH", "LOW"]
        
        intra_rows = [[item['Stock'], item['Close'], item['RSI'], item['Bullish_Sig'], item['Bearish_Sig'], item['Alert_High'], item['Alert_Low']] for item in intraday_data]
        swing_rows = [[item['Stock'], item['Close'], item['RSI'], item['Bullish_Sig'], item['Bearish_Sig'], item['Alert_High'], item['Alert_Low']] for item in swing_data]
        
        max_rows = max(len(intra_rows), len(swing_rows), 1)
        
        row_1 = [f"🕒 Last Updated: {current_time_str} IST"]
        gap_cols = ["", ""]
        row_2 = ["⚡ HIGH-CONVICTION INTRADAY (15 MIN)"] + [""] * 6 + gap_cols + ["HIGH-CONVICTION SWING TRADING (DAILY) ⚡"]
        headers_row = intra_headers + gap_cols + swing_headers

        payload_tab1 = [row_1, row_2, headers_row]
        for i in range(max_rows):
            i_row = intra_rows[i] if i < len(intra_rows) else ["", "", "", "", "", "", ""]
            s_row = swing_rows[i] if i < len(swing_rows) else ["", "", "", "", "", "", ""]
            payload_tab1.append(i_row + gap_cols + s_row)
            
        ws1.update(range_name='A1', values=payload_tab1)
        print("✅ Tab 1 Updated Cleanly.")

        # ========================================================
        # TAB 2: MARKET_MOOD_AND_SECTORS (Clean, No Extra Columns)
        # ========================================================
        try:
            ws2 = sheet.worksheet(MOOD_TAB_NAME)
        except Exception:
            ws2 = sheet.add_worksheet(title=MOOD_TAB_NAME, rows="100", cols="10")
            
        ws2.clear()

        total_stocks = len(stock_metrics)
        advances = sum(1 for m in stock_metrics.values() if m['is_advance'])
        declines = total_stocks - advances
        ad_ratio = round(advances / declines, 2) if declines > 0 else float(advances)
        
        if ad_ratio > 1.2:
            market_mood = "🟢 BULLISH (Buyers in Control)"
        elif ad_ratio < 0.8:
            market_mood = "🔴 BEARISH (Sellers in Control)"
        else:
            market_mood = "🟡 SIDEWAYS / CONSOLIDATION"

        # Strictly 6 columns wide to avoid extra blank columns
        payload_tab2 = [
            [f"🕒 Market Pulse & Breadth Report | Last Updated: {current_time_str} IST"],
            [""],
            ["📊 MARKET MOOD SUMMARY"],
            ["Overall Market Mood", market_mood],
            ["Total Stocks Scanned", total_stocks],
            ["Total Advances (🟢)", advances],
            ["Total Declines (🔴)", declines],
            ["Advance / Decline Ratio", ad_ratio],
            [""],
            ["📈 SECTOR OPPORTUNITY HEATMAP (F&O & Cash Trading)"],
            ["Sector Name", "Avg % Change", "Advances", "Declines", "Sector Momentum", "Action & Cash Opportunity"]
        ]

        for sector_name, tickers in SECTOR_MAP.items():
            sec_pcts = [stock_metrics[t]['pct_change'] for t in tickers if t in stock_metrics]
            sec_adv = sum(1 for t in tickers if t in stock_metrics and stock_metrics[t]['is_advance'])
            sec_dec = len(sec_pcts) - sec_adv
            avg_pct = round(sum(sec_pcts) / len(sec_pcts), 2) if sec_pcts else 0.0
            
            if avg_pct >= 0.5:
                momentum = "🔥 Strong Bullish Leader"
                opportunity = "F&O: Long/Call | Cash: Swing Delivery Buy 🟢"
            elif avg_pct <= -0.5:
                momentum = "💧 Heavy Laggard / Weak"
                opportunity = "F&O: Short/Put | Cash: Avoid / Short Build 🔴"
            else:
                momentum = "⚖️ Neutral / Rangebound"
                opportunity = "F&O: Avoid | Cash: Accumulate Dips Selectively ⏳"
                
            payload_tab2.append([
                sector_name,
                f"{avg_pct}%",
                sec_adv,
                sec_dec,
                momentum,
                opportunity
            ])

        ws2.update(range_name='A1', values=payload_tab2)
        print("✅ Tab 2 Updated Cleanly with Cash Trading Opportunities.")
        
    except Exception as e:
        print(f"❌ Google Sheet Update Error: {e}")
        raise e

if __name__ == "__main__":
    run_scanner()
