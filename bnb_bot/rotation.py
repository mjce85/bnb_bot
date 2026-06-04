"""Cross-sectional rotation allocators — the creative challenger to the entry.

The locked entry treats each token independently and sits in cash during its own
downtrend. A *rotation* strategy instead looks across the whole universe at once
and concentrates capital in the **strongest** tokens — directly attacking the
entry's weak axis (raw return), which it gives up by holding only a fraction of
each coin.

The headline challenger is **dual momentum** (Antonacci-style), adapted to daily
spot crypto:

* **Relative momentum** — rank tokens by their trailing ``lookback``-day return and
  hold the top ``top_k``.
* **Absolute momentum** — a token is only eligible if that return is *positive*
  (it's actually trending up). When nothing qualifies, the book goes to cash.
  This is the built-in downside brake — the same "don't fight the tide" instinct
  as the entry's regime gate, expressed cross-sectionally.

Each held name gets ``1 / top_k`` of equity, so concentration per name is capped
and cash rises automatically when fewer than ``top_k`` tokens are trending.

Parameters are **convention, not search**: ``lookback=90`` is a standard 3-month
momentum horizon; ``top_k=2`` holds the strongest half of the 4-token universe.
We deliberately do not tune them to beat the entry — that would be the overfitting
the whole project rejects. An allocator is a pure function of the causal slices it
is handed (``candles[: t+1]`` per symbol), so no-lookahead is structural.
"""

from __future__ import annotations

from bnb_bot.types import Candle


def trailing_return(history: list[Candle], lookback: int) -> float | None:
    """Total return over the last ``lookback`` bars, or ``None`` if too short.

    Uses only ``history`` (which the engine passes as ``candles[: t+1]``), so the
    most recent close is the decision bar — no future data.
    """
    if len(history) < lookback + 1:
        return None
    past = history[-(lookback + 1)].close
    now = history[-1].close
    if past <= 0:
        return None
    return now / past - 1.0


def dual_momentum_allocator(*, lookback: int = 90, top_k: int = 2):
    """Build a dual-momentum rotation allocator.

    Returns ``allocator(histories) -> {symbol: target_weight}`` for
    :func:`bnb_bot.portfolio.run_rotation_backtest`: rank symbols by trailing
    ``lookback``-day return, keep those with a *positive* return (absolute
    momentum), take the top ``top_k``, and equal-weight them at ``1/top_k`` each
    (cash for the remainder). All-cash when nothing is trending up.
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    def allocator(histories: dict) -> dict:
        scored = []
        for sym, hist in histories.items():
            r = trailing_return(hist, lookback)
            if r is not None and r > 0.0:  # absolute-momentum eligibility
                scored.append((r, sym))
        scored.sort(reverse=True)  # strongest first
        chosen = [sym for _, sym in scored[:top_k]]
        w = 1.0 / top_k
        return {sym: (w if sym in chosen else 0.0) for sym in histories}

    return allocator
