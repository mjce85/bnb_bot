"""Tests for Fear & Greed sentiment loading + the FearGreedGated overlay.

All synthetic — no network. The two things that must hold: the lookup is
strictly no-lookahead, and the overlay only ever *reduces* exposure.
"""

from __future__ import annotations

import pytest

from bnb_bot.sentiment import (
    FearGreedError,
    FearGreedReading,
    FearGreedSeries,
    overlap_correlation,
    parse_alternative,
    parse_cmc,
)
from bnb_bot.strategy import FearGreedGated, Strategy
from bnb_bot.types import Candle

_DAY = 24 * 60 * 60 * 1000


def _series(values, *, source="cmc", start=0):
    readings = [
        FearGreedReading(ts=start + i * _DAY, value=v, classification="x")
        for i, v in enumerate(values)
    ]
    return FearGreedSeries(readings, source=source)


class _Const(Strategy):
    """Base stub that always wants a fixed weight — isolates the gate logic."""

    def __init__(self, w: float):
        self._w = w

    @property
    def name(self) -> str:
        return "const"

    @property
    def params(self) -> dict:
        return {"w": self._w}

    def signal(self, history):
        return self._w


def _candle(ts):
    return Candle(ts=ts, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0)


# --- FearGreedSeries.value_asof (the no-lookahead guard) ---------------


def test_value_asof_returns_most_recent_strictly_before():
    s = _series([10, 20, 30], start=0)  # ts 0, 1d, 2d
    # exactly on day-2's stamp -> must NOT see day-2 (strictly before)
    assert s.value_asof(2 * _DAY) == 20
    # a moment after day-2 -> now day-2 is visible
    assert s.value_asof(2 * _DAY + 1) == 30


def test_value_asof_none_before_series_begins():
    s = _series([50, 60], start=10 * _DAY)
    assert s.value_asof(10 * _DAY) is None  # on the first stamp, nothing earlier
    assert s.value_asof(9 * _DAY) is None


def test_empty_series_fails_loud():
    with pytest.raises(FearGreedError):
        FearGreedSeries([], source="cmc")


def test_range_and_len():
    s = _series([1, 2, 3], start=5 * _DAY)
    assert len(s) == 3
    assert s.range() == (5 * _DAY, 7 * _DAY)


# --- parsing -----------------------------------------------------------


def test_parse_cmc_converts_seconds_to_ms():
    payload = {
        "data": [
            {"timestamp": "1700000000", "value": "42", "value_classification": "Fear"}
        ]
    }
    out = parse_cmc(payload)
    assert out[0].ts == 1700000000 * 1000
    assert out[0].value == 42 and out[0].classification == "Fear"


def test_parse_alternative_shape():
    payload = {
        "data": [
            {
                "timestamp": "1517443200",
                "value": "30",
                "value_classification": "Fear",
                "time_until_update": "1",
            }
        ]
    }
    out = parse_alternative(payload)
    assert out[0].ts == 1517443200 * 1000 and out[0].value == 30


# --- overlap correlation ----------------------------------------------


def test_overlap_correlation_perfect_on_identical_days():
    a = _series([10, 20, 30, 40], start=0)
    b = _series([10, 20, 30, 40], start=0, source="alternative")
    corr, n = overlap_correlation(a, b)
    assert n == 4
    assert corr == pytest.approx(1.0)


def test_overlap_correlation_requires_two_common_days():
    a = _series([10], start=0)
    b = _series([10], start=100 * _DAY, source="alternative")
    with pytest.raises(FearGreedError):
        overlap_correlation(a, b)


# --- FearGreedGated overlay -------------------------------------------


def test_gate_cuts_to_cash_in_extreme_greed():
    s = _series([80, 80], start=0)  # day-0 reading = 80 (extreme greed)
    gated = FearGreedGated(_Const(1.0), s, greed_threshold=75, greed_weight=0.0)
    # decision bar a moment after day-0 -> sees value 80 -> flat
    assert gated.signal([_candle(1)]) == 0.0


def test_gate_passthrough_below_threshold():
    s = _series([50, 50], start=0)
    gated = FearGreedGated(_Const(0.8), s, greed_threshold=75, greed_weight=0.0)
    assert gated.signal([_candle(1)]) == pytest.approx(0.8)


def test_gate_partial_scaledown():
    s = _series([90, 90], start=0)
    gated = FearGreedGated(_Const(1.0), s, greed_threshold=75, greed_weight=0.5)
    assert gated.signal([_candle(1)]) == pytest.approx(0.5)


def test_gate_inert_before_sentiment_exists():
    s = _series([90], start=100 * _DAY)  # sentiment far in the future
    gated = FearGreedGated(_Const(1.0), s, greed_threshold=75, greed_weight=0.0)
    assert gated.signal([_candle(1)]) == pytest.approx(1.0)  # passthrough


def test_gate_never_lifts_a_flat_base():
    s = _series([10, 10], start=0)  # extreme fear, gate would not cut anyway
    gated = FearGreedGated(_Const(0.0), s, greed_threshold=75, greed_weight=0.0)
    assert gated.signal([_candle(1)]) == 0.0


def test_gate_validates_params():
    s = _series([50], start=0)
    with pytest.raises(ValueError):
        FearGreedGated(_Const(1.0), s, greed_threshold=150)
    with pytest.raises(ValueError):
        FearGreedGated(_Const(1.0), s, greed_weight=2.0)
    with pytest.raises(ValueError):  # both sides disabled is meaningless
        FearGreedGated(_Const(1.0), s, greed_threshold=None, fear_threshold=None)


def test_fear_side_cuts_in_extreme_fear():
    s = _series([10, 10], start=0)  # extreme fear
    # greed side off, fear side on (cut at <=25)
    gated = FearGreedGated(
        _Const(1.0), s, greed_threshold=None, fear_threshold=25, fear_weight=0.0
    )
    assert gated.signal([_candle(1)]) == 0.0


def test_fear_side_passthrough_when_not_fearful():
    s = _series([60, 60], start=0)  # greed-ish, not fear
    gated = FearGreedGated(
        _Const(0.7), s, greed_threshold=None, fear_threshold=25, fear_weight=0.0
    )
    assert gated.signal([_candle(1)]) == pytest.approx(0.7)


def test_both_extremes_hold_only_in_middle():
    # cut at greed>=75 AND fear<=25 -> hold only in [26,74]
    mid = _series([50, 50], start=0)
    greed = _series([80, 80], start=0)
    fear = _series([10, 10], start=0)
    kw = dict(greed_threshold=75, fear_threshold=25)
    assert FearGreedGated(_Const(1.0), mid, **kw).signal([_candle(1)]) == pytest.approx(
        1.0
    )
    assert FearGreedGated(_Const(1.0), greed, **kw).signal([_candle(1)]) == 0.0
    assert FearGreedGated(_Const(1.0), fear, **kw).signal([_candle(1)]) == 0.0
