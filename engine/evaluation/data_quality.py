#!/usr/bin/env python3
"""
Data quality checks for normalized OHLCV CSVs.

Expected columns:
- Date (YYYY-MM-DD)
- open, high, low, close, volume

Checks:
- required columns present (case-insensitive mapping)
- Date parseable, sorted, unique
- OHLC positive, high>=max(open,close,low), low<=min(open,close,high)
- volume non-negative
- NaNs
- missing expected trading days:
    --calendar business : Mon-Fri (includes market holidays, so warnings are expected)
    --calendar spy      : use SPY dates as master calendar (recommended)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


REQUIRED = ["Date", "open", "high", "low", "close", "volume"]


def _normalize_columns(cols: List[str]) -> Dict[str, str]:
    """
    Map required canonical names -> actual column names in df.
    Matching is case-insensitive and trims whitespace.
    """
    mapping: Dict[str, str] = {}
    cleaned = {c.strip().lower(): c for c in cols}
    for req in REQUIRED:
        key = req.strip().lower()
        if key in cleaned:
            mapping[req] = cleaned[key]
    return mapping


def _read_csv(path: Path) -> pd.DataFrame:
    # do not set index_col here; we want to validate Date first
    return pd.read_csv(path)


def _load_spy_calendar(base_dir: Path) -> pd.DatetimeIndex:
    spy = base_dir / "SPY.csv"
    if not spy.exists():
        raise FileNotFoundError(f"SPY.csv not found in {base_dir} (needed for --calendar spy)")

    df = pd.read_csv(spy)
    cols = {c.strip().lower(): c for c in df.columns}
    if "date" not in cols:
        raise ValueError(f"SPY.csv missing Date column, columns={list(df.columns)}")

    dates = pd.to_datetime(df[cols["date"]], errors="coerce")
    dates = dates.dropna().drop_duplicates().sort_values()
    return pd.DatetimeIndex(dates)


def _missing_against_expected(
    dates: pd.Series,
    expected: pd.DatetimeIndex,
) -> Tuple[int, int, pd.DatetimeIndex]:
    present = pd.DatetimeIndex(dates.dropna().unique()).sort_values()
    missing = expected.difference(present)
    return len(expected), len(present), missing


def check_file(
    path: Path,
    max_missing_days_to_list: int = 30,
    expected_calendar: pd.DatetimeIndex | None = None,
) -> Dict[str, object]:
    result: Dict[str, object] = {
        "file": str(path),
        "ok": True,
        "errors": [],
        "warnings": [],
    }

    try:
        df = _read_csv(path)
    except Exception as e:
        result["ok"] = False
        result["errors"].append(f"failed to read CSV: {e}")
        return result

    colmap = _normalize_columns(list(df.columns))
    missing_cols = [c for c in REQUIRED if c not in colmap]
    if missing_cols:
        result["ok"] = False
        result["errors"].append(f"missing required columns: {missing_cols}; columns={list(df.columns)}")
        return result

    # Rename to canonical columns for consistent checks
    df = df.rename(columns={colmap[k]: k for k in colmap})

    # Parse Date
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=False)
    bad_dates = int(df["Date"].isna().sum())
    if bad_dates:
        result["ok"] = False
        result["errors"].append(f"unparseable Date rows: {bad_dates}")
        return result

    # Sort by Date
    df = df.sort_values("Date").reset_index(drop=True)

    # Duplicates
    dup = int(df["Date"].duplicated().sum())
    if dup:
        result["ok"] = False
        result["errors"].append(f"duplicate Date rows: {dup}")

    # Basic NaN checks (before coercion)
    nan_counts = df[["open", "high", "low", "close", "volume"]].isna().sum()
    nan_total = int(nan_counts.sum())
    if nan_total:
        result["ok"] = False
        result["errors"].append(f"NaNs in OHLCV: {nan_counts.to_dict()}")

    # Numeric coercion
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    nan_after = df[["open", "high", "low", "close", "volume"]].isna().sum()
    nan_after_total = int(nan_after.sum())
    if nan_after_total:
        result["ok"] = False
        result["errors"].append(f"non-numeric values coerced to NaN in OHLCV: {nan_after.to_dict()}")

    # OHLC sanity
    for c in ["open", "high", "low", "close"]:
        nonpos = int((df[c] <= 0).sum())
        if nonpos:
            result["ok"] = False
            result["errors"].append(f"{c}: non-positive values: {nonpos}")

    vol_neg = int((df["volume"] < 0).sum())
    if vol_neg:
        result["ok"] = False
        result["errors"].append(f"volume: negative values: {vol_neg}")

    bad_high = int((df["high"] < df[["open", "close", "low"]].max(axis=1)).sum())
    bad_low = int((df["low"] > df[["open", "close", "high"]].min(axis=1)).sum())
    if bad_high:
        result["ok"] = False
        result["errors"].append(f"high < max(open,close,low): {bad_high}")
    if bad_low:
        result["ok"] = False
        result["errors"].append(f"low > min(open,close,high): {bad_low}")

    # Missing expected trading days
    if expected_calendar is None:
        expected = pd.date_range(df["Date"].min(), df["Date"].max(), freq="B")  # Mon-Fri
        cal_label = "Mon-Fri calendar (includes market holidays)"
    else:
        expected = expected_calendar[
            (expected_calendar >= df["Date"].min()) & (expected_calendar <= df["Date"].max())
        ]
        cal_label = "SPY calendar"

    expected_n, present_n, missing = _missing_against_expected(df["Date"], expected)

    result["expected_business_days"] = expected_n
    result["present_business_days"] = present_n
    result["missing_business_days"] = len(missing)

    if len(missing) > 0:
        msg = (
            f"missing days vs {cal_label} between {df['Date'].min().date()} and {df['Date'].max().date()}: {len(missing)}"
        )
        result["warnings"].append(msg)

        if len(missing) <= max_missing_days_to_list:
            result["missing_dates_sample"] = [d.strftime("%Y-%m-%d") for d in missing]
        else:
            sample = missing[:max_missing_days_to_list]
            result["missing_dates_sample"] = [d.strftime("%Y-%m-%d") for d in sample]
            result["missing_dates_sample"].append(f"... (+{len(missing)-max_missing_days_to_list} more)")

    # Summary stats
    result["rows"] = int(len(df))
    result["date_min"] = df["Date"].min().strftime("%Y-%m-%d")
    result["date_max"] = df["Date"].max().strftime("%Y-%m-%d")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run data quality checks on processed OHLCV CSVs.")
    parser.add_argument(
        "--dir",
        default="data/processed",
        help="Directory with processed CSV files (default: data/processed)",
    )
    parser.add_argument(
        "--max-missing-list",
        type=int,
        default=30,
        help="Max missing business days to print as a sample list (default: 30)",
    )
    parser.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="Treat warnings as errors (useful for strict CI).",
    )
    parser.add_argument(
        "--calendar",
        choices=["business", "spy"],
        default="business",
        help="Expected trading days calendar: business=Mon-Fri, spy=use SPY dates as master calendar (default: business)",
    )

    args = parser.parse_args()

    base = Path(args.dir)
    if not base.exists() or not base.is_dir():
        print(f"ERROR: directory not found: {base}", file=sys.stderr)
        return 2

    spy_calendar = None
    if args.calendar == "spy":
        try:
            spy_calendar = _load_spy_calendar(base)
        except Exception as e:
            print(f"ERROR: cannot load SPY calendar: {e}", file=sys.stderr)
            return 2

    files = sorted(
        f for f in base.glob("*.csv")
        if (
            not f.name.startswith("_")
            and "log" not in f.name.lower()
            and not f.name.startswith("panel_")
            and not f.name.startswith("baseline_")
        )
    )

    if not files:
        print(f"ERROR: no CSV files found in {base}", file=sys.stderr)
        return 2

    any_errors = False
    any_warnings = False

    print(f"Scanning {len(files)} file(s) in {base}...\n")

    for f in files:
        r = check_file(
            f,
            max_missing_days_to_list=args.max_missing_list,
            expected_calendar=spy_calendar,
        )

        ok = r["ok"]
        errs = r["errors"]
        warns = r["warnings"]

        status = "OK" if ok else "FAIL"
        print(f"== {f.name}: {status}")
        print(f"  rows={r.get('rows')} range={r.get('date_min')}..{r.get('date_max')}")
        print(
            f"  business_days present/expected={r.get('present_business_days')}/{r.get('expected_business_days')}"
            f" missing={r.get('missing_business_days')}"
        )

        if warns:
            any_warnings = True
            for w in warns:
                print(f"  WARN: {w}")
            sample = r.get("missing_dates_sample")
            if sample:
                print(f"  WARN sample missing dates: {sample}")

        if errs:
            any_errors = True
            for e in errs:
                print(f"  ERROR: {e}")

        print("")

    if args.fail_on_warn and any_warnings:
        print("Result: FAIL (warnings treated as errors)", file=sys.stderr)
        return 1

    if any_errors:
        print("Result: FAIL", file=sys.stderr)
        return 1

    print("Result: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
