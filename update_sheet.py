import os, json, gspread, yfinance as yf, requests, pytz
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from google.oauth2.service_account import Credentials

# 1. Global Context Filter
def get_global_sentiment():
    # In V11, we check a proxy for global risk (e.g., ^NSEI or ^GSPC)
    # Agar Nifty 50 apne 200-day EMA ke niche hai, toh Global Risk high hai.
    nifty = yf.Ticker("^NSEI").history(period="1mo")
    sma_200 = nifty['Close'].rolling(200).mean().iloc[-1]
    return "BEARISH" if nifty['Close'].iloc[-1] < sma_200 else "BULLISH"

# 2. Advanced Scan Logic
def scan_stock_v11(sym, global_trend):
    try:
        df = yf.Ticker(sym).history(period="3mo")
        if len(df) < 50: return [sym, 0, "DATA ERR", "-", "-", "-", "-", "-"]
        
        ltp = df['Close'].iloc[-1]
        vol = df['Volume'].iloc[-1]
        avg_vol = df['Volume'].rolling(20).mean().iloc[-1]
        vol_spike = round(vol / avg_vol, 2)
        rsi = 100 - (100 / (1 + (df['Close'].diff().clip(lower=0).rolling(14).mean() / -df['Close'].diff().clip(upper=0).rolling(14).mean())))
        rsi = rsi.iloc[-1]
        
        # Macro Check
        if global_trend == "BEARISH":
            return [sym, round(ltp, 2), "🛡️ GLOBAL RISK", "-", "-", "-", "-", "-"]

        # Breakout/Reversal Scoring
        signal = "⏳ SEARCHING..."
        if vol_spike > 2.5 and (ltp > df['High'].rolling(20).max().iloc[-2]):
            signal = "🔥 SUPER BREAKOUT"
        elif rsi < 30:
            signal = "⚡ STRONG REVERSAL"
        
        atr = (df['High'] - df['Low']).rolling(14).mean().iloc[-1]
        sl = round(ltp - (1.5 * atr), 2)
        tg = round(ltp + (3.0 * atr), 2)
        
        return [sym, round(ltp, 2), signal, f"{vol_spike}x", round(rsi, 2), sl, tg, "ACTIVE"]
    except:
        return [sym, 0, "ERROR", "-", "-", "-", "-", "-"]

def main():
    universe = ['TRENT.NS', 'CUMMINSIND.NS', 'PERSISTENT.NS', 'TATAELXSI.NS', 'MAXHEALTH.NS']
    global_trend = get_global_sentiment()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        report = list(executor.map(lambda s: scan_stock_v11(s, global_trend), universe))
    
    # [Google Sheet Update logic...]
    print(f"Global Trend: {global_trend}")
    print(report)

if __name__ == "__main__":
    main()
