# bnb_bot

Guidance for Claude Code when working in this repository.

## What this is

`bnb_bot` is an entry for the **BNB HACK — AI Trading Agent** hackathon
(CoinMarketCap × Trust Wallet × BNB Chain, build window 3–21 Jun 2026).
We are building **Track 2**: a strategy engine that generates
**backtestable trading strategies** from market data, judged on
**returns, drawdown, risk-adjusted performance, and rule adherence**.

It reuses *patterns and discipline* from prior trading-bot projects — NOT
their code; this repo stands alone.

## Hard rules

- **No imports from sibling projects.** Port patterns by hand; this
  repo stands alone.
- **No live trading in this milestone.** Backtest + report only. No real
  capital, no orders, no private keys. The Trust Wallet execution layer is
  a *later* concern, gated behind operator review. Until then this repo
  moves no money and performs no outward/irreversible action.
- **Fail loud, don't paper over.** If historical data has gaps, if a
  config is missing, if a metric can't be computed honestly — raise a
  clear error naming what's wrong. A silent wrong number in a backtest is
  worse than a loud failure. Synthetic data is allowed ONLY in tests.
- **Backtest honesty is the whole product.** The core value: when the
  backtester says "strategy X earns Y over window W," that number must be
  trustworthy. Guard the three classic lies (see below) or the entry is
  worthless regardless of how good it looks.

## The three backtest lies to guard against

1. **Lookahead bias** — a signal at bar *t* may use ONLY data with
   timestamp ≤ *t*. Fills happen at the *next* bar's open, never the same
   bar's close. Tests must assert this.
2. **Unmodeled costs** — every simulated fill pays swap fee + slippage +
   gas. A fee-free backtest is fantasy. Defaults live in `config.py`.
3. **Overfitting** — reserve an out-of-sample / walk-forward holdout.
   Never report in-sample numbers as if they're the edge.

## Stack

Python 3.13. `ccxt` for historical OHLCV (Binance has spot history for
BSC-listed tokens — free, no key). `polars`/`pyarrow` for candle storage.
CMC free-tier key (reused from operator's secrets) only for *live* latest
quotes during any live window — NOT for historical (free tier lacks it).

## Process

Lean sprint. One `PLAN.md` with a task list; plain atomic git commits; run
`black` before committing; `pytest` must pass before any task is "done."
No GSD machinery in this repo.

## Operator

Single developer (`mjce85`). Business-minded, the
visionary — explain in plain language, lead with what something *does*.
The strategy *direction* is the operator's call; the engineering is ours.
