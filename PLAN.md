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

- [x] **S1 — Fix drawdown-breaker lockout.** DONE. Engine resets `peak_equity`
      to current equity while flat (campaign peak), so the breaker measures
      drawdown since the last flat — no permanent lockout (BNB risk-on exposure
      2%→50.7%). Documented on the RiskManager contract; engine re-entry test.
      Caveat surfaced: reset-when-flat misses cumulative whipsaw bleed (vol
      targeting handles that).
- [x] **S2 — Volatility-targeted sizing.** DONE. `VolatilityTargeted(base,
      target_vol, lookback, max_weight)` scales the base weight by
      `target_vol / realized_vol` (capped) — lean in when calm, shrink when
      wild. Composable, long-only, no-lookahead. 6 tests incl. hand-computed
      scale-down.
- [x] **S3 — Re-evaluate risk-on.** DONE. `scripts/run_riskadjusted.py`. Result:
      vol-targeted regime momentum cuts drawdown in **5/5 folds on all 4 tokens**;
      on BTC it beats buy-and-hold on Sharpe (0.67 vs 0.58) AND Calmar (0.51 vs
      0.24) at <half the drawdown; vol-targeting improved both drawdown and
      return vs plain. Hold still wins risk-adjusted on the steady bulls
      (BNB/ETH). `reports/risk_adjusted_summary.md`.
- [x] **S4 — Update `FINDINGS.md`.** DONE. Stage 3 section: the risk-adjusted
      entry holds up — drawdown beaten 5/5 folds on all tokens; BTC beats hold on
      Sharpe+Calmar; CAKE turned −92% into +10%. Defensible entry. Flags the
      live fork: short bounded search then package vs lock-and-package. STOPPED
      for operator review.

---

## Stage 4 — Bounded search + package (operator-approved 2026-06-03)

Operator chose: short, walk-forward-validated parameter search, **then package**
the entry. Two hard anti-overfit guards: (1) an untouched 25% holdout the search
never sees, validated once; (2) one config selected across ALL tokens, never
per-token. The multi-agent search engine stays parked. Same discipline per task.

- [x] **P1 — Bounded parameter search.** DONE. 120 configs, train-only ranking,
      single config across tokens. Winner: target_vol=0.015, trend_period=50,
      vol_lookback=30, rebalance_band=0.03 — on a stable plateau, not a spike.
      **Holdout PASS**: drawdown beaten 4/4 tokens, return beats hold 3/4
      (BNB +48% vs +2%, BNB Sharpe 1.33 vs 0.29). `reports/search_summary.md`.
      Go confirmed → packaging.
- [x] **P2 — Lock the winning config.** DONE. `bnb_bot/presets.py` freezes the
      search winner as `VOL_TARGETED_REGIME_MOMENTUM` (strategy + rebalance band
      + risk limits). `scripts/run_entry.py` reproduces the headline in one
      command → `reports/entry_summary.md` (full-window drawdowns 22–37% vs hold
      71–98%, positive return on all 4 tokens). 5 tests pin the preset.
- [x] **P3 — Judge-facing `README.md`.** DONE. Replaced the scaffold README with
      a submission front-door: the pitch, the strategy in plain terms, the three
      backtest-honesty guards, headline + holdout results, one-command repro, repo
      map, and honest limitations.
- [x] **P4 — Final sweep + `FINDINGS.md` update.** DONE. `black` clean (27
      files), 83 tests green, no stale refs. FINDINGS Stage 4 records the search
      discipline, the locked entry, the holdout pass, and what's packaged. Entry
      is submission-ready as backtest+report. STOPPED for operator review.
- [x] **P5 — Submission polish.** DONE. `scripts/make_figures.py` →
      committed `docs/headline.png` (equity + underwater drawdown, strategy vs
      hold, per token); devpost-style `SUBMISSION.md` pitch; figure wired into
      README. Visual + narrative submission assets ready.

---

## Stage 5 — Multi-asset portfolio (operator-approved 2026-06-03)

Operator asked for the biggest non-overfitting upside: trade the locked entry as
a real portfolio (the per-symbol/total-exposure risk caps finally do something).

- [x] **PF1 — Portfolio engine.** DONE. `bnb_bot/portfolio.py`:
      `run_portfolio_backtest` (shared cash, per-symbol risk + portfolio
      total-exposure cap, sells-before-buys, common-timeline alignment) +
      `buy_and_hold_portfolio` (analytic equal-weight). Shared fill math
      (`execute_delta`) extracted from the single engine so they can't drift.
      6 tests incl. a single-symbol-portfolio == single-engine equivalence anchor.
- [x] **PF2 — Portfolio run + honest finding.** DONE. `scripts/run_portfolio.py`
      + `reports/portfolio_summary.md` + `docs/portfolio.png`. Traded as a
      portfolio the entry returns **+99% vs equal-weight hold +8%** at **55% vs
      80% drawdown**, drawdown beaten **5/5 folds**. Honest correction: portfolio
      drawdown (55%) is *higher* than the single-token average (33%) — these
      tokens are correlated and the portfolio deploys idle cash; the win is
      capital efficiency vs holding, not diversification.

---

## Out of scope this milestone
- Live trading / Trust Wallet execution layer (later, gated on review).
- CMC paid tier (free tier covers live quotes; ccxt covers history).
- Perps / leverage (TWAK is spot-only; live perps play to our slowness).
- GitHub remote (local-only until Markus reviews the morning output).
