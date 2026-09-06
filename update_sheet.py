import os
import json
import warnings
import pandas as pd
import numpy as np
import yfinance as yf
import gspread

warnings.filterwarnings("ignore")

# 🎯 TARGET MASTER SPREADSHEET ID
SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg"
BULLISH_TAB_NAME = "LIVE_BULLISH_CASH_DASHBOARD"

# ==========================================
# 📌 CASH SEGMENT WATCHLIST (MUST BE ABOVE FUNCTIONS)
# ==========================================
CASH_STOCKS = [
    "ULTRACEMCO", "BSE", "KAYNES", "TORNTPHARM", "ASHOKLEY", "INOXWIND", "GAIL", "KEI", 
    "CGPOWER", "M&M", "DIVISLAB", "MOTHERSON", "GLENMARK", "MAZDOCK", "DELHIVERY",
    "TVSMOTOR", "POLYCAB", "SIEMENS", "CUMMINSIND", "JSWENERGY", "ANGELONE", "COCHINSHIP", 
    "LAURUSLABS", "MOTILALOFS", "BHARATFORG", "TATASTEEL", "LTF", "PRESTIGE", "HAL", 
    "SUZLON", "TATAPOWER", "DMART", "RVNL", "RELIANCE", "BHEL", "NHPC", "JINDALSTEL", 
    "BEL", "TITAN", "OBEROIRLTY", "BHARTIARTL", "TATAELXSI", "HINDALCO", "CIPLA", 
    "MARUTI", "ZOMATO", "TRENT", "DRREDDY", "JSWSTEEL", "SAIL", "PFC", "RECLTD", "ITC"
]

def get_gspread_client():
    creds_json = os.environ.get("GCP_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDS")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    if creds_json:
        creds_dict = json.loads(creds_json)
        return gspread.service_account_from_dict(creds_dict, scopes=scopes)
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json", scopes=scopes)
    else:
        raise FileNotFoundError("❌ Credentials not found in Environment Secrets or local credentials.json!")

def analyze_stocks():
    print("⏳ Fetching Real Market Data (Last 60 Days) to analyze continuous uptrend...")
    tickers = [f"{sym}.NS" for sym in CASH_STOCKS]
    # Baaki ka function code...
