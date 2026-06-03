# PLAN.md — bnb_bot Track 2 sprint

**Target:** A trustworthy backtest engine + at least two baseline strategies
+ an honest backtest report, for the BNB HACK Track 2 ("strategy skills that
generate backtestable strategies"). Submission lock: **21 Jun 2026 12:00 UTC**.
Aim to have a shippable entry in **1–2 weeks**, scaffold within days.

**Judging axes (design to these):** returns · max drawdown · risk-adjusted
performance · rule adherence. Our differentiator is *disciplined risk control*
+ *backtest honesty*, not raw return.

---

## Architecture (lean)

```
bnb_bot/
  config.py     # constants: fees, slippage, gas, risk limits, token set, windows
  types.py      # Candle, Signal, Order, Fill, Position, BacktestResult dataclasses
  data.py       # ccxt OHLCV fetch -> parquet cache in data/; gap detection (fail loud)
  strategy.py   # Strategy ABC + baseline strategies (momentum, mean-reversion)
  risk.py       # risk rules: position sizing, max-drawdown breaker, stop-loss, exposure cap
  backtest.py   # event-driven simulator: no-lookahead, fees+slippage, equity curve
  metrics.py    # total return, max DD, Sharpe, Sortino, Calmar, win rate, exposure
  report.py     # BacktestResult -> markdown report (+ equity/DD plot)
scripts/
  run_backtest.py  # CLI: token(s), window, strategy, params -> report in reports/
tests/             # correctness tests (the backtest's credibility lives here)
```

**Engine model:** genuine *counterfactual* historical simulation (walk candles,
apply strategy, simulate fills). This is the OPPOSITE of imx_bot's recorder —
do not port recorder semantics, only the venue-adapter / typed-dataclass shape.

---

## Overnight autonomous task list

Each task: implement → `black` → `pytest` (green) → atomic git commit. Tasks are
ordered so each builds on a tested foundation. All work is code + backtests in
this sandbox repo — nothing irreversible, no money, safe to run unattended.

- [x] **T1 — config.py + types.py.** DONE (commit 45fa0a3). CostModel +
      RiskLimits (range-validated) + core dataclasses; 8 tests green.
- [x] **T2 — data.py.** DONE (commit da1ff52). ccxt Binance fetch + parquet
      cache + `assert_contiguous` fail-loud gap detection; 8 tests green; live
      fetch smoke-tested. **Overnight loop: start here, at T3.**
- [ ] **T3 — backtest.py engine.** Walk candles; signal at *t* sees only ≤ *t*;
      fill at *t+1* open; apply fees+slippage+gas; track positions + equity
      curve. **Tests assert no-lookahead and exact fee math** on a hand-computed
      fixture. This is the credibility core — over-test it.
- [ ] **T4 — metrics.py.** Equity curve -> total return, max drawdown, Sharpe,
      Sortino, Calmar, win rate, exposure %. Tests vs hand-computed values.
- [ ] **T5 — risk.py.** Position sizing (fraction of equity, capped), max-DD
      breaker (halt new entries past threshold — port the imx_bot breaker
      *concept*), per-trade stop-loss, max concurrent exposure. Tests per rule.
- [ ] **T6 — strategy.py.** Strategy ABC (`generate_signals(candles) -> Signal`)
      + two baselines: (a) **momentum** (e.g. EMA/breakout), (b) **mean-
      reversion** (e.g. z-score / RSI band). Param dataclasses, no magic numbers.
- [ ] **T7 — report.py + run_backtest.py CLI.** Produce a markdown report with
      the metric table + an equity/drawdown plot into `reports/`.
- [ ] **T8 — baseline run.** Run both strategies over the token set on an
      **in-sample window**, holding out the most recent ~30% as out-of-sample.
      Save reports. Report BOTH windows honestly — flag any in/out gap as
      likely overfit.
- [ ] **T9 — STOP. Write `FINDINGS.md`** (see gate below) and halt.

## 🛑 STOP-AND-WAIT GATE (do not cross autonomously)

After T9, **stop and wait for Markus.** Do NOT begin sharpening alpha,
sweeping parameters, or adding strategies beyond the two baselines. That is
where overfitting risk and "build something that runs but means nothing"
creep in — and it needs the operator's judgment on *direction*.

`FINDINGS.md` must answer, in plain language:
1. Do the baselines show *any* edge after fees, in-sample AND out-of-sample?
2. Where did out-of-sample diverge from in-sample (overfit signal)?
3. What's the honest risk-adjusted picture (drawdown, Sharpe/Sortino)?
4. Concrete recommendation: is there a thread worth pulling, or is the
   premise (we can find liquid-token alpha fast) not holding up?
5. Any data/cost-model caveats that make the numbers softer than they look.

Keep it blunt. A clear "the baselines don't beat fees, here's why" is a
*successful* overnight outcome — it saves Markus a week.

---

## Out of scope this milestone
- Live trading / Trust Wallet execution layer (later, gated on review).
- CMC paid tier (free tier covers live quotes; ccxt covers history).
- Perps / leverage (TWAK is spot-only; live perps play to our slowness).
- GitHub remote (local-only until Markus reviews the morning output).
