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
        creds_json = os.environ.get("GCP_CREDENTIALS_JSON")
        sheet_id = os.environ.get("1IlXpzkmGg5QAbqSd1fiVKOTPymcx8PKr")
        
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
]

# ==========================================
# 3. LIVE CORE LOGIC & CALCULATION FUNCTION
# ==========================================
def run_master_screener():
    print("🚀 F&O Screener Master Dashboard Execution Started...")
    
    workbook = get_sheet_client()
    if not workbook:
        print("❌ Workbook object nahi mila, process aborted.")
        return
        
    stock_data_map = {}
    try:
        source_sheet = workbook.worksheet("Trading_Dashboard")
        raw_data = source_sheet.get_all_records()
        df_raw = pd.DataFrame(raw_data)
        
        if not df_raw.empty:
            df_raw.columns = df_raw.columns.str.strip()
            symbol_col = 'SYMBOL' if 'SYMBOL' in df_raw.columns else ('SYMBOLE' if 'SYMBOLE' in df_raw.columns else None)
            
            if symbol_col:
                df_raw.set_index(symbol_col, inplace=True)
                stock_data_map = df_raw.to_dict(orient='index')
                print(f"🎯 Successfully loaded {len(stock_data_map)} stocks from raw data sheet!")
            else:
                print(f"⚠️ Warning: Raw sheet me 'SYMBOL' ya 'SYMBOLE' nahi mila. Columns are: {list(df_raw.columns)}")
    except Exception as e:
        print(f"⚠️ Source sheet read error (Using dynamic simulator logic): {str(e)}")

    processed_rows = []
    current_time_str = datetime.now().strftime("%H:%M:%S")

    for stock in STOCKS:
        try:
            sheet_row = stock_data_map.get(stock, {})
            
            ltp = float(sheet_row.get('LTP', np.random.uniform(100, 5000) if not stock_data_map else 0))
            prev_close = float(sheet_row.get('PREV_CLOSE', ltp * np.random.uniform(0.97, 1.03) if not stock_data_map else (ltp if ltp > 0 else 1)))
            volume = float(sheet_row.get('VOLUME', np.random.randint(10000, 500000) if not stock_data_map else 0))
            avg_volume = float(sheet_row.get('AVG_VOLUME', volume * np.random.uniform(0.5, 1.5) if not stock_data_map else 1))
            oi_change = float(sheet_row.get('OI_CHG_PCT', np.random.uniform(-10, 20) if not stock_data_map else 0))
            pcr = float(sheet_row.get('PCR', np.random.uniform(0.5, 1.5) if not stock_data_map else 1.0))
            max_pain = float(sheet_row.get('MAX_PAIN', ltp * 0.99 if not stock_data_map else 0))
            day_high = float(sheet_row.get('HIGH', max(ltp, prev_close) if not stock_data_map else ltp))
            
            price_change_pct = ((ltp - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
            vol_multiplier = volume / avg_volume if avg_volume > 0 else 1.0
            
            vol_status = "🔥 SPIKE" if vol_multiplier >= 2.0 else "😴 STABLE"
            
            if price_change_pct > 0.5 and oi_change > 5:
                fo_buildup = "🔥 LONG BUILDUP"
            elif price_change_pct < -0.5 and oi_change > 5:
                fo_buildup = "📉 SHORT BUILDUP"
            elif price_change_pct < -0.5 and oi_change < -2:
                fo_buildup = "📉 LONG UNWINDING"
            else:
                fo_buildup = "😴 NEUTRAL"
                
            distance_from_high = ((day_high - ltp) / ltp) * 100 if ltp > 0 else 0.0
            if distance_from_high <= 0.2 and vol_multiplier >= 1.5 and price_change_pct > 1.5:
                bo_status = "🔥 STRONG BREAKOUT"
                bo_trend = "🟢 UPTREND"
                conviction = "⭐ SUPER CONVICTION"
            else:
                bo_status = "No Cash Breakouts"
                bo_trend = "⏳ RANGE / CONSOLIDATION"
                conviction = "😴 NO SIGNAL"
            
            row = {
                "SYMBOLE": stock,
                "LTP": round(ltp, 2),
                "Price % Change": f"{round(price_change_pct, 2)}%",
                "Volume Spike": vol_status,
                "OI % Change": f"{round(oi_change, 2)}%",
                "PCR Ratio": round(pcr, 2),
                "Max Pain": round(max_pain, 2),
                "F&O Build-Up": fo_buildup,
                "B/O STOCKS": bo_status,
                "B/O TREND": bo_trend,
                "⭐ SUPER CONVCTION": conviction,
                "LAST UPDATED TIME": current_time_str
            }
            processed_rows.append(row)
            
        except Exception as e:
            print(f"❌ Error processing {stock}: {str(e)}")
            continue
            
    df_output = pd.DataFrame(processed_rows)
    
    # ==========================================
    # 4. EXECUTING LIVE PUSH TO GOOGLE SHEET
    # ==========================================
    try:
        output_sheet = workbook.worksheet("MASTER_DASHBOARD")
        output_sheet.clear()
        
        headers = df_output.columns.tolist()
        matrix_data = df_output.values.tolist()
        set_with_dataframe_data = [headers] + matrix_data
        
        # Matrix force-update with range block routing
        output_sheet.update(set_with_dataframe_data, 'A1')
        
        print("📊 Preview Matrix data written successfully:")
        print(df_output.head(3).to_string())
        print(f"🏆 MASTER_DASHBOARD successfully updated at {current_time_str}!")
        
    except Exception as e:
        print(f"❌ Failed to push data to Google Sheet: {str(e)}")

if __name__ == "__main__":
    run_master_screener()

