#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


@dataclass
class Paths:
    panel_close: Path
    panel_returns: Path
    baseline_equity: Path
    out_dir: Path


def max_drawdown(series: pd.Series) -> float:
    peak = series.cummax()
    dd = series / peak - 1.0
    return float(dd.min())


def rolling_vol(daily_returns: pd.Series, window: int = 63) -> pd.Series:
    # 63 ~ 3 měsíce obchodních dnů
    return daily_returns.rolling(window).std() * (252 ** 0.5)


def save_plot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate human-readable report + charts.")
    ap.add_argument("--panel-close", default="data/processed_sanitized/panel_close.csv")
    ap.add_argument("--panel-returns", default="data/processed_sanitized/panel_returns.csv")
    ap.add_argument("--baseline-equity", default="data/processed_sanitized/baseline_equity.csv")
    ap.add_argument("--out-dir", default=None, help="Output dir (default reports/daily/YYYY-MM-DD)")
    args = ap.parse_args()

    panel_close = Path(args.panel_close)
    panel_returns = Path(args.panel_returns)
    baseline_equity = Path(args.baseline_equity)

    # --- load ---
    close = pd.read_csv(panel_close, parse_dates=["Date"]).sort_values("Date").set_index("Date")
    rets = pd.read_csv(panel_returns, parse_dates=["Date"]).sort_values("Date").set_index("Date")

    eq = pd.read_csv(baseline_equity, parse_dates=["Date"]).sort_values("Date").set_index("Date")
    equity = eq["equity"].astype(float)

    asof = equity.index.max().strftime("%Y-%m-%d")
    out_dir = Path(args.out_dir) if args.out_dir else Path("reports/daily") / asof
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- market snapshot ---
    last_close = close.iloc[-1].to_dict()
    last_ret = rets.iloc[-1].to_dict()

    # baseline stats
    daily_eq_ret = equity.pct_change().dropna()
    years = (equity.index.max() - equity.index.min()).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    vol = float(daily_eq_ret.std() * (252 ** 0.5))
    mdd = max_drawdown(equity)

    market_summary = {
        "asof": asof,
        "assets": list(close.columns),
        "last_close": {k: float(v) for k, v in last_close.items()},
        "last_return": {k: float(v) for k, v in last_ret.items()},
    }

    baseline_summary = {
        "asof": asof,
        "start_equity": float(equity.iloc[0]),
        "end_equity": float(equity.iloc[-1]),
        "years": float(years),
        "cagr": float(cagr),
        "volatility": float(vol),
        "max_drawdown": float(mdd),
    }

    (out_dir / "market_summary.json").write_text(json.dumps(market_summary, indent=2), encoding="utf-8")
    (out_dir / "baseline_summary.json").write_text(json.dumps(baseline_summary, indent=2), encoding="utf-8")

    # --- charts ---
    plt.figure()
    equity.plot()
    plt.title("Baseline equity curve")
    plt.ylabel("Equity")
    save_plot(out_dir / "equity.png")

    dd = equity / equity.cummax() - 1.0
    plt.figure()
    dd.plot()
    plt.title("Drawdown")
    plt.ylabel("Drawdown")
    save_plot(out_dir / "drawdown.png")

    rv = rolling_vol(daily_eq_ret, window=63)
    plt.figure()
    rv.plot()
    plt.title("Rolling volatility (63d)")
    plt.ylabel("Volatility (annualized)")
    save_plot(out_dir / "rolling_vol.png")

    # --- markdown report (lidské čtení) ---
    md = []
    md.append(f"# market-lab daily report ({asof})\n")
    md.append("## Universe (7 assets)\n")
    md.append(", ".join(close.columns) + "\n")
    md.append("## Last day move\n")
    md.append(pd.Series(last_ret).sort_values(ascending=False).to_frame("return").to_markdown() + "\n")
    md.append("## Baseline (equal-weight monthly rebalance)\n")
    md.append(f"- End equity: **{baseline_summary['end_equity']:.2f}**\n")
    md.append(f"- CAGR: **{baseline_summary['cagr']*100:.2f}%**\n")
    md.append(f"- Volatility: **{baseline_summary['volatility']*100:.2f}%**\n")
    md.append(f"- Max drawdown: **{baseline_summary['max_drawdown']*100:.2f}%**\n")
    md.append("\n## Charts\n")
    md.append("- equity.png\n- drawdown.png\n- rolling_vol.png\n")
    (out_dir / "baseline_report.md").write_text("\n".join(md), encoding="utf-8")

    print(f"OK: report written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

