#!/usr/bin/env python
"""Does a CMC Fear & Greed overlay improve the locked entry? Measure it honestly.

Compares the locked entry **with vs without** the :class:`FearGreedGated` overlay
(step to cash in extreme greed, threshold 75), on two free sentiment sources:

* **alternative.me** — F&G history back to 2018, so it covers the FULL
  2021->2026 window (incl. the 2022 bear). A proxy for CMC's index.
* **CMC** — the sponsor's own index, history from 2023-06-29; compared on the
  window both sources cover, so we see (a) the gate's effect on the real CMC data
  and (b) whether the two indices agree.

Also prints how tightly the two indices correlate on their overlap — the honest
justification for using the alternative.me proxy to extend the backtest.

    ./venv/bin/python scripts/run_fear_greed.py    # -> reports/fear_greed_summary.md

Network: ccxt for candles (cache miss) + CMC F&G (needs CMC_PRO_API_KEY in .env)
+ alternative.me (no key). All cached under data/ after the first run.
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
from bnb_bot.portfolio import (  # noqa: E402
    buy_and_hold_portfolio,
    run_portfolio_backtest,
)
from bnb_bot.presets import VOL_TARGETED_REGIME_MOMENTUM as ENTRY  # noqa: E402
from bnb_bot.sentiment import load_fear_greed, overlap_correlation  # noqa: E402
from bnb_bot.strategy import FearGreedGated  # noqa: E402
from bnb_bot.walkforward import buy_and_hold  # noqa: E402

FULL_START, CMC_START, WINDOW_END = "2021-01-01", "2023-07-01", "2026-06-01"
TIMEFRAME = "1d"
OUT_DIR = "reports"
GREED_THRESHOLD, GREED_WEIGHT = 75, 0.0


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


def _slice(candles, lo, hi):
    return [c for c in candles if lo <= c.ts < hi]


def _entry(fng=None):
    base = ENTRY.build_strategy()
    return (
        FearGreedGated(
            base, fng, greed_threshold=GREED_THRESHOLD, greed_weight=GREED_WEIGHT
        )
        if fng is not None
        else base
    )


def _single(candles, symbol, fng=None):
    res = run_backtest(
        candles,
        _entry(fng),
        symbol=symbol,
        risk=ENTRY.build_risk(),
        rebalance_band=ENTRY.rebalance_band,
        strategy_name="fng" if fng is not None else "base",
    )
    return compute_metrics(res)


def _portfolio(cbs, fng=None):
    res = run_portfolio_backtest(
        cbs,
        lambda sym: _entry(fng),
        risk=ENTRY.build_risk(),
        max_total_exposure=ENTRY.risk_limits.max_total_exposure,
        rebalance_band=ENTRY.rebalance_band,
    )
    return compute_metrics(res)


def _row(label, m):
    return (
        f"| {label} | {_pct(m.total_return)} | {_pct(m.max_drawdown)} | "
        f"{_ratio(m.sharpe)} | {_ratio(m.calmar)} |"
    )


def main() -> int:
    full_lo, cmc_lo, hi = _ms(FULL_START), _ms(CMC_START), _ms(WINDOW_END)

    print("Loading Fear & Greed series...")
    alt = load_fear_greed("alternative")
    cmc = load_fear_greed("cmc")
    corr, n_overlap = overlap_correlation(cmc, alt)
    a0, a1 = (
        datetime.fromtimestamp(t / 1000, tz=timezone.utc).date() for t in alt.range()
    )
    c0, c1 = (
        datetime.fromtimestamp(t / 1000, tz=timezone.utc).date() for t in cmc.range()
    )
    print(f"  alternative.me: {a0} -> {a1} ({len(alt)} days)")
    print(f"  CMC:            {c0} -> {c1} ({len(cmc)} days)")
    print(f"  overlap correlation: {corr:.3f} over {n_overlap} days\n")

    cbs_full, cbs_cmc = {}, {}
    lines = [
        "# Fear & Greed overlay — does CMC sentiment improve the entry?",
        "",
        f"Entry **with vs without** a Fear & Greed gate (step to cash when F&G ≥ "
        f"{GREED_THRESHOLD}, the standard 'Extreme Greed' boundary; not tuned).",
        "",
        f"**Proxy quality:** alternative.me vs CMC F&G correlate **{corr:.3f}** over "
        f"**{n_overlap}** overlapping days — so alternative.me is a sound stand-in "
        "for extending the backtest before CMC's index begins (2023-06-29).",
        "",
        f"- alternative.me F&G: {a0} → {a1} · CMC F&G: {c0} → {c1}",
        "- F&G lookup is strictly pre-bar (no look-ahead); overlay only ever cuts "
        "exposure; backtest is otherwise the locked entry.",
        "",
    ]

    for symbol in config.TOKEN_SET:
        try:
            candles = load_or_fetch(symbol, TIMEFRAME, full_lo, hi)
        except DataGapError as e:
            print(f"SKIP {symbol}: {e}")
            continue
        cbs_full[symbol] = candles
        cbs_cmc[symbol] = _slice(candles, cmc_lo, hi)

    # --- Per-token: FULL window (proxy) ---
    lines += [
        f"## Per token — FULL window ({FULL_START} → {WINDOW_END}), alternative.me F&G",
        "",
        "| Token / variant | Return | MaxDD | Sharpe | Calmar |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    print(f"FULL window {FULL_START}→{WINDOW_END} (alternative.me F&G):")
    for symbol, candles in cbs_full.items():
        base = _single(candles, symbol)
        gated = _single(candles, symbol, alt)
        hold = compute_metrics(buy_and_hold(candles, symbol=symbol))
        lines.append(_row(f"{symbol} — no gate", base))
        lines.append(_row(f"{symbol} — +F&G gate", gated))
        lines.append(_row(f"{symbol} — buy & hold", hold))
        print(
            f"  {symbol:9s} ret {_pct(base.total_return):>8s}→{_pct(gated.total_return):>8s}  "
            f"maxDD {_pct(base.max_drawdown):>6s}→{_pct(gated.max_drawdown):>6s}  "
            f"Calmar {_ratio(base.calmar)}→{_ratio(gated.calmar)}"
        )
    lines.append("")

    # --- Per-token: CMC window, both sources ---
    lines += [
        f"## Per token — CMC window ({CMC_START} → {WINDOW_END}), CMC vs alternative.me",
        "",
        "| Token / variant | Return | MaxDD | Sharpe | Calmar |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    print(f"\nCMC window {CMC_START}→{WINDOW_END} (CMC F&G vs alternative.me):")
    for symbol, candles in cbs_cmc.items():
        base = _single(candles, symbol)
        g_cmc = _single(candles, symbol, cmc)
        g_alt = _single(candles, symbol, alt)
        lines.append(_row(f"{symbol} — no gate", base))
        lines.append(_row(f"{symbol} — +F&G (CMC)", g_cmc))
        lines.append(_row(f"{symbol} — +F&G (alt.me)", g_alt))
        print(
            f"  {symbol:9s} no-gate ret {_pct(base.total_return):>8s} DD {_pct(base.max_drawdown):>6s} | "
            f"CMC ret {_pct(g_cmc.total_return):>8s} DD {_pct(g_cmc.max_drawdown):>6s} | "
            f"alt ret {_pct(g_alt.total_return):>8s} DD {_pct(g_alt.max_drawdown):>6s}"
        )
    lines.append("")

    # --- Portfolio: both windows ---
    lines += [
        "## Portfolio (what you'd actually run)",
        "",
        "| Variant | Return | MaxDD | Sharpe | Calmar |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    print("\nPortfolio:")
    pf_base_full = _portfolio(cbs_full)
    pf_gate_full = _portfolio(cbs_full, alt)
    pf_hold_full = compute_metrics(buy_and_hold_portfolio(cbs_full))
    lines.append(_row(f"FULL, no gate ({FULL_START}+)", pf_base_full))
    lines.append(_row("FULL, +F&G gate (alt.me)", pf_gate_full))
    lines.append(_row("FULL, equal-weight hold", pf_hold_full))
    pf_base_cmc = _portfolio(cbs_cmc)
    pf_gate_cmc = _portfolio(cbs_cmc, cmc)
    pf_gate_cmc_alt = _portfolio(cbs_cmc, alt)
    lines.append(_row(f"CMC-window, no gate ({CMC_START}+)", pf_base_cmc))
    lines.append(_row("CMC-window, +F&G (CMC)", pf_gate_cmc))
    lines.append(_row("CMC-window, +F&G (alt.me)", pf_gate_cmc_alt))
    lines.append("")
    for lbl, m in [
        ("FULL no-gate ", pf_base_full),
        ("FULL +F&G    ", pf_gate_full),
        ("CMC  no-gate ", pf_base_cmc),
        ("CMC  +F&G CMC", pf_gate_cmc),
    ]:
        print(
            f"  {lbl}: ret {_pct(m.total_return):>8s}  maxDD {_pct(m.max_drawdown):>6s}  "
            f"Sharpe {_ratio(m.sharpe)}  Calmar {_ratio(m.calmar)}"
        )

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "fear_greed_summary.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"\nSummary: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
