#!/usr/bin/env python
"""Disciplined validation of the A/B lead: a slower (let-winners-run) exit.

The tournament (Stage 12) showed the entry exits trends early. This tests the ONE
mechanistic fix it pointed to, with NO new/tuned parameters: keep the entry exactly
as-is but swap its symmetric regime gate (:class:`RegimeGated`) for an asymmetric
:class:`StickyExit` — same EMA-12/26 base, same 50-day SMA, same vol target 0.015 /
lookback 15 — so the position is held until the 50-day trend breaks instead of
bailing on a fast-EMA flip.

Held to the entry's own evidence bar: the 18-token generalization set (full history,
never used to fit anything) + the 4-token portfolio, full window and recent holdout
tail. Question: does letting winners run recover return WITHOUT wrecking the
drawdown control that is our actual edge?

    ./venv/bin/python scripts/validate_slow_exit.py  # -> reports/slow_exit_validation_summary.md
"""

from __future__ import annotations

import os
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bnb_bot import config  # noqa: E402
from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.portfolio import (  # noqa: E402
    PortfolioResult,
    buy_and_hold_portfolio,
    run_portfolio_backtest,
)
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.strategy import Momentum, StickyExit, VolatilityTargeted  # noqa: E402
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

GEN_START, PF_START, WINDOW_END = "2017-01-01", "2021-01-01", "2026-06-01"
TIMEFRAME, OUT_DIR, HOLDOUT_FRAC = "1d", "reports", 0.25
TOKENS = (
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "CAKE/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "LINK/USDT",
    "DOT/USDT",
    "LTC/USDT",
    "TRX/USDT",
    "AVAX/USDT",
    "ATOM/USDT",
    "XLM/USDT",
    "ETC/USDT",
    "EOS/USDT",
    "BCH/USDT",
    "FIL/USDT",
)


def _ms(s):
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _pct(x):
    return f"{x * 100:.1f}%"


def _ratio(x):
    if x in (float("inf"), float("-inf")):
        return "+inf" if x > 0 else "-inf"
    return f"{x:.2f}"


def _variant():
    """Entry, but with a sticky (trend-break) exit instead of the regime gate."""
    return VolatilityTargeted(
        StickyExit(Momentum(), trend_period=ENTRY.trend_period),
        target_vol=ENTRY.target_vol,
        lookback=ENTRY.vol_lookback,
    )


def _single(candles, sym, make):
    res = run_backtest(
        candles,
        make(),
        symbol=sym,
        risk=ENTRY.build_risk(),
        rebalance_band=ENTRY.rebalance_band,
        strategy_name="slowexit",
    )
    return compute_metrics(res)


def _tail(curve):
    return curve[int(len(curve) * (1.0 - HOLDOUT_FRAC)) :]


def _metrics_of(curve):
    return compute_metrics(
        PortfolioResult(
            symbols=[],
            window=(curve[0][0], curve[-1][0]),
            equity_curve=list(curve),
            fills=[],
        )
    )


