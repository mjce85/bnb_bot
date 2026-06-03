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

**Gate outcome (operator decision):** baselines confirmed no edge. Markus chose
the **robust redesign** thread (Stage 2 below) over a parameter search or an
arena change.

---

## Stage 2 — Robust redesign (operator-approved 2026-06-03)

Attack the three killers the probe found: fees, long-only-in-downtrends, and
overfit. Same discipline: implement → `black` → `pytest` (green) → atomic commit
→ mark `[x]`. Daily bars, ~5y history (2021→2026), risk-on with the single-asset
position cap opened to 100% (stop-loss + drawdown breaker still active).

- [ ] **R1 — regime filter + low-turnover strategies.** Add `TrendFollowing`
      (long above a long SMA, else cash — native downtrend avoidance) and a
      composable `RegimeGated(base, trend_period)` wrapper that forces any base
      strategy flat unless the long trend is up. Tests per behaviour.
- [ ] **R2 — walk-forward + benchmark harness.** `bnb_bot/walkforward.py`:
      `buy_and_hold(candles)` benchmark result + `walk_forward(...)` that scores
      a (fresh) strategy across N consecutive unseen folds vs buy-and-hold.
      Tests vs hand-checked folds.
- [x] **R3 — robust baseline run.** DONE. `scripts/run_robust.py`: daily, 2021→
      2026, 3 regime-aware strategies × 4 tokens, full-window + 5-fold walk-forward
      vs buy-and-hold. Headline read switched to **risk-off** after discovering a
      drawdown-breaker **lockout bug** (risk-on collapses exposure to ~2%); the
      bug is surfaced in `reports/robust_summary.md`, not hidden. Result: cuts
      drawdown ~half, protects in dying assets, but underperforms hold in bull
      markets — insurance, not alpha.
- [x] **R4 — update `FINDINGS.md`.** DONE. Stage 2 section appended: redesign is
      a risk-reducer not an alpha source — cuts drawdown ~half, protects in
      crashes, but loses to buy-and-hold in bull markets (2/5 folds typical).
      Standout: BTC momentum+regime (+130% vs hold +151% at half the drawdown).
      Flags 3 operator decisions (risk-adjusted positioning, fix the breaker,
      go to search engine?) + the breaker bug. STOPPED for review.

---

## Stage 3 — Risk-adjusted entry (operator-approved 2026-06-03)

Operator chose: **the risk-adjusted story is our entry** (lower drawdown over raw
return). Make the risk layer trustworthy, then build risk-adjusted exposure and
re-test honestly. The multi-agent **strategy-search engine is HELD** for a
separate explicit go-ahead (big/expensive). Same discipline per task.

- [ ] **S1 — Fix drawdown-breaker lockout.** The engine maintains a *campaign
      peak* that resets when the book goes flat, so the breaker measures drawdown
      since the last flat instead of an unreachable all-time peak. Risk `adjust`
      contract unchanged; fix is in how the engine feeds `peak_equity`. Engine
      re-entry test proving the strategy is no longer locked out.
- [ ] **S2 — Volatility-targeted sizing.** Composable
      `VolatilityTargeted(base, target_vol, lookback, max_weight)` wrapper that
      scales a base strategy's weight inversely to recent realized volatility —
      lean in when calm, shrink when wild. Long-only, capped. Tests.
- [ ] **S3 — Re-evaluate risk-on.** `scripts/run_riskadjusted.py`: the
      momentum+regime thread ± vol-targeting, risk-on with the fixed breaker,
      across the token set, full-window + walk-forward vs buy-and-hold. Focus the
      scorecard on risk-adjusted (Calmar, Sharpe, drawdown). Reports + summary.
- [ ] **S4 — Update `FINDINGS.md`.** Does the risk-adjusted entry hold up on
      unseen folds — better drawdown/Calmar than buy-and-hold, consistently? Then
      STOP for operator review (and the search-engine decision).

---

## Out of scope this milestone
- Live trading / Trust Wallet execution layer (later, gated on review).
- CMC paid tier (free tier covers live quotes; ccxt covers history).
- Perps / leverage (TWAK is spot-only; live perps play to our slowness).
- GitHub remote (local-only until Markus reviews the morning output).
