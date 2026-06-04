#!/usr/bin/env python
"""Sensitivity sweep — trend window x MACD setting, on the holdout only.

Answers "why 50-SMA and not 20/30/200? why MACD 12/26?" by sweeping those two
dimensions (everything else at the locked entry's values) and scoring on the
untouched last-25% holdout — per asset (all tokens) AND on the 4-token portfolio.

IMPORTANT: this is a *sensitivity map*, not a re-selection. Picking the best
config by its holdout score would overfit the holdout. We read it to see whether
the locked choice (50, 12/26) sits on a stable plateau or is clearly dominated.

Writes reports/param_sweep_summary.md and docs/param_sweep.png. Network: ccxt.
"""

from __future__ import annotations

import os
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bnb_bot import config  # noqa: E402
from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.metrics import compute_metrics  # noqa: E402
from bnb_bot.portfolio import (
    buy_and_hold_portfolio,
    run_portfolio_backtest,
)  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.strategy import (  # noqa: E402
    Momentum,
    MomentumParams,
    RegimeGated,
    VolatilityTargeted,
)
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

TIMEFRAME = "1d"
HOLDOUT_FRAC = 0.25
MIN_BARS = 120

TREND_VALUES = [20, 30, 50, 100, 200]
MACD_VALUES = [(8, 21), (12, 26), (19, 39)]
LOCKED = (ENTRY.trend_period, 12, 26)  # 50, 12, 26

ALL_TOKENS = (
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
PORTFOLIO_TOKENS = config.TOKEN_SET  # the 4-token product portfolio

RISK = ENTRY.build_risk()
BAND = ENTRY.rebalance_band


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _ratio(x):
    if x in (float("inf"), float("-inf")):
        return "+inf" if x > 0 else "-inf"
    return f"{x:.2f}"


def _make(trend, fast, slow):
    return VolatilityTargeted(
        RegimeGated(Momentum(MomentumParams(fast, slow)), trend_period=trend),
        target_vol=ENTRY.target_vol,
        lookback=ENTRY.vol_lookback,
    )


def _holdout(candles):
    k = int(len(candles) * (1 - HOLDOUT_FRAC))
    return candles[k:]


def per_asset_sweep():
    holds = {}
    for sym in ALL_TOKENS:
        try:
            c = load_or_fetch(sym, TIMEFRAME, _ms("2017-01-01"), _ms("2026-06-01"))
        except DataGapError as e:
            print(f"SKIP {sym}: {e}")
            continue
        h = _holdout(c)
        if len(h) >= MIN_BARS:
            holds[sym] = h
    print(f"Per-asset holdout sweep on {len(holds)} tokens.")

    grid = {}
    for trend in TREND_VALUES:
        for fast, slow in MACD_VALUES:
            dds, rets, dd_wins = [], [], 0
            for sym, h in holds.items():
                m = compute_metrics(
                    run_backtest(
                        h,
                        _make(trend, fast, slow),
                        symbol=sym,
                        risk=RISK,
                        rebalance_band=BAND,
                    )
                )
                bh = compute_metrics(buy_and_hold(h, symbol=sym))
                dds.append(m.max_drawdown)
                rets.append(m.total_return)
                dd_wins += m.max_drawdown < bh.max_drawdown
            grid[(trend, fast, slow)] = {
                "med_dd": statistics.median(dds),
                "med_ret": statistics.median(rets),
                "dd_wins": dd_wins,
                "n": len(holds),
            }
    return grid, len(holds)


def portfolio_sweep():
    cbs = {}
    for sym in PORTFOLIO_TOKENS:
        try:
            cbs[sym] = load_or_fetch(
                sym, TIMEFRAME, _ms("2021-01-01"), _ms("2026-06-01")
            )
        except DataGapError as e:
            print(f"SKIP {sym}: {e}")
    common = sorted(set.intersection(*[set(c.ts for c in v) for v in cbs.values()]))
    lo = common[int(len(common) * (1 - HOLDOUT_FRAC))]
    hold_cbs = {s: [c for c in v if c.ts >= lo] for s, v in cbs.items()}
    bh = compute_metrics(buy_and_hold_portfolio(hold_cbs))
    print(
        f"Portfolio holdout: {len(PORTFOLIO_TOKENS)} tokens from "
        f"{datetime.fromtimestamp(lo/1000, tz=timezone.utc):%Y-%m}."
    )

    grid = {}
    for trend in TREND_VALUES:
        for fast, slow in MACD_VALUES:
            res = run_portfolio_backtest(
                hold_cbs,
                lambda s, t=trend, f=fast, sl=slow: _make(t, f, sl),
                risk=RISK,
                max_total_exposure=1.0,
                rebalance_band=BAND,
            )
            m = compute_metrics(res)
            grid[(trend, fast, slow)] = {
                "ret": m.total_return,
                "dd": m.max_drawdown,
                "sharpe": m.sharpe,
                "calmar": m.calmar,
            }
    return grid, bh


def _panel(ax, data, fmt, cmap, title, label):
    im = ax.imshow(data, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(MACD_VALUES)))
    ax.set_xticklabels([f"MACD {f}/{s}" for (f, s) in MACD_VALUES], fontsize=8)
    ax.set_yticks(range(len(TREND_VALUES)))
    ax.set_yticklabels([f"{t}d SMA" for t in TREND_VALUES], fontsize=8)
    for i, t in enumerate(TREND_VALUES):
        for j, (f, s) in enumerate(MACD_VALUES):
            locked = t == LOCKED[0] and (f, s) == (LOCKED[1], LOCKED[2])
            ax.text(
                j,
                i,
                fmt(data[i][j]) + (" ★" if locked else ""),
                ha="center",
                va="center",
                fontsize=8.5,
                color="black",
                fontweight="bold" if locked else "normal",
            )
    ax.set_title(title, fontsize=10)
    plt.colorbar(im, ax=ax, label=label)


