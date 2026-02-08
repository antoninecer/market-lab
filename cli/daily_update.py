#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple

import pandas as pd

# NOTE:
# - uses yfinance for download (inside venv)
# - calls your existing scripts:
#   - engine/datasource/normalize_yahoo.py
#   - engine/datasource/sanitize_ohlc.py
#   - engine/evaluation/data_quality.py
#   - engine/evaluation/baseline_portfolio.py
#
# Outputs:
# - data/raw/*.csv
# - data/processed/*.csv
# - data/processed_sanitized/*.csv
# - data/processed_sanitized/panel_close.csv
# - data/processed_sanitized/panel_returns.csv
# - data/processed_sanitized/baseline_equity.csv
# - data/processed_sanitized/baseline_trades.csv


DEFAULT_TICKERS = ["SPY", "QQQ", "MSFT", "NVDA", "JNJ", "XLE", "GLD"]


def run(cmd: List[str], cwd: Path) -> None:
    print(f"\n$ {' '.join(cmd)}")
    p = subprocess.run(cmd, cwd=str(cwd))
    if p.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {p.returncode}: {' '.join(cmd)}")


def download_yahoo_raw(tickers: List[str], out_dir: Path, start: str | None, end: str | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import yfinance as yf  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "yfinance not available. Activate venv and install: python -m pip install yfinance"
        ) from e

    for t in tickers:
        print(f"Downloading {t}...")
        df = yf.download(
            t,
            start=start,
            end=end,
            auto_adjust=False,
            group_by="ticker",   # produces MultiIndex columns -> similar to what your normalizer already handled
            progress=True,
            actions=False,
            threads=False,
        )

        if df is None or len(df) == 0:
            raise RuntimeError(f"Download returned empty dataframe for ticker={t}")

        out_path = out_dir / f"{t}.csv"
        df.to_csv(out_path)
        print(f"Saved to {out_path}")


def build_panels_from_sanitized(sanitized_dir: Path) -> Tuple[Path, Path, List[str]]:
    # read sanitized OHLCV, build aligned close panel (inner join on dates)
    files = sorted(
        f for f in sanitized_dir.glob("*.csv")
        if f.is_file() and not f.name.startswith("_") and "log" not in f.name.lower()
    )
    if not files:
        raise RuntimeError(f"No sanitized CSV files found in {sanitized_dir}")

    series_list = []
    assets = []
    for f in files:
        asset = f.stem.upper()
        df = pd.read_csv(f, parse_dates=["Date"])
        if "close" not in df.columns:
            raise ValueError(f"{f.name}: missing 'close' column, columns={list(df.columns)}")
        s = df[["Date", "close"]].copy()
        s["close"] = pd.to_numeric(s["close"], errors="coerce")
        if s["close"].isna().any():
            raise ValueError(f"{f.name}: NaNs in close after numeric coercion")
        s = s.sort_values("Date").drop_duplicates("Date").set_index("Date")["close"]
        s.name = asset
        assets.append(asset)
        series_list.append(s)

    close_panel = pd.concat(series_list, axis=1, join="inner").sort_index()
    if close_panel.isna().any().any():
        raise ValueError("panel_close contains NaNs after join (unexpected for sanitized data)")

    returns_panel = close_panel.pct_change().dropna()

    out_close = sanitized_dir / "panel_close.csv"
    out_ret = sanitized_dir / "panel_returns.csv"
    close_panel.to_csv(out_close, index_label="Date")
    returns_panel.to_csv(out_ret, index_label="Date")

    print(f"OK: assets={assets}")
    print(f"Saved close panel  -> {out_close} (rows={len(close_panel)})")
    print(f"Saved returns panel-> {out_ret} (rows={len(returns_panel)})")

    return out_close, out_ret, assets


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily update pipeline (download -> normalize -> sanitize -> QC -> panels -> baseline).")
    ap.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS, help="Tickers to download (default: 7 assets)")
    ap.add_argument("--start", default="2005-01-01", help="Start date for history (default: 2005-01-01)")
    ap.add_argument("--end", default=None, help="End date (default: None = today)")
    ap.add_argument("--raw-dir", default="data/raw", help="Raw data directory")
    ap.add_argument("--processed-dir", default="data/processed", help="Processed directory (normalized)")
    ap.add_argument("--sanitized-dir", default="data/processed_sanitized", help="Processed sanitized directory")
    ap.add_argument("--sanitizer-log", default="data/processed_sanitized/_sanitizer_log.csv", help="Sanitizer log CSV path")
    ap.add_argument("--skip-download", action="store_true", help="Skip yfinance download step")
    ap.add_argument("--skip-baseline", action="store_true", help="Skip baseline portfolio step")
    ap.add_argument("--fee-bps", type=float, default=5.0, help="Baseline: variable fee in bps (default 5)")
    ap.add_argument("--slippage-bps", type=float, default=2.0, help="Baseline: slippage in bps (default 2)")
    ap.add_argument("--fixed", type=float, default=0.0, help="Baseline: fixed cost per trade/order (default 0)")
    args = ap.parse_args()

    repo = Path.cwd()

    raw_dir = repo / args.raw_dir
    processed_dir = repo / args.processed_dir
    sanitized_dir = repo / args.sanitized_dir
    sanitizer_log = repo / args.sanitizer_log

    # 1) Download
    if not args.skip_download:
        download_yahoo_raw(args.tickers, raw_dir, args.start, args.end)
    else:
        print("Skipping download (--skip-download).")

    # 2) Normalize raw -> processed
    # normalize_yahoo.py uses data/raw and writes to data/processed in your current flow
    run([sys.executable, "engine/datasource/normalize_yahoo.py"], cwd=repo)

    # 3) Sanitize processed -> sanitized
    sanitized_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "engine/datasource/sanitize_ohlc.py",
            "--in-dir", str(processed_dir),
            "--out-dir", str(sanitized_dir),
            "--log", str(sanitizer_log),
        ],
        cwd=repo,
    )

    # 4) Data quality (spy calendar)
    run(
        [
            sys.executable,
            "engine/evaluation/data_quality.py",
            "--dir", str(sanitized_dir),
            "--calendar", "spy",
        ],
        cwd=repo,
    )

    # 5) Build panels (close + returns)
    panel_close, panel_returns, assets = build_panels_from_sanitized(sanitized_dir)

    # 6) Baseline portfolio
    if not args.skip_baseline:
        # baseline_portfolio.py should default to panel_close path you already used,
        # but we pass it explicitly so it always matches sanitized panel.
        run(
            [
                sys.executable,
                "engine/evaluation/baseline_portfolio.py",
                "--panel", str(panel_close),
                "--initial", "1000.0",
                "--fee-bps", str(args.fee_bps),
                "--slippage-bps", str(args.slippage_bps),
                "--fixed", str(args.fixed),
                "--out-equity", str(sanitized_dir / "baseline_equity.csv"),
                "--out-trades", str(sanitized_dir / "baseline_trades.csv"),
            ],
            cwd=repo,
        )
    else:
        print("Skipping baseline (--skip-baseline).")

    print("\nDONE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

