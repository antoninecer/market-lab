#!/usr/bin/env python3
"""market-lab Streamlit dashboard (robust to DB schema drift).

What this version fixes:
- Works when launched as: streamlit run dashboard/app.py
- Does NOT depend on engine.storage.db (no import issues)
- Uses repo-rooted DB path
- Supports both schemas:
  - "new": runs + equity + trades + last_returns
  - "old"/extra: baseline_equity/baseline_trades/baseline_positions/market_daily
- Lets you pick run_id in sidebar and plots full equity curve (5308 rows) from `equity`.
"""

from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


# -----------------------------
# Paths / DB
# -----------------------------
REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DB_PATH = REPO / "db" / "marketlab.sqlite"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Helpers
# -----------------------------
def table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
        return {r[1] for r in rows}
    except Exception:
        return set()


def init_min_schema(con: sqlite3.Connection) -> None:
    # Keep this minimal and non-destructive: only CREATE IF NOT EXISTS.
    con.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asof_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            universe TEXT,
            report_dir TEXT,
            source_dir TEXT,
            note TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);

        CREATE TABLE IF NOT EXISTS equity (
            run_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            equity REAL NOT NULL,
            cash REAL NOT NULL,
            PRIMARY KEY (run_id, date),
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS trades (
            run_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            asset TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            price REAL NOT NULL,
            notional REAL NOT NULL,
            fee_total REAL NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS last_returns (
            run_id INTEGER NOT NULL,
            asset TEXT NOT NULL,
            ret REAL NOT NULL,
            PRIMARY KEY (run_id, asset),
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        );
        """
    )
    con.commit()


def format_money(x: float) -> str:
    return f"{x:,.2f}"


# -----------------------------
# App
# -----------------------------
st.set_page_config(page_title="market-lab", layout="wide")
st.title("market-lab dashboard")

con = sqlite3.connect(str(DB_PATH))
con.execute("PRAGMA foreign_keys=ON;")
init_min_schema(con)

# -----------------------------
# Sidebar: runs
# -----------------------------
st.sidebar.subheader("Runs")

runs_df = pd.DataFrame()
try:
    if table_exists(con, "runs"):
        cols = columns(con, "runs")
        sel_cols = [c for c in ["id", "asof_date", "created_at", "universe", "note", "report_dir"] if c in cols]
        if "id" not in sel_cols:
            sel_cols = ["rowid"] + sel_cols  # ultra fallback
        runs_df = pd.read_sql(
            f"SELECT {', '.join(sel_cols)} FROM runs ORDER BY created_at DESC LIMIT 200",
            con,
        )
except Exception as e:
    st.sidebar.error(f"Cannot read runs: {e}")

if runs_df.empty:
    st.sidebar.info("No runs in DB yet.\n\nRun: python cli/ingest_sqlite.py")
    st.stop()

# choose run
if "id" in runs_df.columns:
    run_ids = runs_df["id"].tolist()
    default_run = run_ids[0]
    selected_run = st.sidebar.selectbox("Select run_id", run_ids, index=0)
    run_row = runs_df[runs_df["id"] == selected_run].iloc[0]
else:
    # shouldn't happen, but keep safe
    selected_run = None
    run_row = runs_df.iloc[0]

# show runs table
show_cols = [c for c in ["id", "asof_date", "created_at", "universe"] if c in runs_df.columns]
st.sidebar.dataframe(runs_df[show_cols], use_container_width=True, height=280)

st.sidebar.caption(f"DB: {DB_PATH}")

# -----------------------------
# Equity curve (prefer `equity`)
# -----------------------------
st.subheader("Equity curve")

equity_df = pd.DataFrame()

if table_exists(con, "equity"):
    try:
        equity_df = pd.read_sql(
            "SELECT date, equity, cash FROM equity WHERE run_id = ? ORDER BY date",
            con,
            params=(int(selected_run),),
        )
    except Exception as e:
        st.error(f"Cannot read equity for run_id={selected_run}: {e}")

# fallback to baseline_equity if present (and if it matches expected columns)
if equity_df.empty and table_exists(con, "baseline_equity"):
    try:
        c = columns(con, "baseline_equity")
        # common variants:
        # 1) asof_date,equity,cash
        # 2) date,equity,cash
        date_col = "asof_date" if "asof_date" in c else ("date" if "date" in c else None)
        if date_col and {"equity", "cash"}.issubset(c):
            equity_df = pd.read_sql(
                f"SELECT {date_col} AS date, equity, cash FROM baseline_equity ORDER BY date",
                con,
            )
    except Exception as e:
        st.warning(f"baseline_equity exists but can't be used: {e}")

if equity_df.empty:
    st.warning(
        "Nemám data pro equity křivku.\n\n"
        "Očekávám tabulku `equity` (run_id,date,equity,cash) naplněnou ingestem.\n"
        "Zkus: python cli/ingest_sqlite.py"
    )
    st.stop()

equity_df["date"] = pd.to_datetime(equity_df["date"], errors="coerce")
equity_df = equity_df.dropna(subset=["date"]).sort_values("date").set_index("date")

col1, col2, col3 = st.columns(3)
col1.metric("Equity (last)", format_money(float(equity_df["equity"].iloc[-1])))
col2.metric("Cash (last)", format_money(float(equity_df["cash"].iloc[-1])))
dd = (equity_df["equity"] / equity_df["equity"].cummax() - 1.0).min()
col3.metric("Max Drawdown", f"{dd*100:.2f}%")

st.line_chart(equity_df["equity"])

st.subheader("Drawdown")
dd_series = equity_df["equity"] / equity_df["equity"].cummax() - 1.0
st.area_chart(dd_series)

last_date = equity_df.index.max().strftime("%Y-%m-%d")

# -----------------------------
# Last day moves (prefer last_returns)
# -----------------------------
st.subheader("Market daily moves (last day)")

if table_exists(con, "last_returns"):
    try:
        lr = pd.read_sql(
            "SELECT asset, ret FROM last_returns WHERE run_id = ? ORDER BY ret DESC",
            con,
            params=(int(selected_run),),
        )
        if lr.empty:
            st.info("No last_returns for this run yet.")
        else:
            st.dataframe(lr, use_container_width=True)
    except Exception as e:
        st.info(f"last_returns not available: {e}")
elif table_exists(con, "market_daily"):
    # fallback to market_daily if you have it populated
    try:
        mk = pd.read_sql(
            "SELECT asset, close, ret_1d FROM market_daily WHERE asof_date = ? ORDER BY ret_1d DESC",
            con,
            params=(last_date,),
        )
        if mk.empty:
            st.info("No market_daily for last day in DB.")
        else:
            st.dataframe(mk, use_container_width=True)
    except Exception as e:
        st.info(f"market_daily not available: {e}")
else:
    st.info("No market table found (expected last_returns or market_daily).")

# -----------------------------
# Positions (optional)
# -----------------------------
st.subheader("Positions (last day)")

if table_exists(con, "baseline_positions"):
    try:
        pos = pd.read_sql(
            "SELECT asset, qty, price, value FROM baseline_positions WHERE asof_date = ? ORDER BY value DESC",
            con,
            params=(last_date,),
        )
        if pos.empty:
            st.info("No baseline_positions for last day in DB.")
        else:
            st.dataframe(pos, use_container_width=True)
    except Exception as e:
        st.info(f"baseline_positions not available yet: {e}")
else:
    st.info("baseline_positions table not present (OK for now).")

# -----------------------------
# Trades (prefer `trades`)
# -----------------------------
st.subheader("Trades (latest 200)")

trades_df = pd.DataFrame()

if table_exists(con, "trades"):
    try:
        trades_df = pd.read_sql(
            """
            SELECT date, asset, side, qty, price, notional, fee_total
            FROM trades
            WHERE run_id = ?
            ORDER BY date DESC
            LIMIT 200
            """,
            con,
            params=(int(selected_run),),
        )
    except Exception as e:
        st.info(f"Trades not available: {e}")

# fallback to baseline_trades if exists
if trades_df.empty and table_exists(con, "baseline_trades"):
    try:
        c = columns(con, "baseline_trades")
        date_col = "asof_date" if "asof_date" in c else ("date" if "date" in c else None)
        if date_col and {"asset", "side", "qty", "price", "notional", "fee_total"}.issubset(c):
            trades_df = pd.read_sql(
                f"""
                SELECT {date_col} AS date, asset, side, qty, price, notional, fee_total
                FROM baseline_trades
                ORDER BY date DESC
                LIMIT 200
                """,
                con,
            )
    except Exception as e:
        st.info(f"baseline_trades exists but can't be used: {e}")

if trades_df.empty:
    st.info("No trades found for this run.")
else:
    st.dataframe(trades_df, use_container_width=True)

con.close()
