#!/usr/bin/env python
"""Stage 6 — robustness hardening of the locked entry. No tuning, just stress.

Two tests that attack our two weakest honesty caveats:

* **Cost sensitivity** — re-run the entry as a portfolio (and per-token) at
  1x/2x/3x fees+slippage+gas. The strategy trades a lot (vol targeting), so it's
  punished harder by higher costs than buy-and-hold (which trades once). Shows
  how much edge survives realistic on-chain costs.
* **Out-of-universe generalization** — run the FROZEN entry on liquid tokens that
  were never in the parameter search. If drawdown control holds on coins the
  config never saw, it isn't overfit to the original four.

Writes reports/robustness_summary.md. Network: ccxt on a cache miss.
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
from bnb_bot.portfolio import (
    buy_and_hold_portfolio,
    run_portfolio_backtest,
)  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"
OUT_DIR = "reports"
COST_MULTS = [1, 2, 3]

# Liquid tokens NOT used to pick the entry's parameters (out-of-universe).
EXTRA_TOKENS = (
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "LINK/USDT",
    "DOT/USDT",
    "LTC/USDT",
    "TRX/USDT",
    "AVAX/USDT",
)


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


def _scaled_costs(k: float) -> config.CostModel:
    base = config.DEFAULT_COSTS
    return config.CostModel(
        swap_fee=base.swap_fee * k,
        slippage_bps=base.slippage_bps * k,
        gas_usd=base.gas_usd * k,
    )


def _portfolio(cbs, costs):
    return run_portfolio_backtest(
        cbs,
        lambda sym: ENTRY.build_strategy(),
        risk=ENTRY.build_risk(),
        max_total_exposure=ENTRY.risk_limits.max_total_exposure,
        rebalance_band=ENTRY.rebalance_band,
        costs=costs,
    )


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)

    cbs = {}
    for symbol in config.TOKEN_SET:
        try:
            cbs[symbol] = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"SKIP base {symbol}: {e}")

    # --- 1. Cost sensitivity (portfolio) ---
    print("=== Cost sensitivity (portfolio vs equal-weight hold) ===")
    cost_rows = []
    for k in COST_MULTS:
        costs = _scaled_costs(k)
        m = compute_metrics(_portfolio(cbs, costs))
        bm = compute_metrics(buy_and_hold_portfolio(cbs, costs=costs))
        cost_rows.append({"k": k, "m": m, "bm": bm})
        print(
            f"  {k}x costs: strat ret {_pct(m.total_return):>8s} maxDD {_pct(m.max_drawdown):>6s} "
            f"Calmar {_ratio(m.calmar):>5s}  |  hold ret {_pct(bm.total_return):>7s} "
            f"maxDD {_pct(bm.max_drawdown)}"
        )

    # --- 2. Out-of-universe generalization (per token, default costs) ---
    print("\n=== Out-of-universe (frozen entry on unseen tokens) ===")
    oou_rows = []
    for symbol in EXTRA_TOKENS:
        try:
            candles = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"  SKIP {symbol}: {e}")
            continue
        res = run_backtest(
            candles,
            ENTRY.build_strategy(),
            symbol=symbol,
            risk=ENTRY.build_risk(),
            rebalance_band=ENTRY.rebalance_band,
        )
        m = compute_metrics(res)
        bh = compute_metrics(buy_and_hold(candles, symbol=symbol))
        oou_rows.append(
            {
                "symbol": symbol,
                "m": m,
                "bh": bh,
                "dd_better": m.max_drawdown < bh.max_drawdown,
            }
        )
        print(
            f"  {symbol:10s} ret {_pct(m.total_return):>8s} (hold {_pct(bh.total_return):>8s})  "
            f"maxDD {_pct(m.max_drawdown):>6s} (hold {_pct(bh.max_drawdown)})  "
            f"DD-better {m.max_drawdown < bh.max_drawdown}"
        )

    dd_wins = sum(r["dd_better"] for r in oou_rows)
    print(
        f"\nOut-of-universe: drawdown beaten on {dd_wins}/{len(oou_rows)} unseen tokens."
    )
    _write_summary(cost_rows, oou_rows, dd_wins)
    return 0


def _write_summary(cost_rows, oou_rows, dd_wins) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    lines = [
        "# Robustness summary (Stage 6)",
        "",
        f"Locked entry **{ENTRY.name}**, daily, {WINDOW_START} → {WINDOW_END}. No "
        "parameter tuning — these are stress tests of the frozen config.",
        "",
        "## 1. Cost sensitivity — portfolio vs equal-weight buy & hold",
        "",
        "Base costs: 0.25% swap + 10 bps slippage + $0.30 gas, scaled 1–3×. The "
        "strategy trades far more than holding, so higher costs hit it harder — "
        "this shows how much edge survives.",
        "",
        "| Costs | Strat return | Strat MaxDD | Strat Calmar | Hold return | Hold MaxDD |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in cost_rows:
        m, bm = r["m"], r["bm"]
        lines.append(
            f"| {r['k']}× | {_pct(m.total_return)} | {_pct(m.max_drawdown)} | "
            f"{_ratio(m.calmar)} | {_pct(bm.total_return)} | {_pct(bm.max_drawdown)} |"
        )
    lines += [
        "",
        "## 2. Out-of-universe — frozen entry on tokens it was never searched on",
        "",
        f"Drawdown beaten on **{dd_wins}/{len(oou_rows)}** unseen tokens. The entry's "
        "parameters were chosen on BNB/CAKE/ETH/BTC only; holding the drawdown edge "
        "on coins it never saw is evidence it isn't curve-fit to the original four.",
        "",
        "| Token | Return | B&H | MaxDD | B&H MaxDD | Calmar | B&H Calmar | DD beaten |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for r in oou_rows:
        m, bh = r["m"], r["bh"]
        lines.append(
            f"| {r['symbol']} | {_pct(m.total_return)} | {_pct(bh.total_return)} | "
            f"{_pct(m.max_drawdown)} | {_pct(bh.max_drawdown)} | {_ratio(m.calmar)} | "
            f"{_ratio(bh.calmar)} | {'yes' if r['dd_better'] else 'NO'} |"
        )
    lines.append("")
    path = os.path.join(OUT_DIR, "robustness_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Summary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
