#!/usr/bin/env python
"""EXPLORATORY: is F&G BTC-led, and do the alts lag BTC?

Tests the operator's mechanistic hypothesis for *why* a (BTC-driven) Fear & Greed
signal might add value to the alts: if alts lag BTC, a BTC-led sentiment reading
carries leading information for them. Pure data analysis on cached daily candles +
the alternative.me F&G series — no backtest, no tuning.

Reports, on daily log returns over the full window:
  (A) lagged cross-correlation alt-vs-BTC: corr(alt[t], BTC[t-k]) for k=-3..3.
      A peak at k>0 means the alt FOLLOWS BTC by k days (alt lags).
  (B) correlation of the daily F&G *change* with each coin's return at lags -2..2
      — does F&G move with BTC and lead the alts?

    ./venv/bin/python scripts/analyze_leadlag.py
"""

from __future__ import annotations

import math
import os
import statistics
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bnb_bot import config  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.sentiment import load_fear_greed  # noqa: E402

WINDOW_START, WINDOW_END, TIMEFRAME = "2021-01-01", "2026-06-01", "1d"
_DAY_MS = 24 * 60 * 60 * 1000
LAGS = range(-3, 4)


def _ms(s):
    return int(
        datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _log_returns_by_day(candles):
    """{day_index: log return} from daily closes."""
    out = {}
    for prev, nxt in zip(candles, candles[1:]):
        if prev.close > 0 and nxt.close > 0:
            out[nxt.ts // _DAY_MS] = math.log(nxt.close / prev.close)
    return out


def _aligned(a: dict, b: dict, lag: int):
    """Pairs (a[d], b[d-lag]) over days where both exist."""
    xs, ys = [], []
    for d, av in a.items():
        bv = b.get(d - lag)
        if bv is not None:
            xs.append(av)
            ys.append(bv)
    return xs, ys


def _corr_at_lag(a, b, lag):
    xs, ys = _aligned(a, b, lag)
    if len(xs) < 30:
        return None
    return statistics.correlation(xs, ys)


def main() -> int:
    lo, hi = _ms(WINDOW_START), _ms(WINDOW_END)
    rets = {}
    for sym in config.TOKEN_SET:
        try:
            rets[sym] = _log_returns_by_day(load_or_fetch(sym, TIMEFRAME, lo, hi))
        except DataGapError as e:
            print(f"SKIP {sym}: {e}")
    btc = rets.get("BTC/USDT")
    if not btc:
        print("no BTC data — cannot run lead-lag")
        return 1

    print("(A) Lead-lag vs BTC — corr(alt[t], BTC[t-k]); peak at k>0 => alt LAGS BTC\n")
    header = "  " + " ".join(f"k={k:+d}" for k in LAGS)
    print(f"  {'token':10s}" + header)
    for sym in config.TOKEN_SET:
        if sym == "BTC/USDT" or sym not in rets:
            continue
        cells = []
        best_k, best_c = 0, -2.0
        for k in LAGS:
            c = _corr_at_lag(rets[sym], btc, k)
            cells.append("  n/a " if c is None else f"{c:+.2f}")
            if c is not None and k > 0 and c > best_c:
                best_c, best_k = c, k
        # also compare lag0 vs the best positive lag
        c0 = _corr_at_lag(rets[sym], btc, 0)
        lags_better = best_c > (c0 or -2) + 0.005 if c0 is not None else False
        flag = (
            f"  -> follows BTC by ~{best_k}d (lag corr {best_c:+.2f} > same-day {c0:+.2f})"
            if lags_better
            else f"  -> strongest SAME-DAY (lag0 {c0:+.2f}); no clear lag"
        )
        print(f"  {sym:10s} " + " ".join(f"{x:>6s}" for x in cells) + flag)

    # (B) F&G change vs coin returns at lags.
    print("\n(B) corr(coin return[t], ΔF&G[t-k]); k>0 => F&G change LEADS the coin\n")
    fng = load_fear_greed("alternative")
    fng_by_day = {r.ts // _DAY_MS: r.value for r in fng.readings}
    dfng = {}
    days = sorted(fng_by_day)
    for prev, cur in zip(days, days[1:]):
        if cur - prev == 1:
            dfng[cur] = fng_by_day[cur] - fng_by_day[prev]
    print(f"  {'token':10s}" + header)
    for sym in config.TOKEN_SET:
        if sym not in rets:
            continue
        cells = []
        for k in LAGS:
            c = _corr_at_lag(rets[sym], dfng, k)
            cells.append("  n/a " if c is None else f"{c:+.2f}")
        print(f"  {sym:10s} " + " ".join(f"{x:>6s}" for x in cells))
    print(
        "\n  (ΔF&G and returns are near-contemporaneous by construction; compare "
        "how much MORE same-day corr BTC has vs the alts.)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
