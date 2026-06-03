"""Walk-forward evaluation + a buy-and-hold benchmark.

The probe's one "winner" was an in-sample mirage, so from here on every result
is judged two ways: **across multiple consecutive unseen windows** (does it hold
up, or did one lucky stretch carry it?) and **against simply holding the token**
(did the strategy actually add anything over doing nothing?).

This is honest *evaluation*, not optimization: the strategy's parameters are
fixed, and each fold is scored independently. True walk-forward *optimization*
(re-fitting per fold) belongs to the later strategy-search phase — naming it
that here would overclaim. Each fold gets a freshly constructed strategy via the
``make_strategy`` factory, so stateful strategies never bleed state across folds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from bnb_bot import config
from bnb_bot.backtest import RiskManager, run_backtest
from bnb_bot.metrics import Metrics, compute_metrics
from bnb_bot.strategy import Strategy
from bnb_bot.types import BacktestResult, Candle


def buy_and_hold(
    candles: list[Candle],
    *,
    symbol: str,
    starting_equity: float = config.STARTING_EQUITY_USD,
    costs: config.CostModel = config.DEFAULT_COSTS,
) -> BacktestResult:
    """Benchmark: deploy 100% at the first fill and hold to the end.

    Runs through the real engine (so it pays exactly one honest entry cost and
    marks to market identically to any strategy). A wide rebalance band means it
    buys once and never churns afterward.
    """
    return run_backtest(
        candles,
        lambda history: 1.0,
        symbol=symbol,
        starting_equity=starting_equity,
        costs=costs,
        rebalance_band=1.0,  # buy once; never re-trim
        strategy_name="buy_and_hold",
    )


@dataclass(frozen=True)
class FoldResult:
    """One walk-forward fold: the strategy vs buy-and-hold over that window."""

    index: int
    window: tuple  # (start_ts, end_ts) epoch ms
    n_bars: int
    strategy_metrics: Metrics
    benchmark_metrics: Metrics

    @property
    def excess_return(self) -> float:
        """Strategy total return minus buy-and-hold total return."""
        return self.strategy_metrics.total_return - self.benchmark_metrics.total_return

    @property
    def beat_benchmark(self) -> bool:
        return self.excess_return > 0


def walk_forward(
    candles: list[Candle],
    make_strategy: Callable[[], Strategy],
    *,
    symbol: str,
    n_folds: int = 4,
    starting_equity: float = config.STARTING_EQUITY_USD,
    costs: config.CostModel = config.DEFAULT_COSTS,
    risk: Optional[RiskManager] = None,
) -> list[FoldResult]:
    """Score ``make_strategy()`` across ``n_folds`` consecutive windows.

    The series is cut into ``n_folds`` contiguous segments (the last absorbs any
    remainder). Each segment is backtested with a *fresh* strategy and compared
    to buy-and-hold over the same segment. Fails loud if the data can't support
    the requested number of folds.
    """
    n = len(candles)
    if n_folds < 1:
        raise ValueError(f"n_folds must be >= 1, got {n_folds}")
    fold_size = n // n_folds
    if fold_size < 2:
        raise ValueError(
            f"{n} bars cannot be split into {n_folds} folds of >=2 bars each; "
            "reduce n_folds or widen the window"
        )

    folds: list[FoldResult] = []
    for i in range(n_folds):
        start = i * fold_size
        end = n if i == n_folds - 1 else (i + 1) * fold_size
        seg = candles[start:end]

        strat = make_strategy()
        res = run_backtest(
            seg,
            strat,
            symbol=symbol,
            starting_equity=starting_equity,
            costs=costs,
            risk=risk,
            strategy_name=strat.name,
            params=strat.params,
        )
        bench = buy_and_hold(
            seg, symbol=symbol, starting_equity=starting_equity, costs=costs
        )
        folds.append(
            FoldResult(
                index=i,
                window=(seg[0].ts, seg[-1].ts),
                n_bars=len(seg),
                strategy_metrics=compute_metrics(res),
                benchmark_metrics=compute_metrics(bench),
            )
        )
    return folds
