import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_sheet_client():
    try:
        creds_json = os.environ.get("GCP_CREDENTIALS_JSON")
        sheet_id = os.environ.get("SHEET_ID")
        
        if not creds_json or not sheet_id:
            raise ValueError("❌ Error: GCP_CREDENTIALS_JSON ya SHEET_ID GitHub Secrets me missing hai!")
            
        scope = ["https://google.com", "https://googleapis.com"]
        creds_dict = json.loads(creds_json)
        
        # 🔍 LOGGING: Terminal me dikhega ki script kis email ka use kar rahi hai
        print(f"🔑 Using Service Account Email: {creds_dict.get('client_email')}")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(sheet_id.strip())
    except Exception as e:
        print(f"❌ Google Sheet Authentication Failed: {str(e)}")
        return None

STOCKS = [
    'NIFTY_50', 'TORNTPHARM', 'ASHOKLEY', 'KAYNES', 'INOXWIND', 'GAIL', 'KEI', 
    'PREMIERENE', 'CGPOWER', 'M&M', 'BSE', 'DIVISLAB', 'NYKAA', 'PHOENIXLTD', 'LUPIN'
]

def run_master_screener():
    print("🚀 F&O Screener Force Matrix Injection Started...")
    workbook = get_sheet_client()
    if not workbook:
        print("❌ Script Stopped: Sheet client initialization failed.")
        return

    processed_rows = []
    current_time_str = datetime.now().strftime("%H:%M:%S")

    # Pure dynamic tester data framework
    for stock in STOCKS:
        try:
            ltp = round(float(np.random.uniform(100, 5000)), 2)
            price_change_pct = round(float(np.random.uniform(-3, 5)), 2)
            oi_change = round(float(np.random.uniform(-5, 15)), 2)
            
            row = {
                "SYMBOLE": stock,
                "LTP": ltp,
                "Price % Change": f"{price_change_pct}%",
                "Volume Spike": "🔥 SPIKE" if price_change_pct > 1 else "😴 STABLE",
                "OI % Change": f"{oi_change}%",
                "PCR Ratio": round(float(np.random.uniform(0.6, 1.4)), 2),
                "Max Pain": round(ltp * 0.98, 2),
                "F&O Build-Up": "🔥 LONG BUILDUP" if price_change_pct > 0 else "😴 NEUTRAL",
                "B/O STOCKS": "No Cash Breakouts",
                "B/O TREND": "⏳ RANGE",
                "⭐ SUPER CONVCTION": "😴 NO SIGNAL",
                "LAST UPDATED TIME": current_time_str
            }
            processed_rows.append(row)
        except Exception as e:
            print(f"Error compiling {stock}: {str(e)}")

    df_output = pd.DataFrame(processed_rows)

    # =======================================================
    # 💥 FOOLPROOF OVERWRITE: TARGETING BY NAME OR GID
    # =======================================================
    try:
        # Pehle naam se try karega
        try:
            output_sheet = workbook.worksheet("MASTER_DASHBOARD")
            print("🎯 Found worksheet by name 'MASTER_DASHBOARD'")
        except:
            # Agar naam kaam nahi kiya toh aapke link wale GID (103159714) se force pick karega
            print("⚠️ Tab name match failed, forcing target with GID: 103159714")
            output_sheet = workbook.get_worksheet_by_id(103159714)
            
        if not output_sheet:
            raise ValueError("❌ Sheet tab nahi mil pa raha hai!")

        # Data matrix clean up and push
        output_sheet.clear()
        headers = df_output.columns.tolist()
        matrix_data = df_output.values.tolist()
        final_dump = [headers] + matrix_data
        
        # Raw value update injection
        output_sheet.update(final_dump, 'A1')
        print(f"\n🏆 SUCCESS! MASTER_DASHBOARD UPDATED AT {current_time_str}!")
        print(df_output.head(2).to_string())
        
    except Exception as e:
        print(f"\n❌ CRITICAL PUSH ERROR: {str(e)}")
        print("💡 Solution: Check if GitHub Secrets 'GCP_CREDENTIALS_JSON' matches your shared email account.")

if __name__ == "__main__":
    run_master_screener()

        
