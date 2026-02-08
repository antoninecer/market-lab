#!/usr/bin/env python3
"""
Normalize Yahoo Finance CSV exports (including yfinance downloads) into a clean format:

Output columns:
Date, close, high, low, open, volume

- Ensures Date is a real column (not index)
- Handles Yahoo/yfinance 2-row "Price/Ticker" headers
- Drops the bogus "Ticker" row if present
- Lowercases OHLCV column names
"""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd


RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")


def _read_yahoo_csv(path: Path) -> pd.DataFrame:
    """
    Read a Yahoo/yfinance CSV robustly.

    yfinance often produces:
        Price,Close,High,Low,Open,Volume
        Ticker,SPY,SPY,SPY,SPY,SPY
        Date,,,,,
        2005-01-03,...

    We try header=[0,1] first (MultiIndex). If that fails, fall back to header=0.
    """
    # Try multi-header first
    try:
        df = pd.read_csv(path, header=[0, 1])
        # If this worked, columns are MultiIndex like ('Price','') or ('Close','SPY'), etc.
        if isinstance(df.columns, pd.MultiIndex):
            # "Flatten": take level 0 (Price/Close/High/Low/Open/Volume/Date)
            df.columns = [str(c[0]).strip() for c in df.columns]
        return df
    except Exception:
        # Fallback: plain header
        return pd.read_csv(path)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Strip whitespace, normalize case
    df.columns = [str(c).strip() for c in df.columns]

    # Some exports have first column called "Date" already.
    # Some (badly normalized) may have first col as "Price" with date values under it.
    # We handle both cases.

    # Drop the "Ticker" row if present in the first column
    first_col = df.columns[0]
    # Sometimes there is a "Date" row with empty values; keep only real dates later.
    if df[first_col].astype(str).str.lower().eq("ticker").any():
        df = df[~df[first_col].astype(str).str.lower().eq("ticker")].copy()

    # If there is a column named 'Date' use it, otherwise if first column is 'Price' treat it as Date.
    if "Date" in df.columns:
        date_col = "Date"
    elif df.columns[0].lower() == "price":
        date_col = df.columns[0]  # "Price"
    else:
        # As a last resort assume first column is date-like
        date_col = df.columns[0]

    # Rename date column to Date
    if date_col != "Date":
        df = df.rename(columns={date_col: "Date"})

    # Remove the spurious "Date,,,,," row if present
    df = df[df["Date"].astype(str).str.lower().ne("date")].copy()

    # Parse Date and drop rows that aren't valid dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).copy()

    # Now normalize OHLCV column names
    rename_map = {
        "Close": "close",
        "High": "high",
        "Low": "low",
        "Open": "open",
        "Volume": "volume",
        "Adj Close": "adj_close",
        "AdjClose": "adj_close",
        "Price": "price",  # if it exists as a real column (usually it shouldn't)
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Keep only the columns we want; prefer 'close' (or fallback to 'adj_close' if needed)
    if "close" not in df.columns and "adj_close" in df.columns:
        df["close"] = df["adj_close"]

    required = ["Date", "close", "high", "low", "open", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns after normalize: {missing}. Columns={list(df.columns)}")

    df = df[required].copy()

    # Ensure numeric types
    for c in ["close", "high", "low", "open", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close", "high", "low", "open"]).copy()

    # Sort by date and de-dup
    df = df.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")

    return df


def normalize_file(csv_path: Path) -> Path:
    df = _read_yahoo_csv(csv_path)
    df = _normalize_columns(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / csv_path.name
    df.to_csv(out_path, index=False)
    return out_path


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"Missing folder: {RAW_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_files = sorted(RAW_DIR.glob("*.csv"))
    if not raw_files:
        print("No CSV files found in data/raw")
        return

    for f in raw_files:
        print(f"Processing {f.name}")
        out = normalize_file(f)
        print(f"Saved normalized to {out}")


if __name__ == "__main__":
    main()

