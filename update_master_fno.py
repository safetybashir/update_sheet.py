import pandas as pd
import numpy as np
from datetime import datetime

# 1. Aapke saare 152+ Stocks ki Master List (Nifty 50 on top + F&O)
STOCKS = [
    'NIFTY_50', 'TORNTPHARM', 'ASHOKLEY', 'KAYNES', 'INOXWIND', 'GAIL', 'KEI', 
    'PREMIERENE', 'CGPOWER', 'M&M', 'BSE', 'DIVISLAB', 'NYKAA', 'PHOENIXLTD', 'LUPIN'
    # ... baki ke saare stocks aap is list me add kar sakte hain
]

def calculate_breakout_and_fo(stock_data):
    """
    Har ek stock ka structural data process karne ka function.
    Agar koi data point missing hoga to script crash nahi karegi.
    """
    processed_rows = []
    
    for stock in STOCKS:
        try:
            # --- PROXY/API DATA FETCHING SIMULATION ---
            # Real execution me aap yahan apna Zerodha/Kite ya Google Sheets API feed lagayenge
            ltp = float(stock_data.get(stock, {}).get('LTP', 0))
            prev_close = float(stock_data.get(stock, {}).get('PREV_CLOSE', 1))
            volume = float(stock_data.get(stock, {}).get('VOLUME', 0))
            avg_volume = float(stock_data.get(stock, {}).get('AVG_VOLUME', 1))
            oi_change = float(stock_data.get(stock, {}).get('OI_CHG_%', 0))
            pcr = float(stock_data.get(stock, {}).get('PCR', 1.0))
            max_pain = float(stock_data.get(stock, {}).get('MAX_PAIN', 0))
            
            # --- MATHEMATICAL CALCULATIONS & LOGIC ---
            price_change_pct = ((ltp - prev_close) / prev_close) * 100
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
                
            # 3. Breakout Status & Conviction (Mark Minervini / Kell Style)
            # Close near Day High & Volume Spike
            day_high = float(stock_data.get(stock, {}).get('HIGH', ltp))
            distance_from_high = ((day_high - ltp) / ltp) * 100
            
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
            
            # Row compilation
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
                "LAST UPDATED TIME": datetime.now().strftime("%H:%M:%S")
            }
            processed_rows.append(row)
            
        except Exception as e:
            # ZERO DEAD-END: Agar kisi stock me error aaye to crash mat karo, logging karo
            print(f"Error processing {stock}: {str(e)}")
            continue
            
    return pd.DataFrame(processed_rows)

# Dashboard run karne ka dummy initiation
# df_dashboard = calculate_breakout_and_fo(raw_market_data)

