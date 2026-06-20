# Cadence — discipline over hype

**BNB HACK — AI Trading Agent · Track 2 (backtestable strategy engine)**

![strategy vs buy & hold — equity and drawdown](docs/headline.png)

*Blue = our strategy, grey = buy & hold. Right column is the point: our drawdowns
are a fraction of holding's, on every token.*

## Inspiration

Most "winning" trading backtests are fiction. They peek at the future, ignore
fees, or are tuned until they look good on the one stretch of history the author
happened to test. In a crypto bull market it's easy to show a big number and
impossible to know if it means anything. We wanted to build the opposite: a
strategy whose backtest you can *trust*, that wins on the axis we can actually
control — **risk** — and that proves itself on data it was never tuned on.

## What it does

`bnb_bot` generates and backtests trading strategies for liquid BNB-ecosystem
tokens. Our entry is **volatility-targeted, regime-gated momentum**:

- **Momentum** rides uptrends.
- A **regime gate** keeps it in *cash* whenever price is below its long trend —
  so it never fights a sustained downturn.
- **Volatility targeting** sizes for constant risk: lean in when calm, scale down
  when wild.
- A **risk layer** (stop-loss + drawdown breaker) backstops the position.

The result, over 2021–2026 daily across BNB/CAKE/ETH/BTC: **max drawdown of
23–37% versus buy-and-hold's 71–98%** — roughly a third to a half — while staying
profitable on every token, including CAKE, which lost 92% buy-and-hold.

## How we built it

A small, fully-tested Python engine (no framework magic):

- **Event-driven backtester** that structurally cannot commit the three classic
  backtest lies — no look-ahead, costs on every fill, overfitting guarded at the
  experiment level.
- **Composable strategies** — momentum / mean-reversion / trend-following, with
  `RegimeGated`, `VolatilityTargeted`, and `FearGreedGated` wrappers that stack
  cleanly.
- **Walk-forward evaluation + buy-and-hold benchmark** baked into every result.
- **A bounded parameter search** with an untouched 25% holdout and one config
  chosen across all tokens — anti-overfitting by construction.
- **131 tests** pinning the engine's honesty and the locked entry.
- **Live CMC data, used honestly** — pulls CoinMarketCap's Fear & Greed + BTC
  dominance for live context; we backtested *gating* on Fear & Greed and reported
  that it doesn't improve risk-adjusted returns, so we use it as context, not a
  trigger.

## Challenges we ran into

- **Naive baselines failed loudly** — hourly momentum/mean-reversion bled to
  death on fees (hundreds of trades) and lost even in bull markets. We kept the
  honest negative result and redesigned around it (daily bars, regime filter).
- **Our own risk module had a bug** — the drawdown breaker permanently locked the
  strategy out after one rough patch. We found it because exposure collapsed to
  2%, diagnosed it, and fixed it (campaign-peak reset) rather than shipping a
  flattering-but-broken number.

## Accomplishments we're proud of

- **Drawdown beaten on 4/4 tokens on an untouched holdout** — and 3/4 on return.
  On BNB's holdout: **+46% vs +2%, Sharpe 1.26 vs 0.29**; on ETH **+39% vs −38%.**
  It held up out of sample.
- **Traded as a portfolio across all four tokens: +85% vs equal-weight
  buy-and-hold's +8%, at 57% vs 80% drawdown** — drawdown beaten in 5/5
  walk-forward folds. (Honestly: the portfolio runs hotter than a single token —
  these coins are correlated — so the win is capital efficiency vs holding, not
  diversification.)
- **It generalizes — emphatically.** Run *frozen* on **18 liquid tokens** over
  their full history back to 2017 (including the 2018 bear), it beat
  buy-and-hold's drawdown on **18/18**, cutting drawdown ~half on average. See
  `docs/generalization.png`.
- **It beat its competition in a fair bake-off** — run against three respected
  challengers (Donchian breakout, time-series momentum, dual-momentum rotation) on
  the identical rig, the entry won the portfolio outright on return, drawdown, and
  Calmar; the flashy rotation collapsed (−63%). We even validated the one
  improvement the bake-off hinted at and it was a wash — so we changed nothing.
- **A backtester we'd actually believe** — every honesty guard is enforced in
  code and tested (131 tests).

## What we learned

There is no easy long-only alpha in liquid crypto — we proved it to ourselves
with blunt negative results. But there *is* a durable edge in **discipline**:
cutting drawdown in half, consistently and out-of-sample, is a real, defensible
product, even when raw return trails a roaring bull market. We also learned where
*not* to trust ourselves: stress-testing showed our returns were **fragile to
costs** (the strategy traded a lot), so we re-tuned turnover down — returns now
**survive 2× our assumed costs**, and the **drawdown control holds even at 3×**.
We still lead with the risk story, not the return.

## What's next

- A multi-objective **strategy-search engine** on top of the validated harness.
- The **Trust Wallet / BNB Chain execution layer** — gated behind review; this
  milestone moves no money.
- Live latest-quote integration (CMC free tier) for a paper-trading demo.

## Reproduce in one command

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python scripts/run_entry.py        # headline result
./venv/bin/python -m pytest -q                # 131 honesty/correctness tests
```

See [`README.md`](README.md) for detail, [`FINDINGS.md`](FINDINGS.md) for the
full research narrative (including the dead-ends), and
[`reports/search_summary.md`](reports/search_summary.md) for the holdout numbers.
