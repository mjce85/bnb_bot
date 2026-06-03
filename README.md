# bnb_bot — a disciplined, honestly-backtested trading strategy

**BNB HACK — AI Trading Agent · Track 2 (backtestable strategy engine)**

> Our edge is not the biggest number. It's a strategy whose backtest you can
> *trust*, that controls drawdown by design, and that proves itself on data it
> was never tuned on.

`bnb_bot` is a strategy engine that generates and backtests trading strategies
on liquid BNB-ecosystem tokens. The shippable entry is **volatility-targeted,
regime-gated momentum**: it rides uptrends, sits in cash during downtrends, and
scales its exposure down when markets get turbulent — cutting drawdown to a
fraction of buy-and-hold while staying profitable.

This milestone is **backtest + report only**. No live trading, no orders, no
keys, no capital at risk.

---

## Why this entry

The judged axes are **returns, max drawdown, risk-adjusted performance, and rule
adherence**. We built to the last three deliberately. A long-only spot strategy
cannot out-return a crypto bull market — and any strategy that *claims* to is
usually lying to itself through one of the three classic backtest mistakes. So we
made two things our product:

1. **A backtester that cannot lie** (see *Backtest honesty* below).
2. **Disciplined risk control** — a strategy that reliably halves drawdown and
   preserves capital in crashes, validated on a strict out-of-sample holdout.

## The strategy, in plain terms

Three layers, each fixing a real failure we measured in naive baselines:

- **Momentum** — go long when the short-term trend is up (EMA crossover).
- **Regime gate** — *only* hold when price is above its long (50-day) moving
  average. In a sustained downtrend the strategy is flat (in cash), so it never
  fights the tide or "catches falling knives."
- **Volatility targeting** — size the position for a constant *risk* budget, not
  constant capital: lean in when markets are calm, shrink when they're wild.

On top sits a **risk layer**: a per-trade stop-loss and a drawdown breaker that
halts new entries during a deep drawdown.

The exact, frozen parameters live in
[`bnb_bot/presets.py`](bnb_bot/presets.py) (`VOL_TARGETED_REGIME_MOMENTUM`) and
were chosen by a holdout-validated search, not by hand.

## Backtest honesty — the three lies we guard against

This is the core of the product. Each guard is enforced in code and pinned by
tests:

1. **No look-ahead.** A signal at bar *t* sees only data with timestamp ≤ *t*,
   and every fill happens at the *next* bar's open — never the same bar's close.
   Tested by feeding two series that differ only in the future and asserting
   identical past fills.
2. **All costs modelled.** Every simulated fill pays a swap fee + slippage + gas.
   There is no fee-free path through the engine.
3. **No overfitting.** Results are reported on a **walk-forward** basis and on an
   **untouched 25% holdout** the parameter search never saw. Strategy parameters
   are chosen once, across all tokens — never cherry-picked per coin.

If a metric can't be computed honestly, the code raises rather than inventing a
number.

## Headline results

Daily bars, 2021 … 2026, four tokens (BNB, CAKE, ETH, BTC). Every fill pays
costs; signals are causal.

![strategy vs buy & hold — equity and drawdown](docs/headline.png)

*Blue = strategy, grey = buy & hold. The right column is the story: our drawdowns
are a fraction of holding's, on every token.*

**Full window — strategy vs buy & hold (max drawdown is the story):**

| Token | Strategy return | B&H return | Strategy maxDD | B&H maxDD |
| --- | ---: | ---: | ---: | ---: |
| BNB | +279% | +1781% | **23%** | 71% |
| BTC | +73% | +151% | **37%** | 77% |
| ETH | +77% | +175% | **32%** | 79% |
| CAKE | **+34%** | −92% | **31%** | 98% |

Drawdown is roughly **one-third to one-half** of buy-and-hold across the board,
and the strategy stays *positive even in CAKE, which lost 92% over the period.*
BNB's Calmar (return per unit drawdown) is **1.22 vs holding's 1.02** — more
return per unit of risk than just holding the best performer.

**Untouched holdout (most recent 25%, scored once) — the honesty test:**

The strategy beat buy-and-hold's **drawdown on 4/4 tokens** and its **return on
3/4** on data the search never touched. On BNB it returned **+46% vs +2%** at a
**Sharpe of 1.26 vs 0.29**; on ETH **+39% vs −38%** (Sharpe 1.02 vs −0.13). Full
detail in
[`reports/search_cost_robust_summary.md`](reports/search_cost_robust_summary.md).

