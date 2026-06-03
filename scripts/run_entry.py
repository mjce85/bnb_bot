#!/usr/bin/env python
"""One-command reproduction of the submission entry.

Runs the locked, search-validated preset
(:data:`bnb_bot.presets.VOL_TARGETED_REGIME_MOMENTUM`) over the token set on
daily bars, writes a per-token report plus a consolidated
``reports/entry_summary.md`` comparing the strategy to buy-and-hold.

    ./venv/bin/python scripts/run_entry.py

Network: fetches daily history via ccxt on a cache miss (Binance spot, no key).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bnb_bot import config  # noqa: E402
from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.report import render_report  # noqa: E402
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"
OUT_DIR = "reports"


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _ratio(x: float) -> str:
    if x in (float("inf"), float("-inf")):
        return "+inf" if x > 0 else "-inf"
    return f"{x:.2f}"


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)
    rows = []
    print(f"Entry preset: {ENTRY.name}")
    print(
        f"  target_vol={ENTRY.target_vol} trend_period={ENTRY.trend_period} "
        f"vol_lookback={ENTRY.vol_lookback} rebalance_band={ENTRY.rebalance_band}"
    )

    for symbol in config.TOKEN_SET:
        try:
            candles = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"SKIP {symbol}: {e}")
            continue

        res = run_backtest(
            candles,
            ENTRY.build_strategy(),
            symbol=symbol,
            risk=ENTRY.build_risk(),
            rebalance_band=ENTRY.rebalance_band,
            strategy_name=ENTRY.name,
            params={
                "target_vol": ENTRY.target_vol,
                "trend_period": ENTRY.trend_period,
                "vol_lookback": ENTRY.vol_lookback,
                "rebalance_band": ENTRY.rebalance_band,
            },
        )
        m = compute_metrics(res)
        bh = compute_metrics(buy_and_hold(candles, symbol=symbol))
        render_report(
            res,
            m,
            out_dir=OUT_DIR,
            label="entry",
            caveats=[
                f"Locked entry preset '{ENTRY.name}', daily bars, risk-on.",
                f"Buy & hold: ret {_pct(bh.total_return)}, maxDD {_pct(bh.max_drawdown)}, "
                f"Calmar {_ratio(bh.calmar)}.",
            ],
        )
        rows.append({"symbol": symbol, "m": m, "bh": bh})
        print(
            f"  {symbol:10s} ret {_pct(m.total_return):>8s} (B&H {_pct(bh.total_return):>8s})  "
            f"maxDD {_pct(m.max_drawdown):>6s} (B&H {_pct(bh.max_drawdown)})  "
            f"Sharpe {_ratio(m.sharpe)}  Calmar {_ratio(m.calmar)}"
        )

    _write_summary(rows)
    return 0


def _write_summary(rows) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    lines = [
        "# Entry summary — locked submission strategy",
        "",
        f"Preset **{ENTRY.name}**: volatility-targeted, regime-gated momentum.",
        "",
        f"- target_vol **{ENTRY.target_vol}**/bar, trend SMA **{ENTRY.trend_period}**, "
        f"vol lookback **{ENTRY.vol_lookback}**, rebalance band **{ENTRY.rebalance_band}**",
        f"- risk: position cap {_pct(ENTRY.risk_limits.max_position_frac)}, stop-loss "
        f"{_pct(ENTRY.risk_limits.stop_loss_frac)}, drawdown breaker "
        f"{_pct(ENTRY.risk_limits.max_drawdown_halt)}",
        f"- window **{WINDOW_START} → {WINDOW_END}**, **{TIMEFRAME}** bars; every fill "
        "pays swap fee + slippage + gas; signals causal (no look-ahead).",
        "",
        "| Symbol | Return | B&H | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | Calmar | B&H Calmar |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        m, bh = r["m"], r["bh"]
        lines.append(
            f"| {r['symbol']} | {_pct(m.total_return)} | {_pct(bh.total_return)} | "
            f"{_pct(m.max_drawdown)} | {_pct(bh.max_drawdown)} | {_ratio(m.sharpe)} | "
            f"{_ratio(bh.sharpe)} | {_ratio(m.calmar)} | {_ratio(bh.calmar)} |"
        )
    lines.append("")
    path = os.path.join(OUT_DIR, "entry_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSummary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
