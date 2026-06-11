import os
import json
import gspread
import yfinance as yf
import pandas as pd
import requests
from oauth2client.service_account import ServiceAccountCredentials

def send_telegram_alert(message):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat_id = os.environ.get('CHAT_ID')
    if token and chat_id:
        requests.get(f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=Markdown")

def main():
    STOCKS_LIST = [
    "NIFTYBEES.NS", "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", 
    "PERSISTENT.NS", "COFORGE.NS", "KPITTECH.NS", "LTTS.NS", "LT.NS", "ALKEM.NS", 
    "BHARATFORG.NS", "DRREDDY.NS", "DIVISLAB.NS", "SUNPHARMA.NS", "CIPLA.NS", 
    "LUPIN.NS", "ZYDUSLIFE.NS", "APOLLOHOSP.NS", "AUROPHARMA.NS", "BIOCON.NS", 
    "GRANULES.NS", "ASIANPAINT.NS", "BERGEPAINT.NS", "PIDILITIND.NS", "DABUR.NS", 
    "MARICO.NS", "TATACONSUM.NS", "BRITANNIA.NS", "BSE.NS", "KALYANKJIL.NS", 
    "NESTLEIND.NS", "MARUTI.NS", "TMPV.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", 
    "EICHERMOT.NS", "TIINDIA.NS", "BALKRISIND.NS", "RVNL.NS", "MAXHEALTH.NS", 
    "TITAN.NS", "SIEMENS.NS", "ABB.NS", "CUMMINSIND.NS", "BHARTIARTL.NS", 
    "HAVELLS.NS", "POLYCAB.NS", "M&M.NS", "POWERINDIA.NS", "ASHOKLEY.NS", 
    "TORNTPHARM.NS", "TATASTEEL.NS", "JINDALSTEL.NS", "HINDALCO.NS", "COALINDIA.NS", 
    "BSOFT.NS", "JUBLFOOD.NS", "ETERNAL.NS", "WAAREEENER.NS", "MOTHERSON.NS", 
    "MAZDOCK.NS", "COCHINSHIP.NS", "GRSE.NS", "BEL.NS", "BDL.NS", "SOLARINDS.NS", 
    "DMART.NS", "CGPOWER.NS", "NAUKRI.NS", "TVSMOTOR.NS", "MANKIND.NS", 
    "ULTRACEMCO.NS", "SHREECEM.NS", "COROMANDEL.NS", "BPCL.NS", "OFSS.NS", 
    "INDUSTOWER.NS", "BOSCHLTD.NS", "DIXON.NS", "SRF.NS", "GRASIM.NS", "HAL.NS", 
    "INDIGO.NS", "HINDUNILVR.NS", "NYKAA.NS", "HINDPETRO.NS", "APARINDS.NS", 
    "GAIL.NS", "UPL.NS", "JSWSTEEL.NS", "TRENT.NS", "ASTRAL.NS", "NETWEB.NS", 
    "GODREJCP.NS", "GODREJPROP.NS", "VOLTAS.NS", "APLAPOLLO.NS", "TATAPOWER.NS", 
    "PIIND.NS", "GLENMARK.NS", "FORTIS.NS", "LAURUSLABS.NS", "PETRONET.NS", 
    "TATACOMM.NS", "PHOENIXLTD.NS", "ESCORTS.NS", "TORNTPOWER.NS", "LENSKART.NS", 
    "KEI.NS", "AMBUJACEM.NS", "PRESTIGE.NS", "SUPREMEIND.NS", "CONCOR.NS", 
    "FLUOROCHEM.NS", "UNOMINDA.NS", "AIAENG.NS", "IRCTC.NS", "AJANTPHARM.NS", 
    "JKCEMENT.NS", "GODREJIND.NS", "APOLLOTYRE.NS", "TATAINVEST.NS", "KPRMILL.NS", 
    "ABBOTINDIA.NS", "ACC.NS", "IPCALAB.NS"
]
    creds_dict = json.loads(os.environ.get('GCP_CREDENTIALS_JSON'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive'])
    sheet = gspread.authorize(creds).open_by_key(os.environ.get('SHEET_ID')).get_worksheet(0)
    
    results = []
    for symbol in stocks:
        try:
            df = yf.Ticker(symbol).history(period="1mo")
            ltp = round(df['Close'].iloc[-1], 2)
            
            # Manual Indicators
            df['VWAP'] = (df['Volume'] * (df['High'] + df['Low'] + df['Close']) / 3).cumsum() / df['Volume'].cumsum()
            df['SMA'] = df['Close'].rolling(20).mean()
            df['STD'] = df['Close'].rolling(20).std()
            df['BB_Low'] = df['SMA'] - (2 * df['STD'])
            
            vwap = round(df['VWAP'].iloc[-1], 2)
            bb_low = round(df['BB_Low'].iloc[-1], 2)
            
            action = '⏳ WAIT'
            if ltp <= bb_low:
                action = '🎯 BUY SIGNAL'
                send_telegram_alert(f"🎯 *RADAR HIT: {symbol}*\n🟢 Entry: {ltp}\n💰 Target: {round(ltp*1.05, 2)}")
            
            results.append([symbol, ltp, action, vwap, bb_low])
        except:
            results.append([symbol, 0, "❌ ERROR", 0, 0])
    
    sheet.clear()
    sheet.update('A1', [['Symbol', 'LTP', 'Action', 'VWAP', 'BB_Low']] + results)

if __name__ == "__main__":
    main()
