import sys
import time
import requests
import pandas as pd

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
    
    # Placeholder structure for output
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
        'last_updated': time.strftime("%H:%M:%S")
    }
    
    # Simulation / Fetching Block (Replace with your actual API session/urls)
    try:
        # Example data mapping logic (Connect your live payload here)
        if is_index:
            data['ltp'] = 24471.70
            data['price_pct_chg'] = -0.46
            data['vwap'] = 24571.91
            data['live_oi_pct'] = None  # Spot index has no native OI
            data['vcp_contraction'] = "N/A"
        else:
            # Individual F&O Stock Example (e.g. ZYDUSLIFE)
            data['ltp'] = 1191.60
            data['price_pct_chg'] = 6.43
            data['vwap'] = 1150.00
            data['ema20'] = 1127.15
            data['vcp_contraction'] = "NO"
            # If live OI is fetched, store float. If API drops, store None
            data['live_oi_pct'] = None  # Set to None if API fails, or numeric e.g. 5.2
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
        # VCP Contraction for Stocks
        col_e_vcp_str = raw_data['vcp_contraction']
        
        # OI Calculation & Fallback logic for Stocks
        if live_oi_pct is not None:
            col_d_oi_str = f"{'+' if live_oi_pct > 0 else ''}{live_oi_pct:.2f}%"
            
            # Buildup determination based on Price and OI
            if price_pct > 0 and live_oi_pct > 0:
                col_g_buildup_str = "LONG BUILDUP 🚀"
            elif price_pct > 0 and live_oi_pct < 0:
                col_g_buildup_str = "SHORT COVERING 🟢"
            elif price_pct < 0 and live_oi_pct > 0:
                col_g_buildup_str = "SHORT BUILDUP 🔻"
            else:
                col_g_buildup_str = "LONG UNWINDING ⚠️"
        else:
            # When stock OI fetch drops or unavailable
            col_d_oi_str = "N/A"
            col_g_buildup_str = "VOLUME BASED (NO OI) ⚠️" if price_pct > 0 else "NO OI DATA ⚠️"

    # --- COL H, I, J: Action & Priority Formatting ---
    if is_index:
        col_h_breakout = "INDEX TREND"
        col_i_action = "MARKET REGIME: BEARISH 📉" if price_pct < 0 else "MARKET REGIME: BULLISH 🚀"
        col_j_priority = "INDEX 🎯"  # Compact format retained
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

    # Assemble Formatted Row (Columns A to O)
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
        'Col L | Last Updated': raw_data['last_updated'],
        'Col M | B/O STOCKS': col_m_bo_stock,
        'Col N | TREND (STOCKS)': col_n_trend,
        'Col O | MOMENTUM': col_o_momentum
    }
    
    return formatted_row


# ==========================================
# 3. EXECUTION & TEST RUN
# ==========================================

if __name__ == "__main__":
    symbols_to_scan = ["NIFTY 50 🎯", "ZYDUSLIFE"]
    output_rows = []

    for sym in symbols_to_scan:
        raw_market_data = fetch_nse_data(sym)
        processed_row = process_scanner_row(raw_market_data)
        output_rows.append(processed_row)

    # Convert to DataFrame for displaying in Google Sheets structure
    df_output = pd.DataFrame(output_rows)
    
    print("\n--- PROCESSED SHEET OUTPUT ---")
    for index, row in df_output.iterrows():
        print(f"\n--- {row['Col A | Stock Symbol']} ---")
        for col_name, value in row.items():
            print(f"{col_name}: {value}")
