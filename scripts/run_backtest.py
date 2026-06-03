#!/usr/bin/env python
"""CLI: run one strategy over a token + window and write a report.

Example:

    ./venv/bin/python scripts/run_backtest.py \\
        --symbol BNB/USDT --timeframe 1h \\
        --start 2024-01-01 --end 2024-04-01 \\
        --strategy momentum --risk

Network: fetches history via ccxt on a cache miss (Binance spot, no key).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

# Run-from-anywhere: put the repo root on the path so `import bnb_bot` works
# even though the package isn't pip-installed.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bnb_bot import config  # noqa: E402
from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.report import render_report  # noqa: E402
from bnb_bot.risk import RuleBasedRisk  # noqa: E402
from bnb_bot.strategy import (  # noqa: E402
    MeanReversion,
    MeanReversionParams,
    Momentum,
    MomentumParams,
)


def parse_date_ms(s: str) -> int:
    """``YYYY-MM-DD`` -> epoch ms at UTC midnight. Fail loud on bad input."""
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise SystemExit(f"bad date {s!r}; expected YYYY-MM-DD")
    return int(dt.timestamp() * 1000)


def build_strategy(name: str, args: argparse.Namespace):
    if name == "momentum":
        return Momentum(MomentumParams(fast_period=args.fast, slow_period=args.slow))
    if name == "mean_reversion":
        return MeanReversion(
            MeanReversionParams(
                lookback=args.lookback, entry_z=args.entry_z, exit_z=args.exit_z
            )
        )
    raise SystemExit(f"unknown strategy {name!r}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Run a bnb_bot backtest and write a report."
    )
    p.add_argument("--symbol", default="BNB/USDT")
    p.add_argument("--timeframe", default=config.DEFAULT_TIMEFRAME)
    p.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--end", required=True, help="YYYY-MM-DD (exclusive)")
    p.add_argument(
        "--strategy", choices=("momentum", "mean_reversion"), default="momentum"
    )
    p.add_argument("--risk", action="store_true", help="apply default risk rules")
    p.add_argument("--out", default="reports")
    p.add_argument("--no-plot", action="store_true")
    # strategy params (defaults mirror the param dataclasses)
    p.add_argument("--fast", type=int, default=12)
    p.add_argument("--slow", type=int, default=26)
    p.add_argument("--lookback", type=int, default=24)
    p.add_argument("--entry-z", dest="entry_z", type=float, default=1.0)
    p.add_argument("--exit-z", dest="exit_z", type=float, default=0.0)
    args = p.parse_args(argv)

    since = parse_date_ms(args.start)
    until = parse_date_ms(args.end)
    if until <= since:
        raise SystemExit("--end must be after --start")

    print(f"Loading {args.symbol} {args.timeframe} {args.start}..{args.end} ...")
    candles = load_or_fetch(args.symbol, args.timeframe, since, until)
    print(f"  {len(candles)} contiguous bars.")

    strat = build_strategy(args.strategy, args)
    risk = RuleBasedRisk() if args.risk else None

    result = run_backtest(
        candles,
        strat,
        symbol=args.symbol,
        risk=risk,
        strategy_name=strat.name,
        params=strat.params,
    )
    metrics = compute_metrics(result)
    caveats = []
    if args.risk:
        caveats.append(
            "Default risk rules active (sizing, stop-loss, drawdown breaker)."
        )
    md_path = render_report(
        result, metrics, out_dir=args.out, caveats=caveats, plot=not args.no_plot
    )

    print(f"\nReport: {md_path}")
    print(
        f"  return {metrics.total_return * 100:.2f}%  "
        f"maxDD {metrics.max_drawdown * 100:.2f}%  "
        f"Sharpe {metrics.sharpe:.2f}  trades {metrics.n_trades}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
