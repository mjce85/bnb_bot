---
name: risk-controlled-momentum
description: |
  Generate and honestly backtest a risk-controlled, long-only spot trading
  strategy (volatility-targeted, regime-gated momentum) on liquid crypto tokens.
  Produces a backtestable spec and a walk-forward / held-out evaluation that
  reports return, max drawdown, Sharpe, Sortino, and Calmar against a
  buy-and-hold benchmark — with no look-ahead, costs charged on every fill, and
  an untouched holdout to guard against overfitting.
  Use this skill whenever the user wants a backtestable trading strategy from
  market data, asks to evaluate a strategy's drawdown / risk-adjusted
  performance, wants to reproduce the BNB HACK Track 2 entry, or asks "how would
  this strategy have done out of sample".
  Trigger: "backtest a strategy", "regime momentum", "risk-controlled strategy",
  "drawdown control", "walk-forward backtest", "BNB Track 2", "/risk-controlled-momentum"
user-invocable: true
allowed-tools:
  - Bash
  - Read
---

# Risk-Controlled Regime Momentum — strategy skill

This skill generates and **honestly backtests** a long-only spot strategy whose
edge is *disciplined risk control*, not raw return. It rides uptrends, sits in
cash during downtrends, and scales exposure down when markets turn turbulent —
cutting max drawdown to roughly a third-to-a-half of buy-and-hold while staying
profitable across 18 tokens it was never tuned on.

It is built for evaluation criteria that reward **return, max drawdown,
risk-adjusted performance, and rule adherence** (BNB HACK Track 2). The full
formal definition is in [`STRATEGY-SPEC.md`](../../STRATEGY-SPEC.md); this skill
is how an agent *operates* it.

## What this skill does NOT do

No live trading, no orders, no private keys, no capital at risk. It produces a
**backtest + report only**. A live execution layer (Trust Wallet / BNB Chain) is
a separate, operator-gated concern and is deliberately out of scope.

## When to use it

- "Give me a backtestable strategy for these tokens with controlled drawdown."
- "Reproduce / evaluate the locked entry and show me the numbers vs holding."
- "Would this hold up on a market window it was never fitted to?"

## The strategy in one paragraph

Three composable layers, each fixing a measured failure of naive baselines:
a **momentum** base (EMA-12/26 crossover) goes long in uptrends; a **regime gate**
(50-day SMA) forces the book flat in downtrends so it never fights the tide; and
**volatility targeting** (15-day lookback, 0.015/day target) sizes for constant
risk — leaning in when calm, shrinking when wild. A **risk overlay** (10%
stop-loss, 20% drawdown breaker) sits on top. Parameters are *frozen* and were
chosen by a holdout-validated search, not by hand.

## The three honesty guards (the core of the product)

1. **No look-ahead.** A signal at bar *t* uses only data with timestamp ≤ *t*;
   every fill happens at the *next* bar's open. Pinned by tests.
2. **All costs charged.** Every fill pays swap fee (0.25%) + slippage (10 bps) +
   gas ($0.30). There is no fee-free path through the engine.
3. **No overfitting.** Reported walk-forward and on an untouched 25% holdout the
   search never saw; one config chosen across all tokens, never per-coin.

If a metric cannot be computed honestly, the code raises rather than inventing a
number.

## Workflow

Prerequisite (once): install the engine this skill drives.

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
```

### Step 1 — Reproduce the locked entry (single tokens)

```bash
./venv/bin/python scripts/run_entry.py
```

Fetches free daily Binance history via `ccxt` (no key) on a cache miss, runs the
frozen preset per token, and writes `reports/entry_summary.md` plus a per-token
report with an equity/drawdown plot. Read the summary:

```bash
# Read: reports/entry_summary.md
```

### Step 2 — Trade it as a portfolio (what you'd actually run)

```bash
./venv/bin/python scripts/run_portfolio.py     # -> reports/portfolio_summary.md
```

One shared book across all tokens, total-exposure cap active, benchmarked vs an
equal-weight buy-and-hold portfolio over the full window + 5 walk-forward folds.

### Step 3 — Evaluate on unseen data / a new universe

```bash
# Generalization: frozen entry on 18 tokens, full history (incl. 2018 bear):
./venv/bin/python scripts/run_generalization.py   # -> reports/generalization_summary.md

