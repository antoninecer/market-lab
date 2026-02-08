#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from engine.storage.db import insert_run


def main() -> int:
    ap = argparse.ArgumentParser(description="Log one pipeline run into SQLite (runs table).")
    ap.add_argument("--db", default="data/market_lab.sqlite3")
    ap.add_argument("--panel-close", required=True)
    ap.add_argument("--panel-returns", required=True)
    ap.add_argument("--baseline-equity", required=True)
    ap.add_argument("--baseline-trades", required=True)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--baseline-summary", required=True)
    ap.add_argument("--market-summary", required=True)
    ap.add_argument("--pipeline-version", default="v1")
    args = ap.parse_args()

    close = pd.read_csv(args.panel_close, parse_dates=["Date"])
    asof_date = close["Date"].max().strftime("%Y-%m-%d")
    universe = [c for c in close.columns if c != "Date"]

    baseline_summary = json.loads(Path(args.baseline_summary).read_text())
    market_summary = json.loads(Path(args.market_summary).read_text())

    run_id = insert_run(
        db_path=Path(args.db),
        asof_date=asof_date,
        universe=universe,
        pipeline_version=args.pipeline_version,
        panel_close_path=args.panel_close,
        panel_returns_path=args.panel_returns,
        baseline_equity_path=args.baseline_equity,
        baseline_trades_path=args.baseline_trades,
        report_dir=args.report_dir,
        baseline_summary=baseline_summary,
        market_summary=market_summary,
    )

    print(f"OK: logged run id={run_id} asof_date={asof_date} universe={universe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

