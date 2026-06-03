#!/usr/bin/env python
"""S3 — risk-adjusted evaluation: momentum+regime ± volatility targeting, risk-on.

Stage 2 found that the momentum+regime thread roughly matched buy-and-hold on BTC
at half the drawdown — promising risk-adjusted behaviour. This run tests that
thread properly, now that the drawdown breaker is fixed (S1) and volatility
targeting exists (S2). The question is NOT "does it beat hold on return" (it
won't in a bull market) but "does it deliver a better risk-adjusted profile —
lower drawdown, higher Calmar — consistently across unseen windows?"

Variants (all risk-on with the fixed breaker; stop-loss 10%, breaker 20%):
  * mom_regime         — regime-gated momentum (the Stage 2 standout)
  * mom_regime_voltgt  — the same, volatility-targeted (the headline candidate)
  * trend_voltgt       — volatility-targeted trend-following (a second candidate)

Scorecard leans on drawdown, Sharpe, and Calmar (return per unit drawdown).
Walk-forward reports both folds-beat-return AND folds-with-lower-drawdown.

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
from bnb_bot.report import render_report  # noqa: E402
from bnb_bot.risk import RuleBasedRisk  # noqa: E402
from bnb_bot.strategy import (  # noqa: E402
    Momentum,
    RegimeGated,
    TrendFollowing,
    TrendFollowingParams,
    VolatilityTargeted,
)
from bnb_bot.walkforward import buy_and_hold, walk_forward  # noqa: E402

WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"
TREND = 100
TARGET_VOL = 0.025  # per-bar (daily) volatility target ~ 40% annualized
VOL_LOOKBACK = 20
N_FOLDS = 5
OUT_DIR = "reports"

RISK = RuleBasedRisk(
    config.RiskLimits(
        max_position_frac=1.0,
        max_total_exposure=1.0,
        max_drawdown_halt=0.20,
        stop_loss_frac=0.10,
    )
)


def _mom_regime():
    return RegimeGated(Momentum(), trend_period=TREND)


def _mom_regime_voltgt():
    return VolatilityTargeted(
        RegimeGated(Momentum(), trend_period=TREND),
        target_vol=TARGET_VOL,
        lookback=VOL_LOOKBACK,
    )


def _trend_voltgt():
    return VolatilityTargeted(
        TrendFollowing(TrendFollowingParams(trend_period=TREND)),
        target_vol=TARGET_VOL,
        lookback=VOL_LOOKBACK,
    )


VARIANTS = {
    "mom_regime": _mom_regime,
    "mom_regime_voltgt": _mom_regime_voltgt,
    "trend_voltgt": _trend_voltgt,
}


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

        bh = compute_metrics(buy_and_hold(candles, symbol=symbol))
        print(
            f"  buy & hold        ret {_pct(bh.total_return):>8s}  "
            f"maxDD {_pct(bh.max_drawdown):>6s}  Sharpe {_ratio(bh.sharpe):>5s}  "
            f"Calmar {_ratio(bh.calmar):>5s}"
        )

        for vname, factory in VARIANTS.items():
            strat = factory()
            res = run_backtest(
                candles,
                strat,
                symbol=symbol,
                risk=RISK,
                strategy_name=strat.name,
                params=strat.params,
            )
            m = compute_metrics(res)
            render_report(
                res,
                m,
                out_dir=OUT_DIR,
                label="riskadj",
                caveats=[
                    "Daily, risk-on (fixed breaker + 10% stop). Risk-adjusted thread.",
                    f"Buy & hold: ret {_pct(bh.total_return)}, maxDD {_pct(bh.max_drawdown)}, "
                    f"Calmar {_ratio(bh.calmar)}.",
                ],
            )
            rows.append(
                {
                    "symbol": symbol,
                    "variant": vname,
                    "ret": m.total_return,
                    "bh_ret": bh.total_return,
                    "dd": m.max_drawdown,
                    "bh_dd": bh.max_drawdown,
                    "sharpe": m.sharpe,
                    "bh_sharpe": bh.sharpe,
                    "calmar": m.calmar,
                    "bh_calmar": bh.calmar,
                    "exp": m.exposure,
                    "trades": m.n_trades,
                }
            )

            folds = walk_forward(
                candles, factory, symbol=symbol, n_folds=N_FOLDS, risk=RISK
            )
            beat_ret = sum(f.beat_benchmark for f in folds)
            better_dd = sum(
                f.strategy_metrics.max_drawdown < f.benchmark_metrics.max_drawdown
                for f in folds
            )
            fold_rows.append(
                {
                    "symbol": symbol,
                    "variant": vname,
                    "beat_ret": beat_ret,
                    "better_dd": better_dd,
                    "n": len(folds),
                }
            )
            print(
                f"  {vname:18s} ret {_pct(m.total_return):>8s}  "
                f"maxDD {_pct(m.max_drawdown):>6s} (B&H {_pct(bh.max_drawdown)})  "
                f"Sharpe {_ratio(m.sharpe):>5s}  Calmar {_ratio(m.calmar):>5s}  "
                f"exp {_pct(m.exposure):>5s}  DD-wins {better_dd}/{len(folds)}"
            )

    _write_summary(rows, fold_rows, skipped)
    return 0


def _write_summary(rows, fold_rows, skipped) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    lines = [
        "# Risk-adjusted summary (S3)",
        "",
        f"Window **{WINDOW_START} → {WINDOW_END}**, **{TIMEFRAME}** bars, trend/regime "
        f"SMA **{TREND}**, vol target **{TARGET_VOL}/bar** over **{VOL_LOOKBACK}** bars, "
        f"walk-forward **{N_FOLDS} folds**.",
        "",
        "All variants **risk-on** with the fixed drawdown breaker (S1) + 10% "
        "stop-loss. The question is risk-*adjusted* quality (drawdown, Sharpe, "
        "Calmar), not raw return — a long-only strategy won't out-return a bull "
        "market. Every fill pays swap fee + slippage + gas; signals causal.",
        "",
        "## Full window vs buy & hold",
        "",
        "| Symbol | Variant | Return | B&H | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | Calmar | B&H Calmar | Exposure | Trades |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            f"| {r['symbol']} | {r['variant']} | {_pct(r['ret'])} | {_pct(r['bh_ret'])} | "
            f"{_pct(r['dd'])} | {_pct(r['bh_dd'])} | {_ratio(r['sharpe'])} | {_ratio(r['bh_sharpe'])} | "
            f"{_ratio(r['calmar'])} | {_ratio(r['bh_calmar'])} | {_pct(r['exp'])} | {r['trades']} |"
        )
    lines += [
        "",
        "## Walk-forward — consistency across unseen folds",
        "",
        "Drawdown-wins = folds where the strategy's max drawdown was *smaller* "
        "than buy-and-hold's (the risk-adjusted bet). Return-wins = folds where "
        "it out-returned hold.",
        "",
        "| Symbol | Variant | DD-wins | Return-wins |",
        "| --- | --- | ---: | ---: |",
    ]
    for r in fold_rows:
        lines.append(
            f"| {r['symbol']} | {r['variant']} | {r['better_dd']}/{r['n']} | "
            f"{r['beat_ret']}/{r['n']} |"
        )
    if skipped:
        lines += ["", "## Skipped (data gaps)", ""]
        for sym, reason in skipped:
            lines.append(f"- **{sym}**: {reason}")
    lines.append("")
    path = os.path.join(OUT_DIR, "risk_adjusted_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSummary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
