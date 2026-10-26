import yfinance as yf

print("🔍 Testing single stock fetch (Bosch)...")
df = yf.download("BOSCHLTD.NS", period="2d", interval="1d", progress=False)

if not df.empty:
    print("✅ Success! Data received:")
    print(df.tail(2))
else:
    print("❌ Failed: yfinance returned empty data.")
