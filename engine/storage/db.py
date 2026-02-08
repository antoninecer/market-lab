#!/usr/bin/env python3
"""SQLite storage for market-lab.

This is intentionally simple: no ORM, just a schema we can evolve.

Tables:
- runs: one row per pipeline run (as-of date, universe, pointers)
- baseline_equity: daily equity curve (as-of date, equity, cash)
- baseline_positions: positions snapshot per day (asset, qty, price, value)
- baseline_trades: executed trades (paper) with costs
- market_daily: per-asset daily close + 1d return

The dashboard only needs tables to exist; ingest is handled elsewhere.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asof_date TEXT NOT NULL,
        created_at TEXT NOT NULL,
        universe TEXT NOT NULL,
        note TEXT,
        source_dir TEXT
    );""",
    """CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);""",
    """CREATE TABLE IF NOT EXISTS baseline_equity (
        asof_date TEXT PRIMARY KEY,
        equity REAL NOT NULL,
        cash REAL NOT NULL
    );""",
    """CREATE TABLE IF NOT EXISTS baseline_positions (
        asof_date TEXT NOT NULL,
        asset TEXT NOT NULL,
        qty REAL NOT NULL,
        price REAL NOT NULL,
        value REAL NOT NULL,
        PRIMARY KEY (asof_date, asset)
    );""",
    """CREATE TABLE IF NOT EXISTS baseline_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asof_date TEXT NOT NULL,
        asset TEXT NOT NULL,
        side TEXT NOT NULL,
        qty REAL NOT NULL,
        price REAL NOT NULL,
        notional REAL NOT NULL,
        fee_var REAL NOT NULL,
        fee_fixed REAL NOT NULL,
        fee_total REAL NOT NULL
    );""",
    """CREATE INDEX IF NOT EXISTS idx_trades_asof_date ON baseline_trades(asof_date);""",
    """CREATE TABLE IF NOT EXISTS market_daily (
        asof_date TEXT NOT NULL,
        asset TEXT NOT NULL,
        close REAL NOT NULL,
        ret_1d REAL,
        PRIMARY KEY (asof_date, asset)
    );""",
]


def init_db(db_path: str | Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Opening a connection will create the file if missing (non-zero size after schema)
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)
        con.commit()
    finally:
        con.close()
