#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def sanitize_df(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = ["Date", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}; columns={list(df.columns)}")

    out = df.copy()

    # Ensure numeric
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    # Drop rows with broken numbers (rare, but be explicit)
    out = out.dropna(subset=["Date", "open", "high", "low", "close"])

    # Compute invariants
    row_max = out[["open", "close", "low"]].max(axis=1)
    row_min = out[["open", "close", "high"]].min(axis=1)

    bad_high = out["high"] < row_max
    bad_low = out["low"] > row_min

    changed = bad_high | bad_low
    changes = out.loc[changed, ["Date", "open", "high", "low", "close", "volume"]].copy()
    if not changes.empty:
        changes = changes.rename(columns={"high": "high_before", "low": "low_before"})
        changes["row_max"] = row_max[changed].values
        changes["row_min"] = row_min[changed].values

    # Clamp
    out.loc[bad_high, "high"] = row_max[bad_high]
    out.loc[bad_low, "low"] = row_min[bad_low]

    if not changes.empty:
        changes["high_after"] = out.loc[changed, "high"].values
        changes["low_after"] = out.loc[changed, "low"].values
        changes["fixed_high"] = bad_high[changed].values
        changes["fixed_low"] = bad_low[changed].values

    return out, changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default="data/processed")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--log", default="")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if not in_dir.exists():
        print(f"ERROR: input dir not found: {in_dir}")
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in in_dir.glob("*.csv") if not p.name.startswith("_")])
    if not files:
        print(f"ERROR: no CSV files in {in_dir}")
        return 2

    all_changes = []
    total_fixed_rows = 0

    for f in files:
        df = pd.read_csv(f)
        sanitized, changes = sanitize_df(df)

        if not changes.empty:
            changes.insert(0, "asset", f.stem)
            total_fixed_rows += len(changes)
            all_changes.append(changes)

        target = (out_dir / f.name) if out_dir else f
        sanitized.to_csv(target, index=False)

        status = "OK" if changes.empty else f"FIXED {len(changes)} row(s)"
        print(f"{f.name}: {status} -> {target}")

    print(f"\nTotal fixed rows: {total_fixed_rows}")

    if args.log:
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if all_changes:
            pd.concat(all_changes, ignore_index=True).to_csv(log_path, index=False)
        else:
            pd.DataFrame(
                columns=["asset", "Date", "open", "high_before", "low_before", "close", "volume",
                         "row_max", "row_min", "high_after", "low_after", "fixed_high", "fixed_low"]
            ).to_csv(log_path, index=False)
        print(f"Sanitizer log written to: {log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

