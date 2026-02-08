#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def load_asset_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Date" not in df.columns or "close" not in df.columns:
        raise ValueError(f"{path.name}: expected columns Date, close; got {list(df.columns)}")
    df["Date"] = pd.to_datetime(df["Date"], errors="raise")
    df = df.sort_values("Date")
    df = df[["Date", "close"]].set_index("Date")
    return df


def main() -> int:
    p = argparse.ArgumentParser(description="Build aligned panel (close + returns) from sanitized OHLCV CSVs.")
    p.add_argument("--dir", default="data/processed_sanitized", help="Input directory with sanitized CSVs")
    p.add_argument("--out-close", default="data/processed_sanitized/panel_close.csv", help="Output close panel CSV")
    p.add_argument("--out-returns", default="data/processed_sanitized/panel_returns.csv", help="Output returns panel CSV")
    args = p.parse_args()

    base = Path(args.dir)
    files = sorted(
        f for f in base.glob("*.csv")
        if not f.name.startswith("_") and "log" not in f.name.lower()
    )
    if not files:
        raise SystemExit(f"No CSV files found in {base}")

    closes = []
    names = []

    for f in files:
        name = f.stem.upper()
        df = load_asset_csv(f).rename(columns={"close": name})
        closes.append(df)
        names.append(name)

    panel_close = pd.concat(closes, axis=1, join="inner").sort_index()

    # sanity: no gaps
    if panel_close.isna().any().any():
        bad = panel_close.isna().sum().to_dict()
        raise SystemExit(f"Panel has NaNs after inner-join: {bad}")

    panel_returns = panel_close.pct_change().dropna()

    Path(args.out_close).parent.mkdir(parents=True, exist_ok=True)
    panel_close.to_csv(args.out_close, index=True)
    panel_returns.to_csv(args.out_returns, index=True)

    print(f"OK: assets={names}")
    print(f"Saved close panel  -> {args.out_close} (rows={len(panel_close)})")
    print(f"Saved returns panel-> {args.out_returns} (rows={len(panel_returns)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

