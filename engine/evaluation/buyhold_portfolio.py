#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


@dataclass
class Costs:
    fee_bps: float = 5.0          # 5 bps = 0.05% per notional
    slippage_bps: float = 2.0     # 2 bps = 0.02% per notional
    fixed_per_trade: float = 0.0  # fixed cost per order


def bps_to_rate(bps: float) -> float:
    return bps / 10_000.0


def load_panel_close(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.sort_values("Date").set_index("Date")
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if df.isna().any().any():
        bad = df.isna().sum().to_dict()
        raise ValueError(f"panel_close contains NaNs: {bad}")
    return df


def summarize_equity(equity: pd.DataFrame) -> Dict[str, float]:
    eq = equity["equity"].astype(float)
    rets = eq.pct_change().dropna()

    years = (pd.to_datetime(equity["Date"].iloc[-1]) - pd.to_datetime(equity["Date"].iloc[0])).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    vol = rets.std() * (252 ** 0.5)
    dd = (eq / eq.cummax() - 1.0).min()

    return {
        "start_equity": float(eq.iloc[0]),
        "end_equity": float(eq.iloc[-1]),
        "years": float(years),
        "CAGR_pct": float(cagr * 100.0),
        "Volatility_pct": float(vol * 100.0),
        "MaxDrawdown_pct": float(dd * 100.0),
        "trading_days": float(len(eq)),
    }


def simulate_buyhold_equal_weight(
    close: pd.DataFrame,
    initial_cash: float,
    costs: Costs,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    assets = list(close.columns)
    n = len(assets)
    w = 1.0 / n

    fee_rate = bps_to_rate(costs.fee_bps)
    slip_rate = bps_to_rate(costs.slippage_bps)

    cash = float(initial_cash)
    qty: Dict[str, float] = {a: 0.0 for a in assets}
    trade_rows: List[Dict[str, object]] = []
    equity_rows: List[Dict[str, float]] = []

    # --- single entry on first date ---
    first_dt = close.index[0]
    first_prices = close.loc[first_dt].astype(float)

    # buy sequentially with cash constraint (cash-friendly)
    for a in assets:
        target_notional = initial_cash * w
        exec_price = float(first_prices[a]) * (1.0 + slip_rate)

        max_notional_exec = max(0.0, (cash - costs.fixed_per_trade) / (1.0 + fee_rate))
        notional_exec = min(target_notional, max_notional_exec)
        if notional_exec <= 0:
            continue

        dq = notional_exec / exec_price
        var_cost = notional_exec * fee_rate
        fix_cost = costs.fixed_per_trade
        total_cost = var_cost + fix_cost

        cash -= (notional_exec + total_cost)
        qty[a] += dq

        trade_rows.append({
            "Date": first_dt.strftime("%Y-%m-%d"),
            "asset": a,
            "side": "BUY",
            "qty": dq,
            "price": exec_price,
            "notional": notional_exec,
            "fee_var": var_cost,
            "fee_fixed": fix_cost,
            "fee_total": total_cost,
        })

    def portfolio_value(prices_row: pd.Series) -> float:
        return cash + sum(qty[a] * float(prices_row[a]) for a in assets)

    for dt, prices in close.iterrows():
        prices = prices.astype(float)
        pv = portfolio_value(prices)

        row = {"Date": dt.strftime("%Y-%m-%d"), "equity": pv, "cash": cash}
        for a in assets:
            row[f"qty_{a}"] = qty[a]
            row[f"val_{a}"] = qty[a] * float(prices[a])
        equity_rows.append(row)

    return pd.DataFrame(equity_rows), pd.DataFrame(trade_rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Baseline B: buy&hold equal-weight with costs (single entry).")
    ap.add_argument("--panel", default="data/processed_sanitized/panel_close.csv", help="Panel close CSV")
    ap.add_argument("--initial", type=float, default=1000.0, help="Initial cash (paper)")
    ap.add_argument("--fee-bps", type=float, default=5.0, help="Variable fee in bps (default 5)")
    ap.add_argument("--slippage-bps", type=float, default=2.0, help="Slippage in bps (default 2)")
    ap.add_argument("--fixed", type=float, default=0.0, help="Fixed cost per trade/order")
    ap.add_argument("--out-equity", default="data/processed_sanitized/buyhold_equity.csv", help="Equity curve output CSV")
    ap.add_argument("--out-trades", default="data/processed_sanitized/buyhold_trades.csv", help="Trades output CSV")
    args = ap.parse_args()

    close = load_panel_close(Path(args.panel))
    costs = Costs(fee_bps=args.fee_bps, slippage_bps=args.slippage_bps, fixed_per_trade=args.fixed)

    equity, trades = simulate_buyhold_equal_weight(close, args.initial, costs)

    Path(args.out_equity).parent.mkdir(parents=True, exist_ok=True)
    equity.to_csv(args.out_equity, index=False)
    trades.to_csv(args.out_trades, index=False)

    s = summarize_equity(equity)
    print("BASELINE B (buy&hold, equal-weight, single entry)")
    print(f"assets={list(close.columns)}")
    print(f"costs: fee_bps={args.fee_bps} slippage_bps={args.slippage_bps} fixed={args.fixed}")
    print(f"start={s['start_equity']:.2f} end={s['end_equity']:.2f} years={s['years']:.2f}")
    print(f"CAGR={s['CAGR_pct']:.2f}%  Vol={s['Volatility_pct']:.2f}%  MaxDD={s['MaxDrawdown_pct']:.2f}%")
    print(f"saved: {args.out_equity}")
    print(f"saved: {args.out_trades}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

