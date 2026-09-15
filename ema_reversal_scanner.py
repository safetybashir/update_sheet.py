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

# --- CONFIGURATION (Sheet ID & Target Tab) ---
SPREADSHEET_ID = "1Tkd_sn6Fk6i702nTHT3rm3efgZZFcTUPNmnTUJeABm0"
UNIFIED_TAB_NAME = "EMA_COMMAND_CENTER"

STOCK_UNIVERSE = [
    # Energy, Oil & Gas, Power
    "RELIANCE", "ONGC", "BPCL", "IOC", "GAIL", "NTPC", "POWERGRID", "ATGL", "JSWENERGY", "TATAPOWER", 
    "NHPC", "SJVN", "TORNTPOWER", "NTPCGREEN", "HINDPETRO", "MRPL", "OIL", 
    "GSPL", "GUJGASLTD", "IGL", "PETRONET", "AEGISLOG", "COALINDIA", "MOLBIO",
    
    # IT & Software Services
    "TCS", "INFY", "HCLTECH", "TECHM", "WIPRO", "LTIM", "LTTS", "COFORGE", 
    "MPHASIS", "PERSISTENT", "OFSS", "KPITTECH", "CYIENT", "ZENSARTECH", "SONATSOFTW",
    
    # Automobile & Auto Ancillaries
    "TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "TVSMOTOR", "HEROMOTOCO", 
    "EICHERMOT", "ASHOKLEY", "BHARATFORG", "BALKRISIND", "APOLLOTYRE", "CEATLTD", 
    "MRF", "BOSCHLTD", "TIINDIA", "ENDURANCE", "UNOMINDA", "MOTHERSON", "FORCEMOT",
    
    # Metals, Mining & Steel (WELCORP Permanently Excluded)
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL", "SAIL", "NMDC", 
    "HINDZINC", "NATIONALUM", "JSL", "APLAPOLLO", "GPIL", "RATNAMANI",
    
    # Capital Goods, Defense & Infrastructure
    "LT", "HAL", "BEL", "SIEMENS", "ABB", "BHEL", "MAZDOCK", "COCHINSHIP", 
    "THERMAX", "BDL", "CGPOWER", "POWERINDIA", "KEI", "DIXON", "POLYCAB", 
    "ASTRAL", "SUPREMEIND", "KEC", "KPIL", "TRIVENI", "ELGIEQUIP", "TIMKEN", 
    "SKFINDIA", "SCHAEFFLER", "NCC", "NBCC", "RVNL", "IRCON", "RAILTEL", 
    
    # Pharma & Healthcare
    "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA", 
    "APOLLOHOSP", "MAXHEALTH", "GLENMARK", "ALKEM", "ABBOTINDIA", 
    "IPCALAB", "SYNGENE", "TORNTPHARM", "GLAXO", "PFIZER", "GRANULES", "AJANTPHARM", 
    "LALPATHLAB", "METROPOLIS", "FORTIS", "MEDANTA", "BIOCON",
    
    # FMCG & Consumer Durables
    "HINDUNILVR", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DABUR", "MARICO", 
    "COLPAL", "GODREJCP", "TITAN", "PAGEIND", "VOLTAS", "BLUESTARCO", "HAVELLS", 
    "CROMPTON", "WHIRLPOOL", "AMBER", "PGEL", "VBL", "DEVYANI", "JUBLFOOD",
    
    # Retail, Realty & Services
    "TRENT", "DMART", "ZOMATO", "SWIGGY", "NYKAA", "PAYTM", "POLICYBZR", "NAUKRI", 
    "DELHIVERY", "IRCTC", "INDHOTEL", "DLF", "LODHA", "GODREJPROP", "PRESTIGE", 
    "OBEROIRLTY", "SOBHA", "PHOENIXLTD", "CONCOR", "MAHLOG", "AMBUJACEM", "ACC", 
    "SHREECEM", "ULTRACEMCO", "DALBHARAT", "RAMCOCEM", "JKCEMENT",
   
    # Master, high value trading Stocks
    "NOVARTIND", "MANINDS", "INDOCO", "ESDS", "GENESYS", "VSSL", "SHAKTIPUMP", "TECHNOCRAF",    
    "ACUTAAS", "RAYMOND", "ITDC", "KROSS", "VARROC", "ELLEN", "SAMHI", "INOXINDIA", "EMIL", "MILKYMIST", 
    "ATHERENERG", "OLAELEC", "PARAGMILK", "IRB", "INDNIPPON", "EMMVEE", "TCC"
]

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
        print(f"Error fetching data for {ticker}: {e}")
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
    print(f"--- Starting Column-J Separated Scanner for {len(STOCK_UNIVERSE)} Stocks ---")
    
    swing_results = []
    intraday_results = []
    
    for stock in STOCK_UNIVERSE:
        print(f"Scanning {stock}...")
        
        # 1. Daily Timeframe Scan (Swing - Right Side)
        df_daily = fetch_data(stock, interval="1d", period="3mo")
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
        
        # 2. 15-Minute Timeframe Scan (Intraday - Left Side)
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
        
    # SORT BY CONVICTION SCORE
    intraday_results.sort(key=lambda x: x['Conviction_Score'], reverse=True)
    swing_results.sort(key=lambda x: x['Conviction_Score'], reverse=True)
        
    print(f"Scan Complete. Swing: {len(swing_results)}, Intraday: {len(intraday_results)}")
    update_google_sheet(swing_results, intraday_results)

