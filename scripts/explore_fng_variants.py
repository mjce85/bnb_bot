#!/usr/bin/env python
"""EXPLORATORY: how do different Fear & Greed gate directions behave?

Curiosity-driven sensitivity map (operator-requested), NOT a re-selection of the
entry. Compares the locked entry under four sentiment-gate variants:

  - no gate            (the locked entry)
  - cut in greed >=75  (risk-off at euphoric tops — the validated negative result)
  - cut in fear  <=25  (the INVERSE: risk-off at capitulation lows)
  - cut both extremes  (hold only in the calm 26-74 middle)

Reported full-window (2021->2026) on alternative.me F&G (covers the whole window),
per token and as a portfolio. Thresholds are the standard classification
boundaries, not tuned. We do NOT pick a winner here — picking the best-looking
variant on this data would be the overfitting our pitch rejects. It's a map.

    ./venv/bin/python scripts/explore_fng_variants.py  # -> reports/fear_greed_variants_summary.md
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
from bnb_bot.sentiment import load_fear_greed  # noqa: E402
from bnb_bot.strategy import FearGreedGated  # noqa: E402

WINDOW_START, WINDOW_END, TIMEFRAME, OUT_DIR = (
    "2021-01-01",
    "2026-06-01",
    "1d",
    "reports",
)

# (label, gate kwargs or None for no gate)
VARIANTS = [
    ("no gate", None),
    ("cut greed ≥75", dict(greed_threshold=75)),
    ("cut fear ≤25 (inverse)", dict(greed_threshold=None, fear_threshold=25)),
    ("cut both extremes", dict(greed_threshold=75, fear_threshold=25)),
]


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


def _build(fng, kwargs):
    base = ENTRY.build_strategy()
    return base if kwargs is None else FearGreedGated(base, fng, **kwargs)


def _single(candles, symbol, fng, kwargs):
    res = run_backtest(
        candles,
        _build(fng, kwargs),
        symbol=symbol,
        risk=ENTRY.build_risk(),
        rebalance_band=ENTRY.rebalance_band,
        strategy_name="explore",
    )
    return compute_metrics(res)


def _portfolio(cbs, fng, kwargs):
    res = run_portfolio_backtest(
        cbs,
        lambda sym: _build(fng, kwargs),
        risk=ENTRY.build_risk(),
        max_total_exposure=ENTRY.risk_limits.max_total_exposure,
        rebalance_band=ENTRY.rebalance_band,
    )
    return compute_metrics(res)


def main() -> int:
    lo, hi = _ms(WINDOW_START), _ms(WINDOW_END)
    fng = load_fear_greed("alternative")

    cbs = {}
    for symbol in config.TOKEN_SET:
        try:
            cbs[symbol] = load_or_fetch(symbol, TIMEFRAME, lo, hi)
        except DataGapError as e:
            print(f"SKIP {symbol}: {e}")

    lines = [
        "# Fear & Greed gate — directional sensitivity (EXPLORATORY)",
        "",
        "Operator-requested curiosity map, **not** a re-selection of the entry. "
        "Full window 2021→2026, alternative.me F&G, standard classification "
        "boundaries (75 / 25), no tuning. We deliberately do not pick a winner.",
        "",
    ]

    # Portfolio (decision-relevant view) first.
    print("Portfolio (full window, alternative.me F&G):")
    lines += [
        "## Portfolio (what you'd actually run)",
        "",
        "| Variant | Return | MaxDD | Sharpe | Calmar |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label, kw in VARIANTS:
        m = _portfolio(cbs, fng, kw)
        lines.append(
            f"| {label} | {_pct(m.total_return)} | {_pct(m.max_drawdown)} | "
            f"{_ratio(m.sharpe)} | {_ratio(m.calmar)} |"
        )
        print(
            f"  {label:24s} ret {_pct(m.total_return):>8s}  maxDD {_pct(m.max_drawdown):>6s}  "
            f"Sharpe {_ratio(m.sharpe)}  Calmar {_ratio(m.calmar)}"
        )
    hold = compute_metrics(buy_and_hold_portfolio(cbs))
    lines.append(
        f"| equal-weight hold | {_pct(hold.total_return)} | {_pct(hold.max_drawdown)} | "
        f"{_ratio(hold.sharpe)} | {_ratio(hold.calmar)} |"
    )
    lines.append("")

    # Per token.
    print("\nPer token (Calmar, full window):")
    lines += [
        "## Per token — Calmar by variant",
        "",
        "| Token | " + " | ".join(lbl for lbl, _ in VARIANTS) + " |",
        "| --- | " + " | ".join("---:" for _ in VARIANTS) + " |",
    ]
    for symbol, candles in cbs.items():
        cells = []
        for _, kw in VARIANTS:
            cells.append(_ratio(_single(candles, symbol, fng, kw).calmar))
        lines.append(f"| {symbol} | " + " | ".join(cells) + " |")
        print(f"  {symbol:9s} " + "  ".join(f"{c:>6s}" for c in cells))
    lines.append("")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "fear_greed_variants_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSummary: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
