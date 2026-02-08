#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


# -----------------------------
# DB schema (base)
# -----------------------------
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at  TEXT NOT NULL,
  asof_date   TEXT NOT NULL
  -- report_dir TEXT (added later via migration if missing)
  -- note       TEXT (added later via migration if missing)
);

CREATE TABLE IF NOT EXISTS equity (
  run_id   INTEGER NOT NULL,
  date     TEXT NOT NULL,
  equity   REAL NOT NULL,
  cash     REAL NOT NULL,
  PRIMARY KEY (run_id, date),
  FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trades (
  run_id     INTEGER NOT NULL,
  date       TEXT NOT NULL,
  asset      TEXT NOT NULL,
  side       TEXT NOT NULL,
  qty        REAL NOT NULL,
  price      REAL NOT NULL,
  notional   REAL NOT NULL,
  fee_total  REAL NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS last_returns (
  run_id   INTEGER NOT NULL,
  asset    TEXT NOT NULL,
  ret      REAL NOT NULL,
  PRIMARY KEY (run_id, asset),
  FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);
"""


@dataclass
class Inputs:
    report_dir: Path
    baseline_equity: Path
    baseline_trades: Path
    panel_returns: Path
    panel_close: Path



def _pick_latest_report(reports_root: Path) -> Path:
    if not reports_root.exists():
        raise FileNotFoundError(f"reports root not found: {reports_root}")
    candidates = [p for p in reports_root.iterdir() if p.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"no report dirs found in: {reports_root}")
    candidates.sort(key=lambda p: p.name)  # expects YYYY-MM-DD
    return candidates[-1]


def _resolve_inputs(repo: Path, report_dir: Optional[Path]) -> Inputs:
    # --- define expected inputs first (fix: do not reference vars before assignment) ---
    panel_close = repo / "data" / "processed_sanitized" / "panel_close.csv"
    baseline_equity = repo / "data" / "processed_sanitized" / "baseline_equity.csv"
    baseline_trades = repo / "data" / "processed_sanitized" / "baseline_trades.csv"
    panel_returns = repo / "data" / "processed_sanitized" / "panel_returns.csv"

    # (optional) check presence of core inputs early (kept, but now valid)
    missing = [
        str(p) for p in (
            baseline_equity,
            baseline_trades,
            panel_returns,
            panel_close,
        )
        if not p.exists()
    ]

    if report_dir is None:
        report_dir = _pick_latest_report(repo / "reports" / "daily")
    report_dir = report_dir.resolve()

    # Keep the original "missing expected input files" gate,
    # but it should at least include all required inputs.
    missing = [str(p) for p in (baseline_equity, baseline_trades, panel_returns, panel_close) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "missing expected input files (run bin/daily_update.sh first):\n- " + "\n- ".join(missing)
        )

    return Inputs(
        report_dir=report_dir,
        baseline_equity=baseline_equity,
        baseline_trades=baseline_trades,
        panel_returns=panel_returns,
        panel_close=panel_close,
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    # row: (cid, name, type, notnull, dflt_value, pk)
    return {r[1] for r in rows}


def _ensure_column(con: sqlite3.Connection, table: str, col: str, col_def: str) -> None:
    cols = _table_columns(con, table)
    if col in cols:
        return
    con.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    con.commit()


def _init_db(con: sqlite3.Connection) -> None:
    # Create base tables (or keep existing)
    con.executescript(SCHEMA_SQL)
    con.commit()

    # Migrate runs table if it exists but is missing newer columns
    _ensure_column(con, "runs", "report_dir", "report_dir TEXT")
    _ensure_column(con, "runs", "note", "note TEXT")
    # Some schemas already have NOT NULL universe; this is safe/idempotent.
    _ensure_column(con, "runs", "universe", "universe TEXT")


def _infer_asof_date(report_dir: Path) -> str:
    # Prefer folder name YYYY-MM-DD
    try:
        datetime.strptime(report_dir.name, "%Y-%m-%d")
        return report_dir.name
    except Exception:
        pass

    # fallback to json if present
    js = report_dir / "baseline_summary.json"
    if js.exists():
        data = json.loads(js.read_text(encoding="utf-8"))
        for k in ("asof_date", "date"):
            if k in data:
                return str(data[k])

    return datetime.now().strftime("%Y-%m-%d")


def _load_last_returns(panel_returns: Path) -> pd.Series:
    df = pd.read_csv(panel_returns)
    if "Date" not in df.columns:
        raise ValueError(f"panel_returns missing Date column: {panel_returns}")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    last = df.iloc[-1]
    s = last.drop(labels=["Date"])
    s = pd.to_numeric(s, errors="coerce").dropna()
    return s


def _insert_run(
    con: sqlite3.Connection,
    asof_date: str,
    report_dir: Path,
    universe: str,
    note: Optional[str],
) -> int:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Be robust to schema drift: insert only columns that exist.
    cols = _table_columns(con, "runs")

    fields: list[str] = []
    values: list[object] = []

    def add(field: str, value: object) -> None:
        if field in cols:
            fields.append(field)
            values.append(value)

    add("created_at", created_at)
    add("asof_date", asof_date)
    # FIX: universe is required in your DB schema; insert it when present
    add("universe", universe)
    add("report_dir", str(report_dir))
    add("note", note)

    sql = f"INSERT INTO runs({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})"
    cur = con.execute(sql, values)
    con.commit()
    return int(cur.lastrowid)


def _upsert_equity(con: sqlite3.Connection, run_id: int, equity_csv: Path) -> int:
    df = pd.read_csv(equity_csv)
    if not {"Date", "equity", "cash"}.issubset(set(df.columns)):
        raise ValueError(f"baseline_equity.csv unexpected columns: {list(df.columns)}")

    rows = [(run_id, str(r["Date"]), float(r["equity"]), float(r["cash"])) for _, r in df[["Date", "equity", "cash"]].iterrows()]
    con.executemany(
        "INSERT OR REPLACE INTO equity(run_id, date, equity, cash) VALUES (?, ?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)


def _upsert_trades(con: sqlite3.Connection, run_id: int, trades_csv: Path) -> int:
    df = pd.read_csv(trades_csv)
    need = {"Date", "asset", "side", "qty", "price", "notional", "fee_total"}
    if not need.issubset(set(df.columns)):
        raise ValueError(f"baseline_trades.csv unexpected columns: {list(df.columns)}")

    rows = []
    for _, r in df[list(need)].iterrows():
        rows.append(
            (
                run_id,
                str(r["Date"]),
                str(r["asset"]),
                str(r["side"]),
                float(r["qty"]),
                float(r["price"]),
                float(r["notional"]),
                float(r["fee_total"]),
            )
        )

    con.executemany(
        "INSERT INTO trades(run_id, date, asset, side, qty, price, notional, fee_total) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)


def _upsert_last_returns(con: sqlite3.Connection, run_id: int, last_returns: pd.Series) -> int:
    rows = [(run_id, str(asset), float(ret)) for asset, ret in last_returns.items()]
    con.executemany(
        "INSERT OR REPLACE INTO last_returns(run_id, asset, ret) VALUES (?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)

def _infer_universe(panel_close: Path) -> str:
    """
    Returns universe as comma-separated string, e.g.:
    'GLD,JNJ,MSFT,NVDA,QQQ,SPY,XLE'
    """
    df = pd.read_csv(panel_close, nrows=1)
    cols = [c for c in df.columns if c != "Date"]
    if not cols:
        raise ValueError("Cannot infer universe: no asset columns found")
    return ",".join(cols)

def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest latest run artifacts into SQLite for the Streamlit dashboard.")
    ap.add_argument("--db", default="db/marketlab.sqlite", help="SQLite path (default: db/marketlab.sqlite)")
    ap.add_argument("--repo", default=".", help="Repo root (default: .)")
    ap.add_argument(
        "--report",
        default=None,
        help="Report dir (e.g. reports/daily/2026-02-06). If omitted, uses latest under reports/daily/",
    )
    ap.add_argument("--note", default=None, help="Optional note stored with the run.")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    report_dir = Path(args.report).resolve() if args.report else None
    inputs = _resolve_inputs(repo, report_dir)
    asof_date = _infer_asof_date(inputs.report_dir)

    # FIX: universe is required in your runs schema; infer it from panel_close columns
    universe = _infer_universe(inputs.panel_close)

    db_path = (repo / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db).resolve()

    con = _connect(db_path)
    try:
        _init_db(con)

        # FIX: pass universe into _insert_run
        run_id = _insert_run(
            con,
            asof_date=asof_date,
            report_dir=inputs.report_dir,
            universe=universe,
            note=args.note,
        )
        n_eq = _upsert_equity(con, run_id, inputs.baseline_equity)
        n_tr = _upsert_trades(con, run_id, inputs.baseline_trades)
        last_ret = _load_last_returns(inputs.panel_returns)
        n_lr = _upsert_last_returns(con, run_id, last_ret)

        print("OK: ingested")
        print(f" db={db_path}")
        print(f" run_id={run_id} asof_date={asof_date} report_dir={inputs.report_dir}")
        print(f" universe={universe}")
        print(f" rows: equity={n_eq} trades={n_tr} last_returns={n_lr}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
