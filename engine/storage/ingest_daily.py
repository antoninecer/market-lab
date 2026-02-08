#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON;")
    con.execute("PRAGMA journal_mode=WAL;")
    return con


def ensure_schema(con: sqlite3.Connection, schema_path: Path) -> None:
    sql = schema_path.read_text(encoding="utf-8")
    con.executescript(sql)
    con.commit()


def upsert_market_from_panels(con, panel_close: Path, panel_returns: Path) -> list[str]:
    close = pd.read_csv(panel_close, parse_dates=["Date"]).set_index("Date")
    rets = pd.read_csv(panel_returns, parse_dates=["Date"]).set_index("Date")

    assets = list(close.columns)

    rows = []
    for dt, r in close.iterrows():
        asof = dt.strftime("%Y-%m-%d")
        for a in assets:
            c = float(r[a])
            ret = None
            if dt in rets.index:
                try:
                    ret = float(rets.loc[dt, a])
                except Exception:
                    ret = None
            rows.append((asof, a, c, ret))

    con.executemany(
        """
        INSERT INTO market_daily(asof_date, asset, close, ret_1d)
        VALUES(?,?,?,?)
        ON CONFLICT(asof_date, asset)
        DO UPDATE SET close=excluded.close, ret_1d=excluded.ret_1d
        """,
        rows,
    )
    con.commit()
    return assets


def upsert_baseline(con, equity_csv: Path, trades_csv: Path) -> None:
    eq = pd.read_csv(equity_csv)
    # equity table
    con.executemany(
        """
        INSERT INTO baseline_equity(asof_date, equity, cash)
        VALUES(?,?,?)
        ON CONFLICT(asof_date) DO UPDATE SET equity=excluded.equity, cash=excluded.cash
        """,
        [(r["Date"], float(r["equity"]), float(r["cash"])) for _, r in eq.iterrows()],
    )

    # positions snapshot per day (qty_*, val_*)
    assets = sorted({c.replace("qty_", "") for c in eq.columns if c.startswith("qty_")})
    pos_rows = []
    for _, r in eq.iterrows():
        d = r["Date"]
        for a in assets:
            qty = float(r.get(f"qty_{a}", 0.0))
            val = float(r.get(f"val_{a}", 0.0))
            pos_rows.append((d, a, qty, val))

    con.executemany(
        """
        INSERT INTO baseline_positions(asof_date, asset, qty, value)
        VALUES(?,?,?,?)
        ON CONFLICT(asof_date, asset) DO UPDATE SET qty=excluded.qty, value=excluded.value
        """,
        pos_rows,
    )

    # trades
    tr = pd.read_csv(trades_csv)
    if len(tr) > 0:
        trade_rows = [
            (r["Date"], r["asset"], r["side"], float(r["qty"]), float(r["price"]), float(r["notional"]), float(r["fee_total"]))
            for _, r in tr.iterrows()
        ]
        con.execute("DELETE FROM baseline_trades")  # jednoduché MVP (později incremental)
        con.executemany(
            """
            INSERT INTO baseline_trades(asof_date, asset, side, qty, price, notional, fee_total)
            VALUES(?,?,?,?,?,?,?)
            """,
            trade_rows,
        )

    con.commit()


def register_run(con, asof_date: str, universe: list[str], source_dir: str, notes: str | None) -> str:
    run_id = f"{asof_date}-{datetime.utcnow().strftime('%H%M%S')}"
    con.execute(
        """
        INSERT OR REPLACE INTO runs(run_id, asof_date, created_at, universe, source_dir, notes)
        VALUES(?,?,?,?,?,?)
        """,
        (run_id, asof_date, datetime.utcnow().isoformat(timespec="seconds"), json.dumps(universe), source_dir, notes or ""),
    )
    con.commit()
    return run_id


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/marketlab.sqlite")
    ap.add_argument("--schema", default="engine/storage/schema_sqlite.sql")
    ap.add_argument("--dir", default="data/processed_sanitized")
    ap.add_argument("--asof", default=None, help="Asof date YYYY-MM-DD (default: infer from panel_close last row)")
    ap.add_argument("--notes", default=None)
    args = ap.parse_args()

    base = Path(args.dir)
    panel_close = base / "panel_close.csv"
    panel_returns = base / "panel_returns.csv"
    equity_csv = base / "baseline_equity.csv"
    trades_csv = base / "baseline_trades.csv"

    for p in [panel_close, panel_returns, equity_csv, trades_csv]:
        if not p.exists():
            raise SystemExit(f"Missing required file: {p}")

    con = connect(Path(args.db))
    ensure_schema(con, Path(args.schema))

    # infer asof from panel_close
    close_df = pd.read_csv(panel_close)
    inferred_asof = close_df["Date"].iloc[-1]
    asof = args.asof or inferred_asof

    universe = upsert_market_from_panels(con, panel_close, panel_returns)
    upsert_baseline(con, equity_csv, trades_csv)
    register_run(con, asof, universe, str(base), args.notes)

    print(f"OK: ingested asof={asof} universe={universe} db={args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

