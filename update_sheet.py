import os
import json
import time
import sys
import requests
from datetime import datetime
import pytz
import pandas as pd
import numpy as np
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# SECTION 1: GOOGLE SHEETS AUTH & TAB UPDATER
# ==========================================
FALLBACK_SHEET_ID = "1e9znYZTTnp3MNKn2Re9FfjtizzS5xZdZwCHp7AJZ3qg" 

def get_gspread_client():
    creds_json = os.environ.get("GOOGLE_CREDS") or os.environ.get("GCP_CREDENTIALS_JSON")
    
    if creds_json:
        creds_dict = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    elif os.path.exists("credentials.json"):
        return gspread.service_account(filename="credentials.json")
    else:
        raise FileNotFoundError("❌ 'credentials.json' file current directory mein nahi mili!")

def write_to_sheet(worksheet, data_to_write):
    """Safe writing across different gspread library versions"""
    try:
        # Compatibility handling for gspread versions
        worksheet.clear()
        worksheet.update('A1', data_to_write)
    except Exception:
        worksheet.clear()
        worksheet.update(values=data_to_write, range_name='A1')

def update_ce_tab(spreadsheet, df):
    tab_name = "NEW OI_VCP B/O DASHBOARD"
    headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "CE Action", "Trigger CE", "Change %", "Last Updated"]
    
    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            print(f"⚠️ Tab '{tab_name}' nahi mila, naya tab banaya ja raha hai...")
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="9")
            
        if not df.empty:
            df_ce = df.copy()
            df_ce["CE Action"] = "BUY CE 🚀"
            df_ce["Trigger CE"] = df_ce["LTP"].apply(lambda x: f"BUY>{round(float(x) * 1.002, 2)}")
            
            df_clean = df_ce[headers].copy().fillna("").replace([np.inf, -np.inf], "")
            for col in headers:
                df_clean[col] = df_clean[col].astype(str)

            data_to_write = [headers] + df_clean.values.tolist()
            write_to_sheet(worksheet, data_to_write)
            print(f"✅ CE Tab Updated: {tab_name} ({len(df_clean)} rows written)")
        else:
            ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
            default_row = [["NONE", "NO_BREAKOUT", "0.0", "0.0", "0.0", "NO TRADE 🚫", "N/A", "0.0", str(ist_time)]]
            write_to_sheet(worksheet, [headers] + default_row)
            print(f"⚠️ CE Tab Updated with Default State.")
            
    except Exception as e:
        print(f"❌ Failed to update CE Tab ({tab_name}): {e}")

def update_pe_tab(spreadsheet, df):
    tab_name = "LIVE_PE_DASHBOARD"
    headers = ["Symbol", "Trend", "Vol Spike", "LTP", "Score", "PE Action", "Trigger PE", "Change %", "Last Updated"]
    
    try:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            print(f"⚠️ Tab '{tab_name}' nahi mila, naya tab banaya ja raha hai...")
            worksheet = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="9")
            
        if not df.empty:
            df_pe = df.copy()
            df_pe["PE Action"] = "BUY PE 🚨"
            df_pe["Trigger PE"] = df_pe["LTP"].apply(lambda x: f"SELL<{round(float(x) * 0.998, 2)}")
            
            df_clean = df_pe[headers].copy().fillna("").replace([np.inf, -np.inf], "")
            for col in headers:
                df_clean[col] = df_clean[col].astype(str)

            data_to_write = [headers] + df_clean.values.tolist()
            write_to_sheet(worksheet, data_to_write)
            print(f"✅ PE Tab Updated: {tab_name} ({len(df_clean)} rows written)")
        else:
            ist_time = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S')
            default_row = [["NONE", "NO_BREAKOUT", "0.0", "0.0", "0.0", "NO TRADE 🚫", "N/A", "0.0", str(ist_time)]]
            write_to_sheet(worksheet, [headers] + default_row)
            print(f"⚠️ PE Tab Updated with Default State.")
            
    except Exception as e:
        print(f"❌ Failed to update PE Tab ({tab_name}): {e}")
