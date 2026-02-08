import pandas as pd
from pathlib import Path
import numpy as np

DATA_DIR = Path("data/processed")

results = []

for csv_file in DATA_DIR.glob("*.csv"):
    symbol = csv_file.stem

    df = pd.read_csv(csv_file)

    # NORMALIZACE HLAVIČEK (kritické!)
    df.columns = [c.strip().lower() for c in df.columns]

    # kontrola
    if "date" not in df.columns:
        raise ValueError(f"{symbol}: missing 'date' column, columns={df.columns}")

    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    # denní výnosy
    df["ret"] = df["close"].pct_change()

    days = len(df)
    years = days / 252

    cagr = (df["close"].iloc[-1] / df["close"].iloc[0]) ** (1 / years) - 1
    vol = df["ret"].std() * np.sqrt(252)

    equity = (1 + df["ret"]).cumprod()
    dd = equity / equity.cummax() - 1
    max_dd = dd.min()

    results.append({
        "asset": symbol,
        "CAGR": round(cagr * 100, 2),
        "Volatility": round(vol * 100, 2),
        "MaxDrawdown": round(max_dd * 100, 2),
        "Years": round(years, 1),
    })

summary = pd.DataFrame(results).sort_values("CAGR", ascending=False)
print(summary)

