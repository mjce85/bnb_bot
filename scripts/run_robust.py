#!/usr/bin/env python
"""R3 robust baseline — daily bars, regime-aware strategies, walk-forward.

Headline read is risk-off; the risk overlay is run only to expose a breaker bug.

The Stage-1 probe showed hourly long-only baselines bleed fees and fight
downtrends. This run applies the three fixes at once and asks, honestly, whether
anything survives:

* **Daily bars** over ~5 years (2021->2026) — spans a bull, a bear, a recovery.
* **Regime-aware strategies** — a plain trend-follower plus regime-gated momentum
  and mean-reversion, all of which sit in cash during downtrends.
The strategy-edge read is **risk-off** (raw signal). We *also* run each strategy
risk-on and report only its exposure/trades, because the drawdown breaker has a
discovered lockout flaw (see below) that would otherwise contaminate the
returns. Surfacing the collapse in the table is the honest way to show it.

**KNOWN ISSUE — drawdown-breaker lockout.** The breaker halts new entries while
equity is >=20% below its peak. But once a strategy is forced into cash during a
drawdown, the cash balance is frozen and can never reclaim the old peak, so the
breaker stays tripped *permanently* — exposure collapses to ~2% and the strategy
makes ~3 trades over five years. Trend strategies are most exposed because they
sit in cash exactly during the downtrends that cause drawdowns. The breaker's
peak reference needs to reset (e.g. when the book goes flat) — a risk-semantics
decision flagged for the operator, not patched here.

Every strategy is scored full-window AND across 5 walk-forward folds, each
against buy-and-hold. Output: per-run reports + reports/robust_summary.md.

Network: fetches daily history via ccxt on a cache miss (Binance spot, no key).
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
from bnb_bot.report import render_report  # noqa: E402
from bnb_bot.risk import RuleBasedRisk  # noqa: E402
from bnb_bot.strategy import (  # noqa: E402
    MeanReversion,
    Momentum,
    RegimeGated,
    TrendFollowing,
    TrendFollowingParams,
)
from bnb_bot.walkforward import buy_and_hold, walk_forward  # noqa: E402

WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"  # exclusive
TIMEFRAME = "1d"
TREND = 100  # SMA lookback for trend filter / regime gate (daily bars)
N_FOLDS = 5
OUT_DIR = "reports"

# Risk overlay used ONLY to expose the breaker-lockout artifact (exposure/trades).
# The headline strategy read is risk-off. Single-asset limits: full allocation
# allowed, stop-loss + drawdown breaker on.
RISK = RuleBasedRisk(
    config.RiskLimits(
        max_position_frac=1.0,
        max_total_exposure=1.0,
        max_drawdown_halt=0.20,
        stop_loss_frac=0.10,
    )
)

# Fresh instance per call (stateful strategies + per-fold isolation).
STRATEGIES = {
    "trend_following": lambda: TrendFollowing(TrendFollowingParams(trend_period=TREND)),
    "momentum_regime": lambda: RegimeGated(Momentum(), trend_period=TREND),
    "meanrev_regime": lambda: RegimeGated(MeanReversion(), trend_period=TREND),
}


def _ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _ratio(x: float) -> str:
    if x in (float("inf"), float("-inf")):
        return "+inf" if x > 0 else "-inf"
    return f"{x:.2f}"


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)
    full_rows = []
    fold_rows = []
    skipped = []

    for symbol in config.TOKEN_SET:
        print(f"\n=== {symbol} ===")
        try:
            candles = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"  SKIPPED: {e}")
            skipped.append((symbol, str(e)))
            continue
        print(
            f"  {len(candles)} daily bars "
            f"({datetime.fromtimestamp(candles[0].ts/1000, tz=timezone.utc):%Y-%m-%d}"
            f" -> {datetime.fromtimestamp(candles[-1].ts/1000, tz=timezone.utc):%Y-%m-%d})"
        )

        bh_full = compute_metrics(buy_and_hold(candles, symbol=symbol))

        for sname, factory in STRATEGIES.items():
            # Full-window, RISK-OFF — the honest strategy-edge read.
            strat = factory()
            res = run_backtest(
                candles,
                strat,
                symbol=symbol,
                strategy_name=strat.name,
                params=strat.params,
            )
            m = compute_metrics(res)
            render_report(
                res,
                m,
                out_dir=OUT_DIR,
                label="robust",
                caveats=[
                    "Daily bars, full window, risk-off (raw signal).",
                    f"Buy & hold over same window: return {_pct(bh_full.total_return)}, "
                    f"maxDD {_pct(bh_full.max_drawdown)}.",
                ],
            )

            # Same strategy RISK-ON — captured only to expose the breaker lockout.
            res_on = run_backtest(
                candles, factory(), symbol=symbol, risk=RISK, strategy_name=strat.name
            )
            m_on = compute_metrics(res_on)

            full_rows.append(
                {
                    "symbol": symbol,
                    "strategy": sname,
                    "ret": m.total_return,
                    "bh_ret": bh_full.total_return,
                    "excess": m.total_return - bh_full.total_return,
                    "dd": m.max_drawdown,
                    "bh_dd": bh_full.max_drawdown,
                    "sharpe": m.sharpe,
                    "trades": m.n_trades,
                    "exp": m.exposure,
                    "exp_on": m_on.exposure,
                    "trades_on": m_on.n_trades,
                }
            )

            # Walk-forward folds, RISK-OFF.
            folds = walk_forward(candles, factory, symbol=symbol, n_folds=N_FOLDS)
            beat = sum(f.beat_benchmark for f in folds)
            excesses = [f.excess_return for f in folds]
            fold_rows.append(
                {
                    "symbol": symbol,
                    "strategy": sname,
                    "beat": beat,
                    "n": len(folds),
                    "mean_excess": statistics.mean(excesses),
                    "excesses": excesses,
                }
            )
            print(
                f"  {sname:16s} ret {_pct(m.total_return):>7s} "
                f"(B&H {_pct(bh_full.total_return):>7s}, excess {_pct(m.total_return - bh_full.total_return):>8s})  "
                f"maxDD {_pct(m.max_drawdown):>6s} (B&H {_pct(bh_full.max_drawdown):>5s})  "
                f"exp {_pct(m.exposure):>5s}  folds {beat}/{len(folds)}  "
                f"[risk-on exp {_pct(m_on.exposure)}/{m_on.n_trades}t]"
            )

    _write_summary(full_rows, fold_rows, skipped)
    return 0


def _write_summary(full_rows, fold_rows, skipped) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    lines = [
        "# Robust redesign summary (R3)",
        "",
        f"Window **{WINDOW_START} → {WINDOW_END}**, **{TIMEFRAME}** bars, "
        f"trend filter SMA **{TREND}**, walk-forward **{N_FOLDS} folds**.",
        "",
        "Headline numbers are **risk-off** (raw signal). Every fill pays swap fee "
        "+ slippage + gas; signals are causal. The last two columns show the same "
        "strategy **risk-on**, included only to expose the breaker-lockout bug "
        "(see note at bottom): exposure collapses to ~2% and trades to ~3.",
        "",
        "## Full window — strategy vs buy & hold (risk-off)",
        "",
        "| Symbol | Strategy | Return | B&H | Excess | MaxDD | B&H MaxDD | Sharpe | Exposure | Trades | RiskOn Exp | RiskOn Trades |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in full_rows:
        lines.append(
            f"| {r['symbol']} | {r['strategy']} | {_pct(r['ret'])} | {_pct(r['bh_ret'])} | "
            f"{_pct(r['excess'])} | {_pct(r['dd'])} | {_pct(r['bh_dd'])} | "
            f"{_ratio(r['sharpe'])} | {_pct(r['exp'])} | {r['trades']} | "
            f"{_pct(r['exp_on'])} | {r['trades_on']} |"
        )
    lines += [
        "",
        "## Walk-forward — folds that beat buy & hold",
        "",
        "| Symbol | Strategy | Folds beaten | Mean excess/fold | Per-fold excess |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for r in fold_rows:
        per = ", ".join(_pct(x) for x in r["excesses"])
        lines.append(
            f"| {r['symbol']} | {r['strategy']} | {r['beat']}/{r['n']} | "
            f"{_pct(r['mean_excess'])} | {per} |"
        )
    lines += [
        "",
        "## KNOWN ISSUE — drawdown-breaker lockout",
        "",
        "The `RiskOn Exp` / `RiskOn Trades` columns above show the bug: with the "
        "drawdown breaker active, exposure collapses to ~2% and trades to ~3 over "
        "five years. Cause: the breaker halts new entries while equity is >=20% "
        "below its peak, but once a strategy is forced into cash during a drawdown "
        "its cash balance is frozen and can never reclaim the old peak — so the "
        "breaker stays tripped permanently. The peak reference must reset (e.g. "
        "when the book goes flat). This is a risk-semantics decision for the "
        "operator; the headline numbers are risk-off so they are not affected.",
    ]
    if skipped:
        lines += ["", "## Skipped (data gaps)", ""]
        for sym, reason in skipped:
            lines.append(f"- **{sym}**: {reason}")
    lines.append("")
    path = os.path.join(OUT_DIR, "robust_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSummary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