def _heatmap(per_asset, port):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))
    dd = [
        [per_asset[(t, f, s)]["med_dd"] * 100 for (f, s) in MACD_VALUES]
        for t in TREND_VALUES
    ]
    calmar = [
        [port[(t, f, s)]["calmar"] for (f, s) in MACD_VALUES] for t in TREND_VALUES
    ]
    _panel(
        ax1,
        dd,
        lambda v: f"{v:.0f}%",
        "RdYlGn_r",
        "Per-asset median holdout drawdown\n(lower=greener)",
        "median max drawdown (%)",
    )
    _panel(
        ax2,
        calmar,
        lambda v: f"{v:.2f}",
        "RdYlGn",
        "Portfolio holdout Calmar (return ÷ drawdown)\n(higher=greener)",
        "Calmar",
    )
    fig.suptitle(
        "Sensitivity to trend window × MACD on the holdout (★ = locked entry)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    os.makedirs("docs", exist_ok=True)
    fig.savefig("docs/param_sweep.png", dpi=120)
    plt.close(fig)
    print("Wrote docs/param_sweep.png")


def main() -> int:
    per_asset, n = per_asset_sweep()
    port, bh = portfolio_sweep()

    print("\n=== Per-asset (median across tokens, holdout) ===")
    for t in TREND_VALUES:
        for f, s in MACD_VALUES:
            g = per_asset[(t, f, s)]
            tag = (
                " <- LOCKED"
                if (t == LOCKED[0] and (f, s) == (LOCKED[1], LOCKED[2]))
                else ""
            )
            print(
                f"  {t:>3}d SMA, MACD {f}/{s}:  DD {_pct(g['med_dd']):>4} "
                f"ret {_pct(g['med_ret']):>5}  DD-beat {g['dd_wins']}/{g['n']}{tag}"
            )
    print(
        f"\n=== 4-token portfolio (holdout; B&H ret {_pct(bh.total_return)} "
        f"DD {_pct(bh.max_drawdown)}) ==="
    )
    for t in TREND_VALUES:
        for f, s in MACD_VALUES:
            g = port[(t, f, s)]
            tag = (
                " <- LOCKED"
                if (t == LOCKED[0] and (f, s) == (LOCKED[1], LOCKED[2]))
                else ""
            )
            print(
                f"  {t:>3}d SMA, MACD {f}/{s}:  ret {_pct(g['ret']):>5} "
                f"DD {_pct(g['dd']):>4} Sharpe {_ratio(g['sharpe'])} "
                f"Calmar {_ratio(g['calmar'])}{tag}"
            )

    _heatmap(per_asset, port)
    _write_summary(per_asset, port, bh, n)
    return 0


def _write_summary(per_asset, port, bh, n):
    os.makedirs("reports", exist_ok=True)
    L = lambda t, f, s: (
        " **(locked)**" if (t == LOCKED[0] and (f, s) == (LOCKED[1], LOCKED[2])) else ""
    )
    lines = [
        "# Parameter sensitivity sweep (holdout)",
        "",
        "Trend window × MACD setting, all other knobs at the locked entry, scored "
        f"on the untouched last-{int(HOLDOUT_FRAC*100)}% holdout. **Read as a "
        "sensitivity map, not a re-selection** — choosing the best-on-holdout "
        "config would overfit the holdout.",
        "",
        "![holdout drawdown heatmap](../docs/param_sweep.png)",
        "",
        f"## Per asset — median across {n} tokens (holdout)",
        "",
        "| Trend | MACD | Median DD | Median return | DD beats hold |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for t in TREND_VALUES:
        for f, s in MACD_VALUES:
            g = per_asset[(t, f, s)]
            lines.append(
                f"| {t}d{L(t,f,s)} | {f}/{s} | {_pct(g['med_dd'])} | "
                f"{_pct(g['med_ret'])} | {g['dd_wins']}/{g['n']} |"
            )
    lines += [
        "",
        f"## 4-token portfolio (holdout; buy & hold: return {_pct(bh.total_return)}, "
        f"drawdown {_pct(bh.max_drawdown)})",
        "",
        "| Trend | MACD | Return | MaxDD | Sharpe | Calmar |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for t in TREND_VALUES:
        for f, s in MACD_VALUES:
            g = port[(t, f, s)]
            lines.append(
                f"| {t}d{L(t,f,s)} | {f}/{s} | {_pct(g['ret'])} | {_pct(g['dd'])} | "
                f"{_ratio(g['sharpe'])} | {_ratio(g['calmar'])} |"
            )
    lines.append("")
    with open("reports/param_sweep_summary.md", "w") as fh:
        fh.write("\n".join(lines))
    print("Summary: reports/param_sweep_summary.md")


if __name__ == "__main__":
    raise SystemExit(main())
