"""Tests for the markdown/plot report and the CLI's pure helpers.

The report is rendered into a tmp dir (no committing of artifacts), and we
assert the markdown carries the scored numbers and honesty notes, and that the
PNG is actually written. CLI date parsing is checked for fail-loud behaviour.
"""

from __future__ import annotations

import os
import sys

import pytest

from bnb_bot.metrics import compute_metrics
from bnb_bot.report import render_report
from bnb_bot.types import BacktestResult, Fill, Side

HOUR = 60 * 60 * 1000

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from run_backtest import parse_date_ms  # noqa: E402


def _result() -> BacktestResult:
    curve = [(i * HOUR, 10_000.0 + i * 5.0) for i in range(50)]
    fills = [
        Fill(
            ts=HOUR,
            symbol="BNB/USDT",
            side=Side.BUY,
            base_qty=1.0,
            price=100.0,
            fee_usd=0.3,
        ),
        Fill(
            ts=10 * HOUR,
            symbol="BNB/USDT",
            side=Side.SELL,
            base_qty=1.0,
            price=120.0,
            fee_usd=0.3,
        ),
    ]
    return BacktestResult(
        strategy="momentum_ema_cross",
        symbol="BNB/USDT",
        window=(0, 49 * HOUR),
        params={"fast_period": 12, "slow_period": 26},
        equity_curve=curve,
        fills=fills,
    )


def test_render_writes_markdown_and_plot(tmp_path):
    res = _result()
    m = compute_metrics(res)
    md_path = render_report(res, m, out_dir=str(tmp_path))

    assert os.path.exists(md_path)
    png_path = md_path[:-3] + ".png"
    assert os.path.exists(png_path)

    text = open(md_path).read()
    assert "momentum_ema_cross" in text
    assert "BNB/USDT" in text
    assert "Total return" in text
    assert "Max drawdown" in text
    assert "Sharpe" in text
    assert "fast_period=12" in text
    # Honesty notes always present.
    assert "Honesty notes" in text
    assert "swap fee" in text


def test_render_caveats_and_label(tmp_path):
    res = _result()
    m = compute_metrics(res)
    md_path = render_report(
        res,
        m,
        out_dir=str(tmp_path),
        label="out_of_sample",
        caveats=["This is the held-out window."],
    )
    assert md_path.endswith("out_of_sample.md")
    text = open(md_path).read()
    assert "This is the held-out window." in text


def test_render_without_plot_skips_png(tmp_path):
    res = _result()
    m = compute_metrics(res)
    md_path = render_report(res, m, out_dir=str(tmp_path), plot=False)
    png_path = md_path[:-3] + ".png"
    assert not os.path.exists(png_path)


def test_parse_date_ms_roundtrip():
    # 2024-01-01 UTC midnight.
    assert parse_date_ms("2024-01-01") == 1_704_067_200_000


def test_parse_date_ms_fails_loud():
    with pytest.raises(SystemExit, match="bad date"):
        parse_date_ms("01/01/2024")