# Any single token / window / strategy, with a report + plot:
./venv/bin/python scripts/run_backtest.py --symbol BNB/USDT \
    --start 2022-01-01 --end 2025-01-01 --strategy momentum --risk
```

To run the strategy on a **held-out window provided after submission** (the Track
2 judging mode), point `run_backtest.py` (or `run_entry.py`'s window constants) at
that date range — the frozen preset is applied unchanged; no re-fitting.

### Step 4 — Re-run the disciplined search (optional, proves it isn't hand-picked)

```bash
./venv/bin/python scripts/search_cost_robust.py   # -> reports/search_cost_robust_summary.md
```

### Step 5 — Confirm the engine's credibility

```bash
./venv/bin/python -m pytest -q     # 131 tests pin no-lookahead, costs, risk, metrics
```

### Step 6 — Today's stance + live CMC market context

```bash
./venv/bin/python scripts/live_context.py     # needs CMC_PRO_API_KEY in .env
```

Pulls **live** CoinMarketCap signals (Fear & Greed index + BTC dominance, free
Basic tier) and shows the locked entry's *current* target weight per token. The
sponsor-data touchpoint for the live demo — "here's the market context, here's
what the strategy says to do right now". Read-only; moves no money.

> **Honest note on Fear & Greed.** We backtested *gating* the strategy on CMC's
> Fear & Greed (both directions, two data sources) and it did **not** improve
> risk-adjusted performance — cutting in greed throws away bull-market upside, and
> the small gain from cutting in fear overlaps the volatility-targeting we already
> do. So F&G is shown as **market context, not a trade trigger**. See
> `reports/fear_greed_summary.md`. This is the discipline the strategy is built
> on: we don't ship a signal that doesn't prove out, even a sponsor's.

## Locked parameters

| Knob | Value | Role |
| --- | --- | --- |
| momentum EMAs | 12 / 26 | trend base |
| regime SMA | 50 | flat-in-downtrend gate |
| target vol | 0.015 / day | constant-risk sizing |
| vol lookback | 15 days | realized-vol window |
| rebalance band | 0.15 | turnover control (cost robustness) |
| stop-loss | 10% | per-trade hard exit |
| drawdown breaker | 20% | halt new entries in deep drawdown |

Frozen in [`bnb_bot/presets.py`](../../bnb_bot/presets.py) as
`VOL_TARGETED_REGIME_MOMENTUM` and pinned by tests so it cannot silently drift.

## Headline result (daily, 2021 → 2026)

| Token | Strategy ret | B&H ret | Strategy maxDD | B&H maxDD |
| --- | ---: | ---: | ---: | ---: |
| BNB | +279% | +1781% | **23%** | 71% |
| BTC | +73% | +151% | **37%** | 77% |
| ETH | +77% | +175% | **32%** | 79% |
| CAKE | **+34%** | −92% | **31%** | 98% |

Out of sample: beat buy-and-hold's drawdown on **4/4** holdout tokens and
**18/18** generalization tokens; in a 3,000-path bootstrap it beat hold's
drawdown **95.6%** of the time. Returns are real but cost-sensitive; **drawdown
control is the durable claim**.

## Outputs

- `reports/entry_summary.md` — per-token strategy vs buy-and-hold.
- `reports/portfolio_summary.md` — the portfolio result + walk-forward folds.
- `reports/<strategy>_<token>_<label>.md` — per-run metric tables.
- `reports/*.png` / `docs/*.png` — equity + underwater-drawdown figures.

## References

- [`STRATEGY-SPEC.md`](../../STRATEGY-SPEC.md) — the formal, self-contained spec.
- [`README.md`](../../README.md) — judge-facing pitch and full results.
- [`FINDINGS.md`](../../FINDINGS.md) — the research narrative, including dead-ends.

## Limitations

- Costs are modelled (PancakeSwap-style) on Binance prices, not measured
  on-venue; the return is cost-sensitive (positive to 2× costs), the drawdown
  control is robust to 3×.
- Long-only spot: in a strong steady bull market, buy-and-hold out-returns this —
  the trade is much lower drawdown for some upside. That trade-off is the point.
- One historical path (2021–2026); the holdout and 18-token tests make the
  result credible, not guaranteed.
