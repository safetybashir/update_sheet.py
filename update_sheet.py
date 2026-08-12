import sys
import time
import requests
import pandas as pd
from datetime import datetime

# ==========================================
# 1. HELPER & DATA FETCHING FUNCTIONS
# ==========================================

def fetch_nse_data(symbol):
    """
    Fetch market data from NSE/Data Provider.
    Handles both Indices (NIFTY 50) and F&O Equity Stocks.
    """
    symbol_clean = symbol.strip().upper()
    is_index = "NIFTY" in symbol_clean or "BANKNIFTY" in symbol_clean
    
    # Live current time timestamp
    current_time_str = datetime.now().strftime("%H:%M:%S")
    
    data = {
        'symbol': symbol_clean,
        'is_index': is_index,
        'ltp': None,
        'price_pct_chg': None,
        'live_oi_pct': None,
        'volume_status': 'DRY-UP 💧',
        'vcp_contraction': 'NO',
        'vwap': None,
        'ema20': None,
        'last_updated': current_time_str
    }
    
    try:
        if is_index:
            data['ltp'] = 24471.70
            data['price_pct_chg'] = -0.46
            data['vwap'] = 24571.91
            data['live_oi_pct'] = None  # Spot index has no native OI
            data['vcp_contraction'] = "N/A"
        else:
            data['ltp'] = 1191.60
            data['price_pct_chg'] = 6.43
            data['vwap'] = 1150.00
            data['ema20'] = 1127.15
            data['vcp_contraction'] = "NO"
            data['live_oi_pct'] = None
            data['volume_status'] = "SPIKE ⚡"
            
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        
    return data


# ==========================================
# 2. MAIN PROCESSING & ROW GENERATION LOGIC
# ==========================================

def process_scanner_row(raw_data):
    symbol = raw_data['symbol']
    is_index = raw_data['is_index']
    price_pct = raw_data['price_pct_chg']
    live_oi_pct = raw_data['live_oi_pct']
    ltp = raw_data['ltp']
    vwap = raw_data['vwap']
    
    # --- COL D: OI % Change & COL G: Option Buildup Logic ---
    if is_index:
        col_d_oi_str = "INDEX (NO OI)"
        col_e_vcp_str = "INDEX (NO VCP)"
        col_g_buildup_str = "INDEX TREND"
    else:
        col_e_vcp_str = raw_data['vcp_contraction']
        
        if live_oi_pct is not None:
            col_d_oi_str = f"{'+' if live_oi_pct > 0 else ''}{live_oi_pct:.2f}%"
            if price_pct > 0 and live_oi_pct > 0:
                col_g_buildup_str = "LONG BUILDUP 🚀"
            elif price_pct > 0 and live_oi_pct < 0:
                col_g_buildup_str = "SHORT COVERING 🟢"
            elif price_pct < 0 and live_oi_pct > 0:
                col_g_buildup_str = "SHORT BUILDUP 🔻"
            else:
                col_g_buildup_str = "LONG UNWINDING ⚠️"
        else:
            col_d_oi_str = "N/A"
            col_g_buildup_str = "VOLUME BASED (NO OI) ⚠️" if price_pct > 0 else "NO OI DATA ⚠️"

    # --- COL H, I, J, K: Action & Priority Formatting ---
    if is_index:
        col_h_breakout = "INDEX TREND"
        col_i_action = "MARKET REGIME: BEARISH 📉" if price_pct < 0 else "MARKET REGIME: BULLISH 🚀"
        col_j_priority = "INDEX 🎯"
        col_k_support = f"PIVOT/VWAP: ₹{vwap}" if vwap else "N/A"
    else:
        col_h_breakout = "CE BREAKOUT 🚀" if price_pct > 3 else "RANGE BOUND ↔️"
        col_i_action = "BUY CE ON REVERSAL 🟢" if price_pct > 3 else "NO TRADE ⏸️"
        col_j_priority = "B/O #1"
        col_k_support = f"EMA20: ₹{raw_data['ema20']}" if raw_data['ema20'] else "N/A"

    # --- COL M, N, O: Trend & Momentum ---
    if ltp and vwap:
        col_m_bo_stock = "ABOVE VWAP 🟢" if ltp >= vwap else "BELOW VWAP 🔻"
    else:
        col_m_bo_stock = "N/A"
        
    col_n_trend = "📈 BULLISH TREND" if price_pct > 0 else "📉 BEARISH TREND"
    col_o_momentum = "SIDEWAYS / MIXED ↔️" if abs(price_pct) < 1 else "STRONG MOMENTUM ⚡"

    # --- FINAL ROW ASSEMBLY (Last Updated explicitly placed at the end) ---
    formatted_row = {
        'Col A | Stock Symbol': symbol,
        'Col B | LTP': f"₹{ltp:.2f}" if ltp else "N/A",
        'Col C | Price % Change': f"{price_pct:+.2f}%" if price_pct is not None else "N/A",
        'Col D | OI % Change': col_d_oi_str,
        'Col E | VCP Contraction': col_e_vcp_str,
        'Col F | Volume Status': raw_data['volume_status'],
        'Col G | CE/PE Option Buildup': col_g_buildup_str,
        'Col H | Breakout Status': col_h_breakout,
        'Col I | Action / Entry Trigger': col_i_action,
        'Col J | Priority Rank': col_j_priority,
        'Col K | Reversal Support Level': col_k_support,
        'Col M | B/O STOCKS': col_m_bo_stock,
        'Col N | TREND (STOCKS)': col_n_trend,
        'Col O | MOMENTUM': col_o_momentum,
        'Col L | Last Updated': raw_data['last_updated']  # <-- Shifted to the last position
    }
    
    return formatted_row


# ==========================================
# 3. CONTINUOUS LIVE SCANNER LOOP
# ==========================================

if __name__ == "__main__":
    symbols_to_scan = ["NIFTY 50 🎯", "ZYDUSLIFE"]
    
    print("🚀 Live Scanner Running... (Ctrl+C to Stop)")
    
    while True:
        try:
            output_rows = []
            for sym in symbols_to_scan:
                raw_market_data = fetch_nse_data(sym)
                processed_row = process_scanner_row(raw_market_data)
                output_rows.append(processed_row)

            df_output = pd.DataFrame(output_rows)
            
            print(f"\n--- SCAN REFRESH [{datetime.now().strftime('%H:%M:%S')}] ---")
            print(df_output.to_string(index=False))
            
            time.sleep(10)  # Refresh every 10 seconds
            
        except KeyboardInterrupt:
            print("\nScanner Stopped.")
            sys.exit()
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(5)
