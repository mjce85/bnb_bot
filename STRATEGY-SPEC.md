# STRATEGY-SPEC.md — Risk-Controlled Regime Momentum

**A self-contained, backtestable specification.** This document defines the
strategy precisely enough that an independent party can re-implement it from
scratch, or re-run our implementation on a *held-out market window after
submission lock* and reproduce the class of result we claim. It is the formal
Track 2 deliverable; the prose pitch lives in [`README.md`](README.md), the full
research narrative (including dead-ends) in [`FINDINGS.md`](FINDINGS.md).

Strategy identifier: **`vol_targeted_regime_momentum`** (frozen in
[`bnb_bot/presets.py`](bnb_bot/presets.py) as `VOL_TARGETED_REGIME_MOMENTUM`).

---

## 1. Scope and claim

- **Universe:** liquid spot tokens quoted in USDT. Validated on BNB, BTC, ETH,
  CAKE (the search set) and 14 further tokens it was never tuned on.
- **Direction:** long-only spot. No shorting, no leverage, no derivatives.
- **Bar size:** daily (`1d`).
- **The claim we stand behind:** *for the same market direction, this strategy
  cuts maximum drawdown to roughly one-third to one-half of buy-and-hold, in
  every regime tested and in 95.6% of bootstrap resamples.* The headline
  **returns** are real in-sample but uncertain and cost-sensitive — we do not
  claim to out-return a crypto bull market. The durable edge is **risk control**,
  which is exactly what Track 2 judges (drawdown, risk-adjusted performance, rule
  adherence).

## 2. Inputs

| Input | Definition |
| --- | --- |
| Candles | OHLCV bars `(timestamp, open, high, low, close, volume)`, contiguous, daily. Sourced from Binance spot via `ccxt` (free, no key); gaps fail loud (`DataGapError`). |
| Starting equity | $10,000 (USD). |
| Cost model | Charged on **every** fill: swap fee **0.25%**, slippage **10 bps**, gas **$0.30** flat. (PancakeSwap-v2-style; see §7 caveat.) |

## 3. The signal — target weight at bar *t*

At each bar *t* the strategy sees only the **causal slice** `candles[0 : t+1]`
(every bar up to and including *t*, nothing after) and emits a **target weight**
`w ∈ [0, 1]` = the fraction of equity it wants held in the asset. The weight is
computed by composing three layers; each is a pure function of the causal slice.

Let `closes = [c.close for c in history]`.

### 3.1 Regime gate (outermost) — `trend_period = 50`

```
if len(closes) < 50:           w = 0          # warmup
sma50 = mean(closes[-50:])
if closes[-1] <= sma50:        w = 0          # downtrend regime -> cash
else:                          w = momentum_weight   # uptrend -> defer to momentum
```

The gate forces the book **flat in any sustained downtrend**, so the strategy
never fights the tide or catches falling knives. This is the single biggest
driver of the drawdown reduction.

### 3.2 Momentum base — EMA crossover, `fast = 12`, `slow = 26`

Only consulted when the regime gate is "up".

```
if len(closes) < 26:           momentum_weight = 0    # warmup
fast = EMA(closes, 12)
slow = EMA(closes, 26)
momentum_weight = 1.0 if fast > slow else 0.0
```

`EMA(values, p)` is the standard exponential moving average, `alpha = 2/(p+1)`,
seeded on `values[0]`.

### 3.3 Volatility targeting (sizing) — `target_vol = 0.015`/day, `vol_lookback = 15`

Applied to the (regime-gated) base weight to hold roughly **constant risk**
rather than constant capital.

```
if base_weight <= 0:           w = 0
if len(closes) < 16:           w = 0                  # warmup (need 15 returns)
rets = simple returns of closes[-16:]                # 15 daily returns
vol  = population stdev(rets)
scale = 1.0 if vol <= 0 else min(1.0, 0.015 / vol)
w = clamp(base_weight * scale, 0, 1)
```

Calm markets → `scale` near 1 (full exposure); turbulent markets → `scale`
shrinks, cutting exposure so a wild regime cannot inflict a large drawdown.
`max_weight = 1.0` (long-only spot cap — no leverage).

## 4. Execution model — how a weight becomes fills

The engine ([`bnb_bot/backtest.py`](bnb_bot/backtest.py)) is an event-driven
counterfactual simulator. Per bar:

1. **Signal at *t*** from the causal slice (§3).
2. **Rebalance band — `0.15`.** The target position is only adjusted if the
   target weight differs from the current weight by more than **15 percentage
   points**. This quarters turnover versus rebalancing every bar, which is what
   makes the return survive realistic costs.
3. **Fill at *t+1* open.** Any trade fills at the **next** bar's open price —
   never the same bar's close. This is the structural no-look-ahead guarantee.
