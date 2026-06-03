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
- [x] **T3 — backtest.py engine.** DONE (commit 5e49753). Event-driven
      target-weight engine: signal at *t* from causal slice, fill at *t+1* open,
      fees+slippage+gas on every fill; equity curve + fills. 9 tests assert
      no-lookahead (future-invariance + fill timing) and exact fee math.
- [x] **T4 — metrics.py.** DONE. `compute_metrics(result)` -> total return,
      CAGR, max drawdown, Sharpe, Sortino, Calmar, win rate, exposure %.
      Stdlib-only; annualization inferred from bar spacing; degenerate cases
      (flat equity, no drawdown, micro-window) handled loud, not papered over.
      8 hand-computed tests green.
- [x] **T5 — risk.py.** DONE. `RuleBasedRisk(limits)` satisfies the engine's
      RiskManager Protocol: stop-loss (forces exit) > position-size cap >
      total-exposure cap > drawdown breaker (halt new entries, allow trims).
      Every rule only lowers risk. 9 tests, one per rule + engine integration.
- [x] **T6 — strategy.py.** DONE. `Strategy` ABC implements the engine's real
      `signal(history)->float` contract (reconciled from the PLAN's
      `generate_signals` sketch — the engine never consumed that). Baselines:
      `Momentum` (EMA crossover, pure) + `MeanReversion` (z-score band w/
      hysteresis). Frozen param dataclasses, validated, no magic numbers. 11
      tests green.
- [x] **T7 — report.py + run_backtest.py CLI.** DONE. `render_report` writes a
      markdown metric table + honesty notes + a two-panel equity/drawdown PNG
      (matplotlib Agg) into `reports/`. CLI `scripts/run_backtest.py` wires
      data→strategy→risk→backtest→metrics→report with fail-loud date parsing.
      5 tests (tmp_path, no committed artifacts) green.
- [x] **T8 — baseline run.** DONE. `scripts/run_baseline.py` swept 4 tokens ×
      2 strategies × {in-sample 70% / out-of-sample 30%} over 2024-06→2026-06
      hourly. Per-run reports + `reports/baseline_summary.md`. Result: both
      baselines lose heavily in BOTH windows; the lone in-sample winner (CAKE
      momentum +75%) collapses to -55% OOS — textbook overfit. See FINDINGS.md.
- [x] **T9 — STOP. Write `FINDINGS.md`** (see gate below) and halt. DONE.
      FINDINGS.md written: baselines have no edge (lose in both windows, even in
      bull in-sample), one in-sample winner is overfit, drawdowns 45–99%,
      Sharpe negative in 15/16 runs. Recommendation: don't tune — cut trade
      frequency + apply the existing risk layer, or rethink the arena. HALTED.

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