**Generalization (the strongest overfitting check):** the *frozen* entry, run on
**18 liquid tokens** (14 never used to choose its parameters), each over its full
Binance history back to 2017 — including the brutal 2018 bear our 2021-start tests
never saw — beat buy-and-hold's drawdown on **18/18**, cutting max drawdown
roughly in **half on average**. It made money in many coins that holders watched
collapse (FIL +79% vs −99%, ADA +429% vs −3%, EOS −3% vs −94%).

![drawdown across 18 tokens](docs/generalization.png)

Detail in [`reports/generalization_summary.md`](reports/generalization_summary.md);
per-asset equity curves in [`docs/performance_all.png`](docs/performance_all.png).

**Traded as a portfolio (what you'd actually run):**

![portfolio vs equal-weight buy & hold](docs/portfolio.png)

Run across all four tokens on one shared book, the strategy returns **+85% vs an
equal-weight buy-and-hold portfolio's +8%**, at **57% vs 80% max drawdown**, and
beats hold's drawdown in **5 of 5 walk-forward folds**. Two honest caveats: (a)
the portfolio's drawdown (57%) is *higher* than the single-token average (31%) —
these tokens are correlated and the portfolio deploys idle cash, so the win is
capital efficiency vs holding, not diversification; (b) the return is somewhat
**cost-sensitive** (the strategy trades) — it stays positive at 2× our assumed
costs (**+15%**) and goes negative only at 3× (−18%), while the **drawdown control
survives at every cost level**. (This is after deliberately re-tuning turnover
down to harden it — see `FINDINGS.md` Stage 7.) Detail in
[`reports/portfolio_summary.md`](reports/portfolio_summary.md) and
[`reports/robustness_summary.md`](reports/robustness_summary.md).

## Reproduce it

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

# Reproduce the headline entry result (fetches free Binance history via ccxt):
./venv/bin/python scripts/run_entry.py        # -> reports/entry_summary.md

# Re-run the holdout-validated search that picked the locked entry:
./venv/bin/python scripts/search_cost_robust.py   # -> reports/search_cost_robust_summary.md

# Stress tests: cost sensitivity + out-of-universe generalization:
./venv/bin/python scripts/run_robustness.py   # -> reports/robustness_summary.md

# Run any single strategy/token/window and get a report + equity/drawdown plot:
./venv/bin/python scripts/run_backtest.py --symbol BNB/USDT \
    --start 2022-01-01 --end 2025-01-01 --strategy momentum --risk

# Tests (the backtest's credibility lives here):
./venv/bin/python -m pytest -q
```

Historical OHLCV comes from `ccxt` (Binance spot, free, no key) cached as
parquet under `data/` (gitignored).

## Repository layout

```
bnb_bot/
  config.py       cost model + risk limits (range-validated)
  types.py        core dataclasses (Candle, Signal, Fill, Position, ...)
  data.py         ccxt OHLCV loader + parquet cache + fail-loud gap detection
  backtest.py     event-driven engine: no-lookahead, costs on every fill
  strategy.py     Momentum, MeanReversion, TrendFollowing + RegimeGated /
                  VolatilityTargeted composable wrappers
  risk.py         stop-loss, position/exposure caps, drawdown breaker
  metrics.py      return, drawdown, Sharpe, Sortino, Calmar, win rate, exposure
  walkforward.py  buy-and-hold benchmark + walk-forward evaluation
  portfolio.py    multi-asset portfolio engine (shared book, exposure caps)
  report.py       markdown report + equity/drawdown plot
  presets.py      the frozen, validated submission entry
scripts/          run_backtest · run_entry · run_portfolio · search_params · …
tests/            89 tests pinning the engine, metrics, risk, and strategies
```

## Honest limitations

- **Costs are modelled, not measured on-venue.** We charge PancakeSwap-style
  fees on Binance price data; real on-chain slippage would differ (and is size-
  dependent). We stress-tested this and re-tuned turnover down to harden it: the
  **drawdown control is robust** (holds at 3× costs) and the portfolio return now
  **stays positive at 2× assumed costs (+15%)**, going negative only at 3×.
  Still, treat the headline return as cost-dependent; the risk-control story is
  the more durable claim.
- **Long-only spot.** In a strong, steady bull market, buy-and-hold out-returns
  us — we trade upside for much lower drawdown. That trade-off is the point.
- **One historical path.** 2021–2026 is a single sequence of regimes. The
  holdout and cross-token validation make the result credible, not guaranteed.

## Status & scope

Backtest + report only. The Trust Wallet / BNB Chain execution layer is a later,
operator-gated concern; until then this repo moves no money and performs no
irreversible action. See [`FINDINGS.md`](FINDINGS.md) for the full research
narrative — including the dead-ends — and [`PLAN.md`](PLAN.md) for the build log.