def update_google_sheet(swing_data, intraday_data):
    try:
        client = get_gspread_client()
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        ist = pytz.timezone("Asia/Kolkata")
        current_time_str = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            ws = sheet.worksheet(UNIFIED_TAB_NAME)
        except Exception:
            ws = sheet.add_worksheet(title=UNIFIED_TAB_NAME, rows="200", cols="25")
            
        ws.clear()
        
        intra_headers = ["INTRA STOCK", "CLOSE", "RSI", "BULLISH SIG", "BEARISH SIG", "HIGH", "LOW"]
        swing_headers = ["SWING STOCK", "CLOSE", "RSI", "BULLISH SIG", "BEARISH SIG", "HIGH", "LOW"]
        
        intra_rows = []
        for item in intraday_data:
            intra_rows.append([item['Stock'], item['Close'], item['RSI'], item['Bullish_Sig'], item['Bearish_Sig'], item['Alert_High'], item['Alert_Low']])
            
        swing_rows = []
        for item in swing_data:
            swing_rows.append([item['Stock'], item['Close'], item['RSI'], item['Bullish_Sig'], item['Bearish_Sig'], item['Alert_High'], item['Alert_Low']])
            
        max_rows = max(len(intra_rows), len(swing_rows), 1)
        
        # Row 1: Title & Timestamp (Col A gets Timestamp, Left Title at Col A, Right Title starting at Col J)
        # Total columns mapped up to Col P (Index 15) to position Right Title cleanly at Column J
        title_row = [
            "⚡ HIGH-CONVICTION INTRADAY (15 MIN)", "", "", "", "", "", "", "", "", 
            "HIGH-CONVICTION SWING TRADING (DAILY) ⚡", "", "", "", "", "", ""
        ]
        # Insert Timestamp specifically into Column A cell of row 1
        title_row[0] = f"🕒 Last Updated: {current_time_str} IST | ⚡ HIGH-CONVICTION INTRADAY (15 MIN)"

        # Row 2: Headers (Intra headers A to G, Col H & I empty gap, Swing headers starting at Col J)
        gap_cols = ["", ""] # Columns H and I as blank separators
        headers_row = intra_headers + gap_cols + swing_headers

        combined_payload = [
            title_row,
            headers_row
        ]
        
        # Row 3 onwards: Data rows with blank gap in columns H and I
        for i in range(max_rows):
            i_row = intra_rows[i] if i < len(intra_rows) else ["", "", "", "", "", "", ""]
            s_row = swing_rows[i] if i < len(swing_rows) else ["", "", "", "", "", "", ""]
            combined_payload.append(i_row + gap_cols + s_row)
            
        ws.update('A1', combined_payload)
        print(f"✅ Google Sheet updated successfully with Column J separation at {current_time_str}!")
    except Exception as e:
        print(f"❌ Google Sheet Update Error: {e}")
        raise e

if __name__ == "__main__":
    run_scanner()
