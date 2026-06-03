#!/usr/bin/env python
"""P1 — bounded parameter search for the vol-targeted regime-momentum entry.

Overfitting is the one thing our whole pitch is built against, so this search is
deliberately disciplined:

* **Untouched holdout.** Each token's most recent 25% is held out. The search
  ranks configs on the first 75% (train) ONLY. The single winner is scored on
  the holdout exactly once, at the end.
* **One config across all tokens.** We pick the parameter set that is best
  *aggregated across the four tokens*, never the best per token — cross-sectional
  robustness, not curve-fitting to each coin.
* **Risk-adjusted objective with a hard drawdown gate.** Among configs whose
  drawdown beats buy-and-hold on EVERY token (our core promise), rank by mean
  Sharpe across tokens.

Grid: target_vol × trend_period × vol_lookback × rebalance_band. Momentum is
left at its default (the search lever is risk/regime/vol sizing, not the signal).

Network: fetches daily history via ccxt on a cache miss (Binance spot, no key).
"""

from __future__ import annotations

import itertools
import os
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bnb_bot import config  # noqa: E402
from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.risk import RuleBasedRisk  # noqa: E402
from bnb_bot.strategy import Momentum, RegimeGated, VolatilityTargeted  # noqa: E402
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

WINDOW_START = "2021-01-01"
WINDOW_END = "2026-06-01"
TIMEFRAME = "1d"
TRAIN_FRAC = 0.75  # first 75% search; last 25% untouched holdout
OUT_DIR = "reports"

GRID = {
    "target_vol": [0.015, 0.02, 0.025, 0.03, 0.04],
    "trend_period": [50, 100, 150, 200],
    "vol_lookback": [15, 20, 30],
    "rebalance_band": [0.0, 0.03],
}

