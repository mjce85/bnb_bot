#!/usr/bin/env python
"""Play-by-play — visualize each buy/sell and WHAT triggered it.

Runs the locked entry on a recent BNB window and annotates every fill with its
cause, reconstructed from the gate state on the decision bar:
  * BUY  from cash      -> "entry" (both gates turned on)
  * BUY  while holding  -> "add" (volatility sizing scaled up in calm)
  * SELL to cash, trend -> "below 50-day trend" (regime gate off)
  * SELL to cash, mom   -> "momentum flip" (MACD turned down)
  * SELL to cash, both on-> "stop / breaker" (risk overlay)
  * SELL partial        -> "trim" (volatility sizing scaled down in turbulence)

Top panel: price + 50-day trend with buy/sell markers and reason labels.
Bottom panel: the target weight (0=cash, 1=all-in). Writes docs/strategy_events.png.
"""

from __future__ import annotations

import os
import statistics
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bnb_bot.backtest import run_backtest  # noqa: E402
from bnb_bot.data import load_or_fetch  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.strategy import _ema  # noqa: E402
from bnb_bot.types import Side  # noqa: E402

SYMBOL = "BNB/USDT"
START = "2023-09-01"
END = "2024-09-01"
LABEL_GAP_DAYS = 18  # suppress reason labels closer than this, to avoid overlap


def _ms(s: str) -> int:
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _dt(ts):
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)


def main() -> int:
    candles = load_or_fetch(SYMBOL, "1d", _ms(START), _ms(END))
    closes = [c.close for c in candles]
    dts = [_dt(c.ts) for c in candles]
    idx_of = {c.ts: i for i, c in enumerate(candles)}

    strat = ENTRY.build_strategy()  # pure -> callable per prefix
    weights = [strat.signal(candles[: i + 1]) for i in range(len(candles))]

    tp, fast, slow, vl = ENTRY.trend_period, 12, 26, ENTRY.vol_lookback
    sma = [
        statistics.mean(closes[max(0, i - tp + 1) : i + 1]) if i >= tp - 1 else None
        for i in range(len(closes))
    ]

    def gate_state(i):  # gates as seen on decision bar i
        if i < tp - 1:
            return False, False
        regime = closes[i] > statistics.mean(closes[i - tp + 1 : i + 1])
        sub = closes[: i + 1]
        mom = _ema(sub, fast) > _ema(sub, slow)
        return regime, mom

    res = run_backtest(
        candles,
        ENTRY.build_strategy(),
        symbol=SYMBOL,
        risk=ENTRY.build_risk(),
        rebalance_band=ENTRY.rebalance_band,
    )

    # Replay fills to classify each as entry/add/trim/exit-reason.
    qty = 0.0
    events = []  # (dt, price, side, kind, label, big)
    for f in res.fills:
        i = idx_of[f.ts]
        di = i - 1  # decision bar
        regime, mom = gate_state(di) if di >= 0 else (False, False)
        before = qty
        if f.side is Side.BUY:
            qty += f.base_qty
            if before <= 1e-9:
                events.append((_dt(f.ts), f.price, "buy", "entry", "BUY entry", True))
            else:
                events.append((_dt(f.ts), f.price, "buy", "add", "add (calm)", False))
        else:
            qty -= f.base_qty
            if qty <= 1e-9:  # full exit
                if not regime:
                    lbl = "SELL: below 50-day trend"
                elif not mom:
                    lbl = "SELL: momentum flip"
                else:
                    lbl = "SELL: stop / breaker"
                events.append((_dt(f.ts), f.price, "sell", "exit", lbl, True))
            else:
                events.append(
                    (_dt(f.ts), f.price, "sell", "trim", "trim (turbulence)", False)
                )

    # === Plot ===
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 8), sharex=True, height_ratios=[3, 1]
    )
    ax1.plot(dts, closes, color="#111827", lw=1.1, label=f"{SYMBOL} price")
    ax1.plot(dts, sma, color="#f59e0b", lw=1.5, label=f"{tp}-day trend")
    ax1.fill_between(
        dts,
        min(closes),
        max(closes),
        where=[w > 0 for w in weights],
        color="#16a34a",
        alpha=0.08,
        label="invested",
    )

    for dt, price, side, kind, label, big in events:
        if side == "buy":
            ax1.scatter(
                dt,
                price,
                marker="^",
                s=130 if big else 45,
                color="#16a34a",
                zorder=5,
                edgecolor="white",
                linewidth=0.6,
            )
        else:
            ax1.scatter(
                dt,
                price,
                marker="v",
                s=130 if big else 45,
                color="#dc2626",
                zorder=5,
                edgecolor="white",
                linewidth=0.6,
            )

    # Label only the big events (entries / full exits), and skip any that fall
    # within LABEL_GAP_DAYS of the previous label so the callouts stay readable.
    big_events = [e for e in events if e[5]]
    last_label = None
    for dt, price, side, kind, label, _b in big_events:
        if last_label is not None and (dt - last_label) < timedelta(
            days=LABEL_GAP_DAYS
        ):
            continue
        last_label = dt
        up = side == "buy"
        ax1.annotate(
            label,
            (dt, price),
            xytext=(0, 26 if up else -30),
            textcoords="offset points",
            ha="center",
            fontsize=7.5,
            color="#166534" if up else "#991b1b",
            arrowprops=dict(arrowstyle="-", color="#9ca3af", lw=0.6),
            bbox=dict(boxstyle="round", fc="white", ec="#d1d5db", alpha=0.9),
        )

    ax1.set_yscale("log")
    ax1.set_ylabel("price (log)")
    ax1.set_title(f"How buys & sells happen — {SYMBOL} ({START} … {END})", fontsize=12)
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)

    ax2.fill_between(dts, weights, 0, color="#16a34a", alpha=0.5)
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("target weight\n(0=cash, 1=all-in)")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    os.makedirs("docs", exist_ok=True)
    fig.savefig("docs/strategy_events.png", dpi=120)
    plt.close(fig)
    n_buy = sum(1 for e in events if e[2] == "buy")
    n_sell = len(events) - n_buy
    print(f"Wrote docs/strategy_events.png ({n_buy} buys, {n_sell} sells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