4. **Costs** (§2) are charged on the traded notional of every fill.
5. **Risk overlay** is applied (§5) and can only ever *reduce* exposure.

## 5. Risk rules (rule-adherence axis) — all hard, all loud

Enforced by [`bnb_bot/risk.py`](bnb_bot/risk.py) (`RuleBasedRisk`), in priority
order. Every rule only ever *lowers* risk; none can increase a position.

| Rule | Locked value | Behaviour |
| --- | --- | --- |
| Stop-loss | **10%** | Force a full exit if an open position moves 10% against entry. |
| Position-size cap | **100%** | Max fraction of equity in one position. |
| Total-exposure cap | **100%** | Max fraction of equity deployed at once (binds in the portfolio engine). |
| Drawdown breaker | **20%** | Halt *new* entries while equity is ≥20% below its campaign peak (peak resets when the book is flat — see §7). Trims/exits still allowed. |

## 6. Evaluation protocol — how the claim was validated

The whole point of the spec is that the number is *trustworthy*. Three anti-self-
deception guards, all reproducible from this repo:

1. **No look-ahead** — enforced structurally (§3, §4) and pinned by a test that
   feeds two series differing only in the future and asserts identical past fills.
2. **All costs charged** — no fee-free path through the engine; pinned by tests.
3. **No overfitting** — parameters were chosen by a bounded search
   ([`scripts/search_cost_robust.py`](scripts/search_cost_robust.py)) that (a)
   ranked configs on a **train split only**, (b) selected **one config across all
   tokens** (never per-coin), (c) ranked under a **conservative 2× cost
   assumption**, and (d) was validated **once** on an untouched 25% holdout.

Reported on a **walk-forward** basis (`bnb_bot/walkforward.py`) and benchmarked
against **buy-and-hold** on every run.

### Locked parameters (the entire spec, in one block)

```
strategy          = VolatilityTargeted(RegimeGated(Momentum(fast=12, slow=26),
                                                   trend_period=50),
                                       target_vol=0.015, vol_lookback=15)
rebalance_band    = 0.15
risk: stop_loss=0.10, position_cap=1.0, exposure_cap=1.0, drawdown_halt=0.20
costs: swap_fee=0.0025, slippage_bps=10, gas_usd=0.30
bars: daily; starting_equity = $10,000
```

### Headline result (full window 2021-01-01 → 2026-06-01, per token)

| Token | Strategy ret | B&H ret | Strategy maxDD | B&H maxDD | Strategy Calmar | B&H Calmar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BNB | +279% | +1781% | **23%** | 71% | **1.22** | 1.02 |
| BTC | +73% | +151% | **37%** | 77% | 0.29 | 0.24 |
| ETH | +77% | +175% | **32%** | 79% | 0.35 | 0.26 |
| CAKE | **+34%** | −92% | **31%** | 98% | 0.18 | −0.40 |

### Out-of-sample evidence (the honesty test)

- **Untouched holdout** (most recent 25%, scored once): beat B&H drawdown **4/4
  tokens**, return **3/4** (BNB +46% vs +2%, Sharpe 1.26 vs 0.29).
- **Generalization:** the frozen entry on **18 tokens** (14 never used to tune
  it), full Binance history incl. the 2018 bear: beat B&H drawdown **18/18**.
- **Bootstrap** (3,000 paired resamples): beat B&H drawdown in **95.6%**; return
  spread −63% … +823% (return is uncertain, drawdown is robust).
- **Regime slices** (2018 crash → 2023–24 recovery): drawdown control holds in
  **every** regime.

## 7. Honest limitations

- **Costs are modelled, not measured on-venue.** PancakeSwap-style fees on
  Binance prices; real on-chain slippage differs and is size-dependent. The
  **drawdown control survives 3× costs**; the **return** stays positive only to
  2× (+15%), negative at 3× (−18%). Treat the return as cost-dependent.
- **Long-only spot** cannot out-return a sustained bull market — we trade upside
  for much lower drawdown by design.
- **Drawdown-breaker semantics:** the breaker measures drawdown since the book
  was last flat (campaign peak). This catches drawdown *within* a held position
  but not slow bleed across many small trades — volatility targeting is the tool
  for that. Documented, not hidden.
- **One historical path.** 2021–2026 is a single sequence of regimes; the holdout
  and 18-token generalization make the result credible, not guaranteed.

## 8. Reproduce

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python scripts/run_entry.py          # -> reports/entry_summary.md
./venv/bin/python scripts/run_portfolio.py      # -> reports/portfolio_summary.md
./venv/bin/python scripts/search_cost_robust.py # re-runs the validated search
./venv/bin/python -m pytest -q                  # the engine's credibility
```
