import time
import pandas as pd
from datetime import datetime

# ==============================================================================
# 1. AAPKE SELECTED STOCKS LIST (Nifty 200 / FnO Watchlist)
# ==============================================================================
# Aap is list mein apne saare puraane selected stocks ke symbols rakh sakte hain
SELECTED_STOCKS = [
    'MOTILALOFS', 'BOSCHLTD', 'DALBHARAT', 'ASHOKLEY', 'DIXON',
    'TATASTEEL', 'RELIANCE', 'HDFCBANK', 'INFY', 'ICICIBANK',
    'TORNTPHARM', 'SBIN', 'BHARTIARTL', 'LT', 'AXISBANK',
    'TATAMOTORS', 'BAJFINANCE', 'MARUTI', 'SUNPHARMA', 'TITAN'
]

# ==============================================================================
# 2. GLOBAL MEMORY LOCK (First Come First Served - FIFO Queue)
# ==============================================================================
# Ye memory list screen par breakout hone wale stocks ki jagah ko FIX/LOCK rakhegi
CONFIRMED_STOCKS_QUEUE = []

# ==============================================================================
# 3. METRICS & 15M BREAKOUT CONFIRMATION LOGIC
# ==============================================================================
def process_stock_metrics(stock_data_list):
    """
    Aapke selected stocks ka live calculation aur 15M Breakout Trigger set karta hai.
    """
    df = pd.DataFrame(stock_data_list)

    # Price % Change & VWAP Difference
    df['Price % Change'] = ((df['LTP'] - df['Prev_Close']) / df['Prev_Close']) * 100
    df['LTP - VWAP'] = df['LTP'] - df['VWAP']

    # Intraday Trend Status
    df['Intraday Trend (VWAP / 15M)'] = df['LTP - VWAP'].apply(
        lambda x: "ABOVE VWAP (+ve) 🟢" if x > 0 else "BELOW VWAP (-ve) 🔴"
    )

    # Volume Spike Status
    df['Volume Status'] = df['Volume_Multiplier'].apply(
        lambda x: f"{round(x, 1)}x SPIKE ⚡" if x >= 1.5 else "DRY-UP 💧"
    )

    # CE / PE Option OI Buildup Status
    def calculate_oi_buildup(row):
        if row['Price % Change'] > 0 and row['OI % Change'] > 0:
            return "CE LONG BUILDUP 🔥"
        elif row['Price % Change'] < 0 and row['OI % Change'] > 0:
            return "PE LONG BUILDUP 🩸"
        elif row['Price % Change'] > 0 and row['OI % Change'] < 0:
            return "SHORT COVERING 🛡️"
        else:
            return "SHORT BUILDUP 📉"

    df['CE/PE Option Buildup'] = df.apply(calculate_oi_buildup, axis=1)

    # 15-Minute Breakout Entry Trigger Logic
    def determine_action(row):
        # Filter: LTP > VWAP + Volume >= 1.5x + VCP Pattern YES
        if (row['LTP'] > row['VWAP']) and (row['Volume_Multiplier'] >= 1.5) and (row['VCP_Pattern'] == "YES"):
            return "🔥🔥 BUY CE (15M CONFIRMED) 🟢"
        elif (row['LTP'] < row['VWAP']) and (row['Volume_Multiplier'] >= 1.5) and (row['VCP_Pattern'] == "YES"):
            return "🚨🚨 BUY PE (15M CONFIRMED) 🔴"
        else:
            return "NO ENTRY 🚫"

    df['Action / Entry Trigger'] = df.apply(determine_action, axis=1)

    return df