def main() -> int:
    gen_lo, pf_lo, hi = _ms(GEN_START), _ms(PF_START), _ms(WINDOW_END)
    lines = [
        "# Slow-exit (let-winners-run) — disciplined validation of the A/B lead",
        "",
        "Entry with `StickyExit` (hold until the 50-day trend breaks) vs the locked "
        "entry (`RegimeGated`, exits on fast-EMA flip). Same EMA-12/26, same SMA-50, "
        "same vol target 0.015 / lookback 15 — **no new or tuned parameters.**",
        "",
    ]

    # --- 18-token generalization (full history) ---
    print("Generalization (full history, ENTRY vs SLOW-EXIT vs hold):")
    rows = []
    for sym in TOKENS:
        try:
            candles = load_or_fetch(sym, TIMEFRAME, gen_lo, hi)
        except DataGapError as e:
            print(f"  SKIP {sym}: {e}")
            continue
        e = _single(candles, sym, ENTRY.build_strategy)
        v = _single(candles, sym, _variant)
        h = compute_metrics(buy_and_hold(candles, symbol=sym))
        rows.append((sym, e, v, h))
        print(
            f"  {sym:10s} ENTRY ret {_pct(e.total_return):>8s} DD {_pct(e.max_drawdown):>6s} | "
            f"SLOW ret {_pct(v.total_return):>8s} DD {_pct(v.max_drawdown):>6s} | "
            f"hold ret {_pct(h.total_return):>8s}"
        )

    n = len(rows)
    v_beats_e_ret = sum(v.total_return > e.total_return for _, e, v, _ in rows)
    v_dd_beats_hold = sum(v.max_drawdown < h.max_drawdown for _, _, v, h in rows)
    e_dd_beats_hold = sum(e.max_drawdown < h.max_drawdown for _, e, _, h in rows)
    avg_ret_e = statistics.mean(e.total_return for _, e, _, _ in rows)
    avg_ret_v = statistics.mean(v.total_return for _, _, v, _ in rows)
    avg_dd_e = statistics.mean(e.max_drawdown for _, e, _, _ in rows)
    avg_dd_v = statistics.mean(v.max_drawdown for _, _, v, _ in rows)

    print(
        f"\n  SLOW-EXIT beats ENTRY on return: {v_beats_e_ret}/{n} tokens. "
        f"DD beats hold: SLOW {v_dd_beats_hold}/{n} vs ENTRY {e_dd_beats_hold}/{n}."
    )
    print(
        f"  avg return ENTRY {_pct(avg_ret_e)} -> SLOW {_pct(avg_ret_v)}; "
        f"avg maxDD ENTRY {_pct(avg_dd_e)} -> SLOW {_pct(avg_dd_v)}"
    )

    lines += [
        f"## 18-token generalization ({GEN_START}+, full history)",
        "",
        f"- **SLOW-EXIT beats ENTRY on return on {v_beats_e_ret}/{n} tokens.**",
        f"- Drawdown beaten vs hold: **SLOW {v_dd_beats_hold}/{n}**, ENTRY "
        f"{e_dd_beats_hold}/{n} (does the slower exit keep the risk edge?).",
        f"- Average return: ENTRY {_pct(avg_ret_e)} → **SLOW {_pct(avg_ret_v)}**; "
        f"average maxDD: ENTRY {_pct(avg_dd_e)} → **SLOW {_pct(avg_dd_v)}**.",
        "",
        "| Token | ENTRY ret/DD | SLOW ret/DD | hold ret/DD |",
        "| --- | --- | --- | --- |",
    ]
    for sym, e, v, h in rows:
        lines.append(
            f"| {sym} | {_pct(e.total_return)}/{_pct(e.max_drawdown)} | "
            f"{_pct(v.total_return)}/{_pct(v.max_drawdown)} | "
            f"{_pct(h.total_return)}/{_pct(h.max_drawdown)} |"
        )
    lines.append("")

    # --- 4-token portfolio: full + holdout tail ---
    print("\nPortfolio (4 tokens):")
    cbs = {}
    for sym in config.TOKEN_SET:
        try:
            cbs[sym] = load_or_fetch(sym, TIMEFRAME, pf_lo, hi)
        except DataGapError as e:
            print(f"  SKIP {sym}: {e}")

    def _pf(make):
        return run_portfolio_backtest(
            cbs,
            lambda s: make(),
            risk=ENTRY.build_risk(),
            max_total_exposure=1.0,
            rebalance_band=ENTRY.rebalance_band,
        )

    pf_e, pf_v = _pf(ENTRY.build_strategy), _pf(_variant)
    pf_h = buy_and_hold_portfolio(cbs)

    lines += [
        "## 4-token portfolio",
        "",
        "| Variant | Window | Return | MaxDD | Sharpe | Calmar |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for label, res in (("ENTRY", pf_e), ("SLOW-EXIT", pf_v), ("hold", pf_h)):
        mf = compute_metrics(res)
        mt = _metrics_of(_tail(res.equity_curve))
        for win, m in (("full", mf), ("holdout", mt)):
            lines.append(
                f"| {label} | {win} | {_pct(m.total_return)} | {_pct(m.max_drawdown)} "
                f"| {_ratio(m.sharpe)} | {_ratio(m.calmar)} |"
            )
        print(
            f"  {label:10s} full ret {_pct(mf.total_return):>8s} DD {_pct(mf.max_drawdown):>6s} "
            f"Calmar {_ratio(mf.calmar)} | holdout ret {_pct(mt.total_return):>7s} DD {_pct(mt.max_drawdown):>6s}"
        )
    lines.append("")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "slow_exit_validation_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSummary: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
