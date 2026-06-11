import os, json, gspread, yfinance as yf, requests, pytz
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# --- V10.0: Autonomous Engine Logic ---

def get_market_bias(universe):
    """Checks if the broader market is in a healthy state."""
    # Logic: Agar 50% stocks apni 50-day EMA ke upar hain, toh Market 'Healthy' hai
    healthy_stocks = 0
    for sym in universe[:50]: # Sample check for speed
        df = yf.Ticker(sym).history(period="3mo")
        if len(df) > 50:
            ema_50 = df['Close'].ewm(span=50).mean().iloc[-1]
            if df['Close'].iloc[-1] > ema_50:
                healthy_stocks += 1
    return (healthy_stocks / 50) > 0.5

def scan_stock(sym, market_is_healthy):
    try:
        df = yf.Ticker(sym).history(period="3mo")
        if len(df) < 50: return [sym, 0, "DATA ERR", "-", "-", "-", "-", "-", "-"]
        
        ltp = df['Close'].iloc[-1]
        atr = (df['High'] - df['Low']).rolling(14).mean().iloc[-1]
        volatility = df['Close'].pct_change().std() * 100
        
        # Adaptive Risk Calculation
        multiplier = 2.0 if volatility > 1.5 else 1.2
        sl = round(ltp - (multiplier * atr), 2)
        tg = round(ltp + (2.5 * multiplier * atr), 2)
        
        # Contextual Logic
        signal = "⏳ SEARCHING..."
        if market_is_healthy:
            if df['Close'].iloc[-1] > df['Close'].ewm(span=50).mean().iloc[-1]:
                signal = "🎯 SYSTEM BUY" # Sirf jab market healthy ho
        else:
            signal = "🛡️ DEFENSIVE MODE" # Market risky hai, no new buys
            
        return [sym, round(ltp, 2), signal, f"{volatility:.2f}%", sl, tg]
    except:
        return [sym, 0, "ERROR", "-", "-", "-", "-", "-"]

# --- Main Setup ---
def main():
    universe = ['TRENT.NS', 'CUMMINSIND.NS', 'PERSISTENT.NS', 'TATAELXSI.NS', 'MAXHEALTH.NS']
    is_healthy = get_market_bias(universe)
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = [executor.submit(scan_stock, s, is_healthy) for s in universe]
        report = [r.result() for r in results]
    
    # [Update logic for Google Sheets same as previous versions...]
    print(f"Market Healthy: {is_healthy}")
    print(report)

if __name__ == "__main__":
    main()
