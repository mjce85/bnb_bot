"""Render a :class:`BacktestResult` + :class:`Metrics` into an honest report.

Output is a markdown file (the scored numbers, the run's parameters, and the
honesty caveats) plus a two-panel PNG — equity curve on top, drawdown beneath.
The markdown is plain text so it diffs and commits cleanly; the PNG is a local
artifact (gitignored).

Honesty is the product, so the report states its own caveats inline: which
window it covers, that costs are modelled (not free), and — when relevant — that
in-sample numbers are not an out-of-sample edge. The caller passes the caveat
list; this module just renders it.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from bnb_bot.metrics import Metrics
from bnb_bot.types import BacktestResult


def _iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _ratio(x: float) -> str:
    if x == float("inf"):
        return "∞"
    if x == float("-inf"):
        return "−∞"
    return f"{x:.2f}"


def _metric_table(m: Metrics) -> str:
    rows = [
        ("Total return", _pct(m.total_return)),
        ("CAGR", _ratio(m.cagr) if abs(m.cagr) == float("inf") else _pct(m.cagr)),
        ("Max drawdown", _pct(m.max_drawdown)),
        ("Sharpe (ann.)", _ratio(m.sharpe)),
        ("Sortino (ann.)", _ratio(m.sortino)),
        ("Calmar", _ratio(m.calmar)),
        ("Win rate", _pct(m.win_rate)),
        ("Exposure (time in mkt)", _pct(m.exposure)),
        ("Trades", str(m.n_trades)),
        ("Bars", str(m.n_bars)),
    ]
    lines = ["| Metric | Value |", "| --- | ---: |"]
    lines += [f"| {k} | {v} |" for k, v in rows]
    return "\n".join(lines)


def _equity_drawdown_plot(result: BacktestResult, path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")  # headless: no display, just write a file
    import matplotlib.pyplot as plt

    ts = [
        datetime.fromtimestamp(t / 1000.0, tz=timezone.utc)
        for t, _ in result.equity_curve
    ]
    equity = [e for _, e in result.equity_curve]

    # Running drawdown as a positive percentage.
    peak = equity[0]
    dd = []
    for e in equity:
        peak = max(peak, e)
        dd.append((peak - e) / peak * 100.0 if peak > 0 else 0.0)

    fig, (ax_eq, ax_dd) = plt.subplots(
        2, 1, figsize=(10, 6), sharex=True, height_ratios=[3, 1]
    )
    ax_eq.plot(ts, equity, color="#2563eb", linewidth=1.2)
    ax_eq.set_ylabel("Equity (USD)")
    ax_eq.set_title(f"{result.strategy} — {result.symbol}")
    ax_eq.grid(True, alpha=0.3)

    ax_dd.fill_between(ts, dd, 0, color="#dc2626", alpha=0.4)
    ax_dd.set_ylabel("Drawdown (%)")
    ax_dd.invert_yaxis()  # deeper drawdowns hang lower
    ax_dd.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def render_report(
    result: BacktestResult,
    metrics: Metrics,
    *,
    out_dir: str = "reports",
    label: str | None = None,
    caveats: list[str] | None = None,
    plot: bool = True,
) -> str:
    """Write a markdown report (and PNG plot) for one run; return the .md path.

    ``label`` distinguishes filenames when one run is split into windows
    (e.g. ``"in_sample"`` / ``"out_of_sample"``). ``caveats`` are rendered as a
    bullet list under an Honesty section.
    """
    os.makedirs(out_dir, exist_ok=True)
    safe_symbol = result.symbol.replace("/", "-")
    stem = f"{result.strategy}_{safe_symbol}"
    if label:
        stem += f"_{label}"

    plot_rel = f"{stem}.png"
    if plot:
        _equity_drawdown_plot(result, os.path.join(out_dir, plot_rel))

    start_iso, end_iso = _iso(result.window[0]), _iso(result.window[1])
    params_str = (
        ", ".join(f"{k}={v}" for k, v in result.params.items())
        if result.params
        else "(defaults)"
    )

    parts = [
        f"# Backtest — {result.strategy} on {result.symbol}",
        "",
        f"**Window:** {start_iso} → {end_iso}  ",
        f"**Parameters:** {params_str}",
        "",
        "## Metrics",
        "",
        _metric_table(metrics),
        "",
    ]
    if plot:
        parts += [f"![equity and drawdown]({plot_rel})", ""]

    parts += ["## Honesty notes", ""]
    base_caveats = [
        "Every simulated fill pays swap fee + slippage + gas (see `config.CostModel`).",
        "Signals at bar *t* use only data ≤ *t*; fills land at the next bar's open.",
    ]
    for c in base_caveats + (caveats or []):
        parts.append(f"- {c}")
    parts.append("")

    md = "\n".join(parts)
    md_path = os.path.join(out_dir, f"{stem}.md")
    with open(md_path, "w") as f:
        f.write(md)
    return md_path