# ==============================================================================
# 4. SEQUENTIAL LOCKING LOGIC (Stock Position Freeze Mechanism)
# ==============================================================================
def apply_sequential_fifo_locking(df):
    """
    Breakout hone par pehla stock TOP #1 par Freeze hoga.
    Agla stock uske theek niche (#2, #3) add hoga. Shuffling nahi hogi.
    """
    global CONFIRMED_STOCKS_QUEUE

    # Step A: Identify 15M Confirmed Breakouts
    confirmed_mask = df['Action / Entry Trigger'].str.contains('CONFIRMED', na=False)
    newly_confirmed_symbols = df[confirmed_mask]['Stock Symbol'].tolist()

    # Step B: Add new breakout stocks to FIFO Queue
    for symbol in newly_confirmed_symbols:
        if symbol not in CONFIRMED_STOCKS_QUEUE:
            CONFIRMED_STOCKS_QUEUE.append(symbol)
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"🔒 [{timestamp}] LOCK TRIGGERED: {symbol} Locked at Priority #{len(CONFIRMED_STOCKS_QUEUE)}")

    # Step C: Re-order DataFrame without changing locked sequence
    confirmed_rows = []
    for symbol in CONFIRMED_STOCKS_QUEUE:
        matched_row = df[df['Stock Symbol'] == symbol]
        if not matched_row.empty:
            confirmed_rows.append(matched_row)

    if confirmed_rows:
        # Top Confirmed Section
        df_confirmed = pd.concat(confirmed_rows).reset_index(drop=True)
        df_confirmed['Priority Rank 🎯'] = [f"🔥 TOP PRIORITY #{i+1} ⚡" for i in range(len(df_confirmed))]

        # Bottom Watchlist Section (Rest of Selected Stocks)
        df_unconfirmed = df[~df['Stock Symbol'].isin(CONFIRMED_STOCKS_QUEUE)].copy()
        df_unconfirmed['Priority Rank 🎯'] = "WATCHLIST 👁️"
        df_unconfirmed = df_unconfirmed.sort_values(by=['Volume_Multiplier', 'Stock Symbol'], ascending=[False, True])

        # Final Dashboard Assembly
        final_df = pd.concat([df_confirmed, df_unconfirmed]).reset_index(drop=True)
    else:
        df['Priority Rank 🎯'] = "SCANNING 🔍"
        df = df.sort_values(by=['Volume_Multiplier', 'Stock Symbol'], ascending=[False, True]).reset_index(drop=True)
        final_df = df

    final_df['Last Updated'] = datetime.now().strftime('%H:%M:%S')
    return final_df

# ==============================================================================
# 5. LIVE MARKET BROKER / API DUMMY FETCHING
# ==============================================================================
def fetch_live_data_for_selected_stocks():
    """
    Aapka Zerodha/Fyers API function har 5 second mein aapke SELECTED_STOCKS 
    ka live data lekar aayega.
    """
    # DEMO REAL-TIME TICK DATA (API ke live data ko simulate karne ke liye)
    return [
        {'Stock Symbol': 'MOTILALOFS', 'LTP': 942.1, 'Prev_Close': 899.1, 'VWAP': 930.0, 'OI % Change': 13.5, 'Volume_Multiplier': 2.5, 'VCP_Pattern': 'YES'},
        {'Stock Symbol': 'BOSCHLTD', 'LTP': 48460.0, 'Prev_Close': 47100.0, 'VWAP': 48000.0, 'OI % Change': 12.0, 'Volume_Multiplier': 4.3, 'VCP_Pattern': 'YES'},
        {'Stock Symbol': 'DALBHARAT', 'LTP': 1980.0, 'Prev_Close': 2000.0, 'VWAP': 1990.0, 'OI % Change': 5.0, 'Volume_Multiplier': 0.8, 'VCP_Pattern': 'NO'},
        {'Stock Symbol': 'ASHOKLEY', 'LTP': 173.5, 'Prev_Close': 177.0, 'VWAP': 174.0, 'OI % Change': -2.0, 'Volume_Multiplier': 0.5, 'VCP_Pattern': 'NO'},
        {'Stock Symbol': 'TATASTEEL', 'LTP': 155.0, 'Prev_Close': 150.0, 'VWAP': 152.0, 'OI % Change': 8.5, 'Volume_Multiplier': 2.1, 'VCP_Pattern': 'YES'},
    ]

# ==============================================================================
# 6. MAIN ENGINE LOOP
# ==============================================================================
def run_screener_engine():
    print("🚀 SMART OI-VCP SCREENER STARTED FOR SELECTED STOCKS...")
    global CONFIRMED_STOCKS_QUEUE
    CONFIRMED_STOCKS_QUEUE = []  # Daily Reset at start

    try:
        while True:
            # Step 1: Fetch Live Feed of Selected Stocks
            raw_data = fetch_live_data_for_selected_stocks()

            # Step 2: Calculate VWAP, OI & Breakout Status
            processed_df = process_stock_metrics(raw_data)

            # Step 3: Apply Sequential Lock (Positions Freeze)
            final_dashboard = apply_sequential_fifo_locking(processed_df)

            # Step 4: Display Output
            print("\n" + "="*85)
            print(f"📊 LIVE DASHBOARD ({datetime.now().strftime('%H:%M:%S')}) | TOTAL WATCHED: {len(SELECTED_STOCKS)}")
            print("="*85)
            print(final_dashboard[[
                'Priority Rank 🎯', 'Stock Symbol', 'LTP', 'Price % Change',
                'Volume Status', 'CE/PE Option Buildup', 'Action / Entry Trigger', 'Last Updated'
            ]].to_string(index=False))

            time.sleep(5)  # Refresh every 5 seconds

    except KeyboardInterrupt:
        print("\n🛑 Screener Stopped Safely.")

# ==============================================================================
# EXECUTION START
# ==============================================================================
if __name__ == "__main__":
    run_screener_engine()