RISK = RuleBasedRisk(
    config.RiskLimits(
        max_position_frac=1.0,
        max_total_exposure=1.0,
        max_drawdown_halt=0.20,
        stop_loss_frac=0.10,
    )
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


def _make(cfg: dict):
    return VolatilityTargeted(
        RegimeGated(Momentum(), trend_period=cfg["trend_period"]),
        target_vol=cfg["target_vol"],
        lookback=cfg["vol_lookback"],
    )


def _evaluate(candles, symbol, cfg):
    """Risk-on metrics for one config on one candle segment."""
    res = run_backtest(
        candles,
        _make(cfg),
        symbol=symbol,
        risk=RISK,
        rebalance_band=cfg["rebalance_band"],
    )
    return compute_metrics(res)


def main() -> int:
    since, until = _ms(WINDOW_START), _ms(WINDOW_END)

    # Load + split each token once. train = search; holdout = untouched.
    data = {}
    for symbol in config.TOKEN_SET:
        try:
            candles = load_or_fetch(symbol, TIMEFRAME, since, until)
        except DataGapError as e:
            print(f"SKIP {symbol}: {e}")
            continue
        k = int(len(candles) * TRAIN_FRAC)
        data[symbol] = {
            "train": candles[:k],
            "holdout": candles[k:],
            "bh_train_dd": compute_metrics(
                buy_and_hold(candles[:k], symbol=symbol)
            ).max_drawdown,
        }
    symbols = list(data)
    print(
        f"{len(symbols)} tokens; train/holdout split {int(TRAIN_FRAC*100)}/"
        f"{int((1-TRAIN_FRAC)*100)}"
    )

    keys = list(GRID)
    combos = [dict(zip(keys, vals)) for vals in itertools.product(*GRID.values())]
    print(f"Searching {len(combos)} configs on TRAIN only ...")

    ranked = []
    for cfg in combos:
        per_token = {}
        all_dd_better = True
        for symbol in symbols:
            m = _evaluate(data[symbol]["train"], symbol, cfg)
            per_token[symbol] = m
            if not (m.max_drawdown < data[symbol]["bh_train_dd"]):
                all_dd_better = False
        mean_sharpe = statistics.mean(per_token[s].sharpe for s in symbols)
        mean_dd = statistics.mean(per_token[s].max_drawdown for s in symbols)
        ranked.append(
            {
                "cfg": cfg,
                "mean_sharpe": mean_sharpe,
                "mean_dd": mean_dd,
                "all_dd_better": all_dd_better,
            }
        )

    # Eligible = beats B&H drawdown on every token; rank by mean train Sharpe.
    eligible = [r for r in ranked if r["all_dd_better"]]
    pool = eligible if eligible else ranked
    pool.sort(key=lambda r: r["mean_sharpe"], reverse=True)
    winner = pool[0]
    print(f"\n{len(eligible)}/{len(ranked)} configs beat B&H drawdown on all tokens.")
    print(f"Winner (train): {winner['cfg']}  mean Sharpe {winner['mean_sharpe']:.3f}")

    # --- Validate the winner ONCE on the untouched holdout. ---
    holdout_rows = []
    for symbol in symbols:
        cfg = winner["cfg"]
        m = _evaluate(data[symbol]["holdout"], symbol, cfg)
        bh = compute_metrics(buy_and_hold(data[symbol]["holdout"], symbol=symbol))
        holdout_rows.append(
            {
                "symbol": symbol,
                "m": m,
                "bh": bh,
                "dd_better": m.max_drawdown < bh.max_drawdown,
            }
        )
        print(
            f"  HOLDOUT {symbol:10s} ret {_pct(m.total_return):>8s} "
            f"(B&H {_pct(bh.total_return):>8s})  maxDD {_pct(m.max_drawdown):>6s} "
            f"(B&H {_pct(bh.max_drawdown)})  Sharpe {_ratio(m.sharpe)} "
            f"(B&H {_ratio(bh.sharpe)})  DD-better {m.max_drawdown < bh.max_drawdown}"
        )

    _write_summary(pool, winner, holdout_rows, len(eligible), len(ranked))
    dd_wins = sum(r["dd_better"] for r in holdout_rows)
    print(f"\nHoldout: drawdown beaten on {dd_wins}/{len(holdout_rows)} tokens.")
    return 0


def _write_summary(pool, winner, holdout_rows, n_eligible, n_total) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    w = winner["cfg"]
    lines = [
        "# Parameter search summary (P1)",
        "",
        f"Window **{WINDOW_START} → {WINDOW_END}**, **{TIMEFRAME}** bars. "
        f"Train/holdout split **{int(TRAIN_FRAC*100)}/{int((1-TRAIN_FRAC)*100)}** "
        "per token; the search saw TRAIN only.",
        "",
        f"Searched **{n_total}** configs; **{n_eligible}** beat buy-and-hold "
        "drawdown on every token (the eligibility gate). Ranked by mean train "
        "Sharpe across tokens. One config chosen for all tokens (no per-token fit).",
        "",
        "## Winning config",
        "",
        f"- **target_vol**: {w['target_vol']}",
        f"- **trend_period**: {w['trend_period']}",
        f"- **vol_lookback**: {w['vol_lookback']}",
        f"- **rebalance_band**: {w['rebalance_band']}",
        f"- mean train Sharpe across tokens: **{winner['mean_sharpe']:.3f}**, "
        f"mean train drawdown: **{_pct(winner['mean_dd'])}**",
        "",
        "## Top configs (train) — plateau check",
        "",
        "| target_vol | trend | vol_lb | reb_band | mean Sharpe | mean DD |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in pool[:8]:
        c = r["cfg"]
        lines.append(
            f"| {c['target_vol']} | {c['trend_period']} | {c['vol_lookback']} | "
            f"{c['rebalance_band']} | {r['mean_sharpe']:.3f} | {_pct(r['mean_dd'])} |"
        )
    lines += [
        "",
        "## Holdout validation (untouched 25%) — winner only, scored once",
        "",
        "| Symbol | Return | B&H | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | Calmar | B&H Calmar | DD beaten |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    for r in holdout_rows:
        m, bh = r["m"], r["bh"]
        lines.append(
            f"| {r['symbol']} | {_pct(m.total_return)} | {_pct(bh.total_return)} | "
            f"{_pct(m.max_drawdown)} | {_pct(bh.max_drawdown)} | {_ratio(m.sharpe)} | "
            f"{_ratio(bh.sharpe)} | {_ratio(m.calmar)} | {_ratio(bh.calmar)} | "
            f"{'yes' if r['dd_better'] else 'NO'} |"
        )
    lines.append("")
    path = os.path.join(OUT_DIR, "search_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"Summary: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
