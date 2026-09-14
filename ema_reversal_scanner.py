import os
import time
import yaml
import pandas as pd
import numpy as np
import yfinance as yf
from google.oauth2.service_account import Credentials
import gspread

# Load Configuration from YAML
def load_config():
    with open("ema_config.yaml", "r") as file:
        return yaml.safe_load(file)

config = load_config()

def fetch_data(ticker, interval, period):
    """
    Yahoo Finance se OHLCV data fetch karne ke liye function.
    Intervals: '1d' (Daily ke liye), '15m' (15-Min ke liye)
    """
    try:
        df = yf.download(ticker + ".NS", period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None

def calculate_indicators(df):
    """
    5 EMA aur RSI calculate karna, aur Alert Candle (Separation) logic check karna.
    """
    if df is None or len(df) < 20:
        return None
    
    # 5 EMA Calculation
    df['EMA_5'] = df['Close'].ewm(span=config['settings']['ema_period'], adjust=False).mean()
    
    # RSI Calculation (14 Period)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=config['settings']['rsi_period']).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=config['settings']['rsi_period']).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Alert Candle Logic (Separation Check)
    # Bullish Alert: Low of the candle is separated completely above 5 EMA (touch chhoda ho)
    # Bearish Alert: High of the candle is separated completely below 5 EMA
    df['Bullish_Alert'] = (df['Low'] > df['EMA_5']) & (df['Close'] > df['Open'])
    df['Bearish_Alert'] = (df['High'] < df['EMA_5']) & (df['Close'] < df['Open'])
    
    return df

def run_scanner():
    print("--- Starting 5 EMA + RSI Reversal Scanner ---")
    universe = config['target_universe']
    
    swing_results = []
    intraday_results = []
    
    for stock in universe:
        print(f"Scanning {stock}...")
        
        # 1. Daily Timeframe Scan (Swing - Daily Chart)
        df_daily = fetch_data(stock, interval="1d", period="3mo")
        df_daily = calculate_indicators(df_daily)
        if df_daily is not None and not df_daily.empty:
            latest_daily = df_daily.iloc[-1]
            if latest_daily['Bullish_Alert'] or latest_daily['Bearish_Alert']:
                swing_results.append({
                    'Stock': stock,
                    'Timeframe': 'Daily',
                    'Close': round(float(latest_daily['Close']), 2),
                    'RSI': round(float(latest_daily['RSI']), 2),
                    'Signal': 'Bullish Reversal' if latest_daily['Bullish_Alert'] else 'Bearish Reversal',
                    'Alert_High': round(float(latest_daily['High']), 2),
                    'Alert_Low': round(float(latest_daily['Low']), 2)
                })
        
        # 2. 15-Minute Timeframe Scan (Intraday - 15Min Chart)
        df_15m = fetch_data(stock, interval="15m", period="5d")
        df_15m = calculate_indicators(df_15m)
        if df_15m is not None and not df_15m.empty:
            latest_15m = df_15m.iloc[-1]
            if latest_15m['Bullish_Alert'] or latest_15m['Bearish_Alert']:
                intraday_results.append({
                    'Stock': stock,
                    'Timeframe': '15Min',
                    'Close': round(float(latest_15m['Close']), 2),
                    'RSI': round(float(latest_15m['RSI']), 2),
                    'Signal': 'Bullish Reversal' if latest_15m['Bullish_Alert'] else 'Bearish Reversal',
                    'Alert_High': round(float(latest_15m['High']), 2),
                    'Alert_Low': round(float(latest_15m['Low']), 2)
                })
                
        time.sleep(0.5) # Rate limit handling to avoid blocking
        
    print(f"Scan Complete. Daily Setups found: {len(swing_results)}, 15M Setups found: {len(intraday_results)}")
    
    # Update Google Sheets
    update_google_sheet(swing_results, intraday_results)

def update_google_sheet(swing_data, intraday_data):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        
        # Open Google Sheet using unique Sheet ID from YAML config
        sheet = client.open_by_key(config['google_sheets']['spreadsheet_id'])
        
        # Update Daily Swing Tab
        tab_swing = sheet.worksheet(config['google_sheets']['tabs']['swing_daily'])
        tab_swing.clear()
        if swing_data:
            df_s = pd.DataFrame(swing_data)
            tab_swing.update([df_s.columns.values.tolist()] + df_s.values.tolist())
        else:
            tab_swing.update([["Status"]], [["No Daily Alert Setups Today"]])
            
        # Update 15M Intraday Tab
        tab_intra = sheet.worksheet(config['google_sheets']['tabs']['intraday_15m'])
        tab_intra.clear()
        if intraday_data:
            df_i = pd.DataFrame(intraday_data)
            tab_intra.update([df_i.columns.values.tolist()] + df_i.values.tolist())
        else:
            tab_intra.update([["Status"]], [["No 15M Alert Setups Active"]])
            
        print("Google Sheet 'Swing_Intraday_Command_Center' successfully updated using Sheet ID!")
    except Exception as e:
        print(f"Google Sheet Update Error: {e}")

if __name__ == "__main__":
    run_scanner()
