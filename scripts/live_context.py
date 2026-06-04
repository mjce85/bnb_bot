#!/usr/bin/env python
"""Live decision panel: today's strategy stance + CMC market context.

The submission's CMC-data touchpoint. Pulls **live** signals from the CoinMarketCap
Agent Hub / Data API (free Basic tier) — the Fear & Greed index and BTC dominance —
and shows them alongside the locked entry's *current* target weight for each token.

Honest framing baked in: F&G is shown as **market context**, not a position control.
We backtested gating the strategy on F&G and it did not improve risk-adjusted
performance (see reports/fear_greed_summary.md), so it informs the operator; it does
not override the validated strategy.

    ./venv/bin/python scripts/live_context.py

Network: CMC (needs CMC_PRO_API_KEY in .env) + ccxt for recent candles. Read-only;
no orders, no money moved.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bnb_bot import config  # noqa: E402
from bnb_bot.data import DataGapError, load_or_fetch  # noqa: E402
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.sentiment import FearGreedError, cmc_api_key  # noqa: E402

_CMC = "https://pro-api.coinmarketcap.com"
LOOKBACK_DAYS = 300  # enough for the 50-day regime SMA + warmup


def _cmc_get(path: str, key: str) -> dict:
    req = urllib.request.Request(f"{_CMC}{path}", headers={"X-CMC_PRO_API_KEY": key})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _stance(weight: float) -> str:
    if weight <= 0.0:
        return "FLAT (cash)"
    if weight < 0.5:
        return f"LIGHT long ({weight:.0%})"
    return f"long ({weight:.0%})"


def main() -> int:
    try:
        key = cmc_api_key()
    except FearGreedError as e:
        print(e)
        return 1

    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    since_ms = int((now - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000)

    # --- Live CMC market context (free tier) ---
    fng = _cmc_get("/v3/fear-and-greed/latest", key)["data"]
    gm = _cmc_get("/v1/global-metrics/quotes/latest", key)["data"]
    fng_val = int(fng["value"])
    fng_cls = fng.get("value_classification", "")
    btc_dom = gm.get("btc_dominance")

    print("=" * 60)
    print(f"  LIVE MARKET CONTEXT (CoinMarketCap)   {now:%Y-%m-%d %H:%M UTC}")
    print("=" * 60)
    print(f"  Fear & Greed : {fng_val}  ({fng_cls})")
    if btc_dom is not None:
        print(f"  BTC dominance: {btc_dom:.1f}%")
    print()
    print("  Strategy stance today (locked entry, per token):")
    for symbol in config.TOKEN_SET:
        try:
            candles = load_or_fetch(symbol, "1d", since_ms, now_ms)
        except DataGapError as e:
            print(f"    {symbol:10s} n/a — {e}")
            continue
        weight = ENTRY.build_strategy().signal(candles)
        print(f"    {symbol:10s} -> {_stance(weight)}")
    print()
    print("  Note: Fear & Greed is shown as market CONTEXT, not a trade trigger.")
    print("  Backtests showed gating the strategy on it does not improve")
    print("  risk-adjusted performance, so it informs — it does not control.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
