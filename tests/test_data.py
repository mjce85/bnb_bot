"""T2 — historical data loader: gap detection + parquet cache (no network)."""

import pytest

from bnb_bot import config, data
from bnb_bot.types import Candle


def _series(n, step_ms, start=1_700_000_000_000, drop=()):
    """Synthetic contiguous candle series; `drop` removes bar indices to
    punch a gap. Synthetic data in tests is allowed (CLAUDE.md)."""
    out = []
    for i in range(n):
        if i in drop:
            continue
        ts = start + i * step_ms
        out.append(
            Candle(
                ts=ts,
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=1000.0 + i,
            )
        )
    return out


def test_timeframe_ms_known_and_unknown():
    assert data.timeframe_ms("1h") == 3_600_000
    with pytest.raises(ValueError):
        data.timeframe_ms("3s")


def test_detect_gaps_contiguous():
    c = _series(10, data.timeframe_ms("1h"))
    assert data.detect_gaps(c, "1h") == []


def test_detect_gaps_finds_missing_bar():
    c = _series(10, data.timeframe_ms("1h"), drop=(5,))
    gaps = data.detect_gaps(c, "1h")
    assert len(gaps) == 1
    lo, hi = gaps[0]
    assert hi - lo == 2 * data.timeframe_ms("1h")  # one bar missing


def test_assert_contiguous_passes_on_clean_series():
    data.assert_contiguous(_series(5, data.timeframe_ms("1d")), "1d")


def test_assert_contiguous_raises_on_gap():
    c = _series(10, data.timeframe_ms("1h"), drop=(5,))
    with pytest.raises(data.DataGapError):
        data.assert_contiguous(c, "1h")


def test_assert_contiguous_raises_on_empty():
    with pytest.raises(data.DataGapError):
        data.assert_contiguous([], "1h")


def test_parquet_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    c = _series(10, data.timeframe_ms("1h"))
    data.save_candles(c, "BNB/USDT", "1h")
    loaded = data.load_cached("BNB/USDT", "1h")
    assert loaded == c


def test_load_cached_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    assert data.load_cached("NOPE/USDT", "1h") is None
