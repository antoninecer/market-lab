import yfinance as yf
from pathlib import Path

ASSETS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "MSFT": "MSFT",
    "NVDA": "NVDA",
    "JNJ": "JNJ",
    "XLE": "XLE",
    "GLD": "GLD",
}

START = "2005-01-01"
END = None  # do dnes

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

for name, ticker in ASSETS.items():
    print(f"Downloading {ticker}...")
    df = yf.download(ticker, start=START, end=END, auto_adjust=True)
    if df.empty:
        print(f"⚠️  No data for {ticker}")
        continue

    out = DATA_DIR / f"{name}.csv"
    df.to_csv(out)
    print(f"Saved to {out}")

