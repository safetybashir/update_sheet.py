import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 1. GOOGLE SHEETS SETTINGS & AUTHENTICATION
# ==========================================
def get_sheet_client():
    try:
        # GitHub Secrets se credentials aur sheet ID uthana
        creds_json = os.environ.get("GCP_CREDENTIALS_JSON")
        sheet_id = os.environ.get("SHEET_ID")
        
        if not creds_json or not sheet_id:
            raise ValueError("GCP_CREDENTIALS_JSON ya SHEET_ID GitHub Secrets me missing hai!")
            
        scope = ["https://google.com", "https://googleapis.com"]
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(sheet_id)
    except Exception as e:
        print(f"❌ Google Sheet Authentication Failed: {str(e)}")
        return None

# ==========================================
# 2. MASTER STOCKS LIST (152+ F&O STOCKS)
# ==========================================
STOCKS = [
    'NIFTY_50', 'TORNTPHARM', 'ASHOKLEY', 'KAYNES', 'INOXWIND', 'GAIL', 'KEI', 
    'PREMIERENE', 'CGPOWER', 'M&M', 'BSE', 'DIVISLAB', 'NYKAA', 'PHOENIXLTD', 'LUPIN'
    # Aap is list me apne baki ke saare stocks isi tarah add kar sakte hain
]

# ==========================================
# 3. LIVE CORE LOGIC & CALCULATION FUNCTION
# ==========================================
def run_master_screener():
    print("🚀 F&O Screener Master Dashboard Execution Started...")
    
    # Connect to Google Sheet
    workbook = get_sheet_client()
    if not workbook:
        return
        
    try:
        # Aisa mante hain ki aapka raw data sheet ka naam "Trading_Dashboard" hai
        # Agar aapka source tab name kuch aur hai, toh yahan badal dein
        source_sheet = workbook.worksheet("Trading_Dashboard")
        raw_data = source_sheet.get_all_records()
        df_raw = pd.DataFrame(raw_data)
        
        # Raw Data ko key-value mapping me convert karna taaki easily find ho sake
        # columns name match hone chahiye: SYMBOL, LTP, PREV_CLOSE, VOLUME, AVG_VOLUME, OI_CHG_PCT, PCR, MAX_PAIN, HIGH
        stock_data_map = {}
        if not df_raw.empty and 'SYMBOL' in df_raw.columns:
            df_raw.set_index('SYMBOL', inplace=True)
            stock_data_map = df_raw.to_dict(orient='index')
    except Exception as e:
        print(f"⚠️ Source sheet read error (Falling back to proxy calculations): {str(e)}")
        stock_data_map = {}

    processed_rows = []
    current_time_str = datetime.now().strftime("%H:%M:%S")

    for stock in STOCKS:
        try:
            # Live dictionary se mapping read karna, data na hone par proxy/default set hona
            sheet_row = stock_data_map.get(stock, {})
            
            ltp = float(sheet_row.get('LTP', 0))
            prev_close = float(sheet_row.get('PREV_CLOSE', ltp if ltp > 0 else 1))
            volume = float(sheet_row.get('VOLUME', 0))
            avg_volume = float(sheet_row.get('AVG_VOLUME', 1))
            oi_change = float(sheet_row.get('OI_CHG_PCT', 0))
            pcr = float(sheet_row.get('PCR', 1.0))
            max_pain = float(sheet_row.get('MAX_PAIN', 0))
            day_high = float(sheet_row.get('HIGH', ltp))
            
            # --- MATHEMATICAL CALCULATIONS & LOGIC ---
            price_change_pct = ((ltp - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
            vol_multiplier = volume / avg_volume if avg_volume > 0 else 1.0
            
            # 1. Volume Spike Status
            vol_status = "🔥 SPIKE" if vol_multiplier >= 2.0 else "😴 STABLE"
            
            # 2. F&O Build-up Logic
            if price_change_pct > 0.5 and oi_change > 5:
                fo_buildup = "🔥 LONG BUILDUP"
            elif price_change_pct < -0.5 and oi_change > 5:
                fo_buildup = "📉 SHORT BUILDUP"
            elif price_change_pct < -0.5 and oi_change < -2:
                fo_buildup = "📉 LONG UNWINDING"
            else:
                fo_buildup = "😴 NEUTRAL"
                
            # 3. Breakout Status & Conviction (Mark Minervini / Oliver Kell Style)
            distance_from_high = ((day_high - ltp) / ltp) * 100 if ltp > 0 else 0.0
            
            if distance_from_high <= 0.2 and vol_multiplier >= 1.5 and price_change_pct > 1.5:
                bo_status = "🔥 STRONG BREAKOUT"
                bo_trend = "🟢 UPTREND"
                conviction = "⭐ SUPER CONVICTION"
            else:
                bo_status = "No Cash Breakouts"
                bo_trend = "⏳ RANGE / CONSOLIDATION"
                conviction = "😴 NO SIGNAL"
                
            # Dynamic Targets
            sl_pct = 2.0
            target_pct = 4.0
            
            # Row compilation match to your MASTER_DASHBOARD columns
            row = {
                "SYMBOLE": stock,
                "LTP": round(ltp, 2),
                "Price % Change": f"{round(price_change_pct, 2)}%",
                "Volume Spike": vol_status,
                "OI % Change": f"{round(oi_change, 2)}%",
                "PCR Ratio": round(pcr, 2),
                "Max Pain": max_pain,
                "F&O Build-Up": fo_buildup,
                "B/O STOCKS": bo_status,
                "B/O TREND": bo_trend,
                "⭐ SUPER CONVCTION": conviction,
                "LAST UPDATED TIME": current_time_str
            }
            processed_rows.append(row)
            
        except Exception as e:
            print(f"Error processing {stock}: {str(e)}")
            continue
            
    df_output = pd.DataFrame(processed_rows)
    
    # ==========================================
    # 4. EXECUTING LIVE PUSH TO GOOGLE SHEET
    # ==========================================
    try:
        # Aapka target output tab jahan dashboard bana hai (MASTER_DASHBOARD)
        output_sheet = workbook.worksheet("MASTER_DASHBOARD")
        
        # Grid clear karke bilkul fresh structure write karna
        output_sheet.clear()
        
        # Headers + Data frames ko combine karke update karna
        set_with_dataframe_data = [df_output.columns.values.tolist()] + df_output.values.tolist()
        output_sheet.update(set_with_dataframe_data)
        print(f"🏆 MASTER_DASHBOARD successfully updated at {current_time_str}!")
        
    except Exception as e:
        print(f"❌ Failed to push data to Google Sheet: {str(e)}")

# Execution point trigger
if __name__ == "__main__":
    run_master_screener()

