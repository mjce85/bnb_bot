"""Historical OHLCV loading + caching for backtests.

Source: ccxt (Binance spot — free, no API key, has history for BSC-listed
tokens). Candles are cached as parquet under ``config.DATA_DIR`` and validated
for gaps. We FAIL LOUD on missing bars: a silently gap-filled series produces a
backtest number that lies, which is the one thing this repo must not do.
"""

from __future__ import annotations

import os

import polars as pl

from bnb_bot import config
from bnb_bot.types import Candle

_TF_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}


class DataGapError(Exception):
    """Raised when cached/fetched candles are missing one or more bars."""


def timeframe_ms(timeframe: str) -> int:
    try:
        return _TF_MS[timeframe]
    except KeyError:
        raise ValueError(
            f"unsupported timeframe {timeframe!r}; known: {sorted(_TF_MS)}"
        )


# --- gap detection (the credibility guard) -----------------------------


def detect_gaps(candles: list[Candle], timeframe: str) -> list[tuple[int, int]]:
    """Return ``[(prev_ts, next_ts), ...]`` for every adjacent pair whose
    spacing isn't exactly one bar. Empty list == contiguous."""
    step = timeframe_ms(timeframe)
    gaps: list[tuple[int, int]] = []
    for prev, nxt in zip(candles, candles[1:]):
        if nxt.ts - prev.ts != step:
            gaps.append((prev.ts, nxt.ts))
    return gaps


def assert_contiguous(candles: list[Candle], timeframe: str) -> None:
    """Fail loud unless ``candles`` is a non-empty, one-bar-spaced series."""
    if not candles:
        raise DataGapError("no candles to validate (empty series)")
    gaps = detect_gaps(candles, timeframe)
    if gaps:
        step = timeframe_ms(timeframe)
        lo, hi = gaps[0]
        missing = (hi - lo) // step - 1
        raise DataGapError(
            f"{len(gaps)} gap(s) in {timeframe} series; first spans ts "
            f"{lo} -> {hi} (~{missing} missing bar(s)). Refusing to backtest "
            f"on a discontinuous series — re-fetch the window or narrow it."
        )


# --- parquet cache -----------------------------------------------------


def _cache_path(symbol: str, timeframe: str) -> str:
    safe = symbol.replace("/", "-")
    return os.path.join(config.DATA_DIR, f"{safe}_{timeframe}.parquet")


def candles_to_df(candles: list[Candle]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": [c.ts for c in candles],
            "open": [float(c.open) for c in candles],
            "high": [float(c.high) for c in candles],
            "low": [float(c.low) for c in candles],
            "close": [float(c.close) for c in candles],
            "volume": [float(c.volume) for c in candles],
        }
    )


def df_to_candles(df: pl.DataFrame) -> list[Candle]:
    return [
        Candle(
            ts=int(r["ts"]),
            open=r["open"],
            high=r["high"],
            low=r["low"],
            close=r["close"],
            volume=r["volume"],
        )
        for r in df.iter_rows(named=True)
    ]


def save_candles(candles: list[Candle], symbol: str, timeframe: str) -> str:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = _cache_path(symbol, timeframe)
    candles_to_df(candles).write_parquet(path)
    return path


def load_cached(symbol: str, timeframe: str) -> list[Candle] | None:
    path = _cache_path(symbol, timeframe)
    if not os.path.exists(path):
        return None
    return df_to_candles(pl.read_parquet(path))


# --- ccxt fetch (network; not exercised in unit tests) -----------------


def _fetch_ohlcv_ccxt(
    symbol: str, timeframe: str, since_ms: int, until_ms: int
) -> list[Candle]:
    """Paginate Binance OHLCV via ccxt. Network call — kept out of tests."""
    import ccxt  # local import keeps test collection light

    ex = getattr(ccxt, config.EXCHANGE_ID)({"enableRateLimit": True})
    step = timeframe_ms(timeframe)
    out: list[Candle] = []
    since = since_ms
    while since < until_ms:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not batch:
            break
        for ts, o, h, low, c, v in batch:
            if ts >= until_ms:
                break
            out.append(Candle(ts=ts, open=o, high=h, low=low, close=c, volume=v))
        since = batch[-1][0] + step
        if len(batch) < 1000:
            break
    return out


def load_or_fetch(
    symbol: str,
    timeframe: str,
    since_ms: int,
    until_ms: int,
    *,
    use_cache: bool = True,
) -> list[Candle]:
    """Return a validated, contiguous candle series for ``[since_ms, until_ms)``.

    Tries the parquet cache first (when it covers the requested range), else
    fetches from ccxt. Either way the result is checked for gaps before return.
    """
    step = timeframe_ms(timeframe)
    if use_cache:
        cached = load_cached(symbol, timeframe)
        if cached:
            window = [c for c in cached if since_ms <= c.ts < until_ms]
            covers = (
                window
                and window[0].ts <= since_ms + step
                and window[-1].ts >= until_ms - 2 * step
            )
            if covers:
                assert_contiguous(window, timeframe)
                return window
    candles = _fetch_ohlcv_ccxt(symbol, timeframe, since_ms, until_ms)
    assert_contiguous(candles, timeframe)
    save_candles(candles, symbol, timeframe)
    return candles
