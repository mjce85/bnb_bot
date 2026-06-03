# FINDINGS — overnight baseline run (T1–T8)

**Bottom line up front: the two baseline strategies have no edge. They lose
money badly, in every token, in both the in-sample and the out-of-sample
window — and they lose even when the market went *up*. This is a clean
negative result. The engine works; the naive strategies don't.**

Window tested: **1 Jun 2024 → 1 Jun 2026**, hourly candles, 4 tokens
(BNB, CAKE, ETH, BTC). Split 70% in-sample (the head) / 30% out-of-sample
(the most recent tail). Costs charged on every trade: 0.25% swap fee +
10 bps slippage + $0.30 gas. Strategies run "risk-off" (allowed to go fully
invested) so we measure the *signal* itself, not the risk caps.

Full numbers: `reports/baseline_summary.md` and the per-token reports in
`reports/` (regenerate with `./venv/bin/python scripts/run_baseline.py`).

---

## 1. Is there any edge after fees? No — and it's not close.

The cleanest way to see it: compare each strategy's return to simply **buying
and holding** the same token over the same window.

| Token | Window | Buy & hold | Momentum | Mean-reversion |
| --- | --- | ---: | ---: | ---: |
| BNB | in-sample | **+86.7%** | −54.6% | −91.4% |
| BNB | out-of-sample | −35.6% | −61.9% | −71.1% |
| BTC | in-sample | **+64.1%** | −63.6% | −89.2% |
| BTC | out-of-sample | −33.5% | −68.5% | −72.8% |
| ETH | in-sample | +4.5% | −67.9% | −94.0% |
| ETH | out-of-sample | −48.8% | −63.1% | −75.9% |
| CAKE | in-sample | −3.7% | **+75.1%** | −98.9% |
| CAKE | out-of-sample | −43.8% | −55.0% | −74.2% |

Read the in-sample BNB and BTC rows again: the market rose **+87%** and
**+64%**, and momentum still *lost more than half the account*. A strategy
that loses money in a bull market isn't underperforming — it's actively
destroying value. The cause is over-trading: momentum fired **~600 trades**
and mean-reversion **~1000 trades** per in-sample window. At ~0.35% all-in
cost per fill, hundreds of round-trips grind the account down regardless of
direction. Mean-reversion is worse because it "buys the dip" into tokens that
keep dipping (catching falling knives) while churning fees the whole way.

There is exactly **one** green cell in the whole grid — CAKE momentum
in-sample, +75%. Hold that thought for section 2.

## 2. Where did out-of-sample diverge? The one winner was a mirage.

CAKE momentum made **+75% in-sample** and then **−55% out-of-sample**. That's
the textbook overfit signature: a single token/period combination looked
brilliant, and the moment we showed it unseen data the "edge" inverted into a
large loss. It wasn't skill, it was one lucky regime. Every other
strategy/token was negative in both windows, so there's no in→out divergence
to chase there — they were just consistently bad.

Worth noting the out-of-sample window (roughly the last 7 months) was a broad
**downturn** — buy-and-hold was −33% to −49% across all four tokens. A
long-only strategy is swimming upstream there. But that doesn't rescue the
result: in most OOS cases the strategies lost *more* than simply holding
(e.g. BNB momentum −62% vs hold −36%), so they added harm on top of the
market, they didn't dodge it.

## 3. The risk-adjusted picture: ugly across the board.

- **Sharpe / Sortino** (higher is better; >1 is decent): negative in 15 of 16
  runs. The only positive was CAKE momentum in-sample (Sharpe 0.90) — the same
  mirage from section 2, and still below the "1.0 = interesting" bar.
- **Max drawdown** (how deep the account fell from its peak): **45% to 99%**.
  Mean-reversion routinely drew down **>90%** — effectively a blown account.
  Momentum's drawdowns were 45–75%. Either way, far past the 20% halt line our
  risk module is built to enforce.
- **Win rate**: 9–25% of trades were profitable. The strategies are wrong far
  more often than right, and the rare wins don't pay for the frequent small
  losses plus fees.

## 4. Recommendation: the *premise as tested* is dead. One thread is worth pulling.

"We can find liquid-token alpha fast with textbook hourly signals" — **that
specific premise does not hold.** Don't invest more time tuning EMA periods or
z-score thresholds on hourly bars; that's polishing a strategy whose core
problem (it trades too much and pays fees to lose) tuning won't fix.

What the diagnosis *does* point at, if you want to keep going:

- **Trade far less often.** Fees are the dominant killer here. The single
  highest-leverage change is cutting trade frequency by ~10× — daily bars
  instead of hourly, and/or a hard "don't re-enter for N bars" rule. This is a
  structural fix, not a parameter tweak.
- **Use the risk layer we already built.** This run was risk-off. The
  drawdown breaker, position cap, and stop-loss (all tested in `risk.py`) were
  deliberately *not* applied. They won't manufacture edge, but they would have
  capped the 90%+ drawdowns — relevant because the hackathon judges drawdown
  and rule-adherence directly, not just raw return.
- **Add a trend filter to mean-reversion**, or drop it. Buying dips in a
  downtrend is what produced the −90%+ results. Mean-reversion only makes sense
  in range-bound regimes; it needs a "don't catch knives" gate or it shouldn't
  ship.

My honest recommendation: **before building more strategy, decide with fresh
eyes whether hourly long-only spot is the right arena at all.** The combination
of high fees, long-only (can't profit in the OOS downturn), and fast signals is
structurally stacked against us. Lower frequency + the existing risk discipline
is the one thread I'd pull; everything else is rearranging deck chairs.

## 5. Caveats — why these numbers are softer than they look (in both directions)

- **Cost model is an assumption, and possibly the wrong venue's.** We charge
  PancakeSwap-style costs (0.25% swap, 10 bps slippage, $0.30 gas) but the
  *price data* is Binance spot. Real BSC/PancakeSwap execution would have
  different (likely higher, size-dependent) slippage. Slippage here is a flat
  10 bps regardless of trade size — generous for big orders, harsh for tiny
  ones. The losses are so large that plausible cost changes don't flip the
  conclusion, but the exact figures shouldn't be quoted as precise.
- **One split, not a full walk-forward.** We tested a single 70/30 cut, not a
  rolling walk-forward across many windows. The negative result is consistent
  enough that more splits would very likely agree, but we haven't *proven* that.
- **Out-of-sample = one specific (bearish) regime.** The 30% tail happened to
  be a broad downturn. A different holdout period might treat long-only less
  harshly. This cuts the strategies *some* slack on OOS — but not in-sample,
  where they failed in a rising market with no such excuse.
- **Independent OOS warmup.** The out-of-sample run starts flat and re-warms
  its own indicators (no peeking at in-sample state). The first ~24 bars of the
  OOS window are therefore inactive — a small, honest reduction in OOS activity.
- **No look-ahead, costs always charged.** On the trustworthy side: the engine
  is tested to use only past data for each decision and to fill at the next
  bar's open, and there is no fee-free path through it. The numbers are grim,
  but they are honestly grim — not a backtest bug making good strategies look
  bad.

---

🛑 **Stopping at the gate (T9).** Per PLAN.md I am not sharpening alpha,
sweeping parameters, or adding strategies. The direction call — pull the
lower-frequency thread, change arenas, or shelve it — is yours, Markus.

---
---

# FINDINGS — Stage 2: robust redesign (R1–R4, 2026-06-03)

You picked the **robust redesign** thread. Here's what it changed.

**Bottom line: the redesign worked as far as it could — it stopped the bleeding
and turned the strategies into a genuine *risk reducer*. But it did not produce
*alpha*. None of the three strategies reliably beats simply holding the token.
What they reliably do is cut drawdown (often roughly in half) and protect you in
assets that collapse. That's insurance, not an edge. And along the way I found a
real bug in our own risk module that has to be fixed before the risk layer is
usable.**

What changed from the probe: **daily** bars instead of hourly (≈24× fewer
trades — the fee bleed is gone), a **trend/regime filter** so strategies sit in
**cash** during downtrends instead of fighting them, a longer **2021→2026**
history spanning a full bull/bear/recovery cycle, **walk-forward** scoring across
5 unseen windows, and **buy-and-hold as the benchmark** on every run.

Full numbers: `reports/robust_summary.md`. Headline numbers below are **risk-off**
(see the bug section for why).

## 1. Does anything beat buy-and-hold now? Mostly no — but the drawdowns got much better.

Best strategy per token (risk-off, full 2021–2026 window):

| Token | Buy & hold | Best strategy | Strat return | Drawdown: strat vs hold | Folds beaten |
| --- | ---: | --- | ---: | --- | ---: |
| BNB | **+1781%** | momentum+regime | +133% | 61% vs 71% | 3/5 |
| BTC | +151% | momentum+regime | **+130%** | **37% vs 77%** | 2/5 |
| ETH | +175% | meanrev+regime | +17% | 45% vs 79% | 2/5 |
| CAKE | −92% | meanrev+regime | **−25%** | 45% vs 98% | 5/5 |

Read it honestly:

- **In bull markets, holding wins by a mile.** BNB rose +1781%; our best did
  +133%. The strategies sit out the biggest up-legs (they're in cash on every
  pullback), so they capture a fraction of a strong rise. No way around it for a
  trend/regime approach.
- **But drawdowns dropped a lot.** Almost every strategy cut max drawdown
  versus holding — frequently to about half. **BTC momentum+regime is the
  standout: +130% return (vs hold's +151%) at 37% drawdown (vs hold's 77%)** —
  nearly the same money for half the pain. That's a real risk-adjusted
  improvement on one asset.
- **In a dying asset, the regime filter clearly earns its keep.** CAKE fell
  −92%; sitting in cash during its decline cut the loss to −25% to −70%, and beat
  hold in **5 of 5** walk-forward windows. Capital preservation works.

## 2. Walk-forward tells the real story: this is a hedge, not an edge.

Most strategies beat buy-and-hold in only **2 of 5** windows — and it's always
the *same* 2: the down-market folds. They lose the up-market folds. In plain
terms, these strategies are essentially a **bet against the asset / a volatility
hedge**: they win when things fall and lag when things rise. That's a coherent,
useful behaviour — but it is not a stable source of outperformance, and a judge
looking at raw returns in a crypto bull market would not be impressed.

## 3. Risk-adjusted picture: improved, and that's the whole point of the redesign.

Drawdowns are dramatically better than the probe (no more 90%+ wipeouts from
churn) and usually better than buy-and-hold. Sharpe ratios are still mostly
around zero — these aren't efficient compounders — but the *shape* is what our
stated differentiator cares about: smaller holes, faster recovery, capital
protected in crashes. If our pitch is "disciplined risk control, not raw
return," **BTC momentum+regime is the kind of result that pitch is made of.**

## 4. I found a bug in our risk module — flagging, not fixing.

I planned to run this risk-on (stop-loss + drawdown breaker active). When I did,
every strategy collapsed to **~2% time in market and ~3 trades over five years**.
That's not the strategy — it's a flaw in our **drawdown breaker**:

> The breaker halts new entries while equity is ≥20% below its peak. But once a
> strategy is forced into cash during a drawdown, its cash balance is frozen and
> can never climb back to the old peak — so the breaker stays tripped *forever*.
> One early rough patch disables the strategy permanently.

Trend strategies are hit hardest because they're in cash exactly during the
downturns that cause drawdowns. The fix is a small **risk-semantics decision**:
the breaker's "peak" should reset (e.g. when the book goes flat, or after a
recovery/cooldown). I did **not** patch it autonomously because how aggressive
the breaker should be is a judgment call about how the product behaves — your
call. The headline numbers above are risk-off, so they're unaffected; the
`RiskOn Exp` columns in the summary show the collapse as evidence.

## 5. Recommendation + the decisions I need from you.

The robust redesign answered its question: **there is no easy long-only alpha
here, but there is a defensible risk-control story** — especially BTC
momentum+regime (near-hold return, half the drawdown) and capital preservation
in crashes. Whether that's a *winning hackathon entry* depends on how the judges
weigh "lower return, much lower risk" against raw return, and that's a
positioning call, not an engineering one.

Three decisions before I do more:

1. **Is the risk-adjusted story our entry?** If yes, the next build is
   volatility-aware sizing + leaning into the momentum+regime thread, and the
   pitch becomes "we don't chase the top, we don't eat the crash." If raw return
   is what we think wins, this whole approach is the wrong tool.
2. **Fix the drawdown breaker?** Quick to do once you tell me the semantics you
   want (reset-when-flat is my default suggestion). Needed before any risk-on
   result is trustworthy.
3. **Go to the strategy-search engine now?** We now have the walk-forward +
   benchmark spine that makes a search safe from overfitting. This is the
   bigger, multi-agent effort — worth it only if direction (1) says keep going.

## 6. Caveats (same honesty bar as before).

- **Costs are still assumptions on the wrong venue** (PancakeSwap-style fees on
  Binance price data) — see Stage 1 caveats; unchanged.
- **Walk-forward here is evaluation, not optimization.** Parameters are fixed
  (SMA-100, default momentum/mean-reversion); each fold is scored independently.
  We have *not* yet re-fit per fold — that's the search engine's job, and it's
  where overfitting risk reappears and must be guarded.
- **One config per strategy.** The BTC momentum+regime result is one asset, one
  parameter set. It's promising, not proven — treat it as a thread to pull, not
  a finding to bank.
- **Survivorship/regime luck.** 2021–2026 is one historical path. CAKE's −92%
  flatters the "protection" story; a different five years could look different.
- **Still trustworthy where it counts:** no look-ahead, costs on every fill,
  fresh strategy per fold so no state bleed. The numbers are honest.

---

🛑 **Stopping for review (R4).** Stage 2 is complete. I'm not fixing the breaker,
tuning the risk-adjusted thread, or starting the search engine until you weigh in
on the three decisions above — those are yours, Markus.

---
---

# FINDINGS — Stage 3: the risk-adjusted entry (S1–S4, 2026-06-03)

You said go for the risk-adjusted story. I fixed the risk module, built
volatility targeting, and re-tested. **It works — and unlike everything before
it, it holds up across every unseen window.**

**Bottom line: the risk-adjusted redesign delivers exactly what it promised. It
cuts drawdown by roughly half, consistently — in 5 of 5 walk-forward windows on
all four tokens, every variant. On BTC it actually beats buy-and-hold on every
risk-adjusted measure (more return-per-unit-risk at less than half the
drawdown), and on CAKE it turned a −92% wipeout into a small *profit*. It does
not beat buy-and-hold on raw return in steady bull markets — nothing long-only
will — but as a disciplined risk-control product, this is a real, defensible
hackathon entry.**

Three things changed since Stage 2: (1) the **drawdown-breaker bug is fixed**
(it no longer locks the strategy out); (2) **volatility targeting** now scales
exposure down when markets are wild; (3) everything ran **risk-on** and was
scored on the risk-adjusted scorecard — drawdown, Sharpe, and Calmar (return
earned per unit of drawdown — higher is better).

Full numbers: `reports/risk_adjusted_summary.md`.

## 1. The headline strategy: volatility-targeted regime momentum.

| Token | Buy & hold (ret / maxDD / Calmar) | Our strategy (ret / maxDD / Calmar) | DD beaten |
| --- | --- | --- | --- |
| **BTC** | +151% / 77% / 0.24 | **+110% / 31% / 0.48** | 5/5 |
| BNB | +1781% / 71% / 1.02 | +184% / 45% / 0.48 | 5/5 |
| ETH | +175% / 79% / 0.26 | +2% / 53% / 0.01 | 5/5 |
| CAKE | −92% / 98% / −0.40 | **+10% / 50% / +0.04** | 5/5 |

(On BTC the *non*-vol-targeted version is even better on Calmar — +139% at 34%
drawdown, Calmar 0.51, Sharpe 0.67 vs hold's 0.58. Both beat holding.)

What this says:

- **Drawdown control is rock-solid.** Every strategy, every token, beat
  buy-and-hold's drawdown in **all 5** walk-forward windows. This is the most
  consistent result in the whole project — the thing we set out to prove.
- **BTC is a genuine win.** Near-hold return at less than half the drawdown, and
  higher Sharpe *and* Calmar than holding. That's not insurance — that's a
  better risk-adjusted bet than the benchmark, out of sample.
- **CAKE is the capital-preservation showcase.** Holding lost 92%; we made a
  small profit by scaling out of the decline. In a portfolio, that's the
  difference between a survivable year and a ruinous one.
- **Volatility targeting earned its place.** It improved *both* drawdown and
  return versus the plain version almost everywhere (BNB +133%→+184%,
  CAKE −42%→+10%, ETH −19%→+2%) — calmer ride, usually more money.

## 2. Where it honestly doesn't win.

In **steady bull markets (BNB, ETH)**, buy-and-hold's own risk-adjusted numbers
are excellent (BNB Calmar 1.02), and we don't beat them — we sit out pullbacks
and miss too much of a strong, sustained rise. On raw return we trail badly
there (BNB +184% vs +1781%). A judge who weighs bull-market returns above all
else will not be wowed. Our pitch has to be the risk-adjusted / discipline angle
— which is the one we chose, and the one the data supports.

Also: vol-targeting trades a **lot** more (≈500 trades vs ≈90 for the plain
version) because it nudges exposure every bar. It still came out ahead after
fees, but a **rebalance band** (already supported by the engine, just not turned
on here) would cut that fee drag — an easy refinement.

## 3. Risk module: the bug is fixed, with one honest limitation.

The drawdown breaker no longer locks the strategy out (Stage 2's 2%-exposure
collapse is gone — it's back to ~40-50% time in market). The fix measures
drawdown since the book was last flat. The trade-off: it catches drawdown
*within a held position* but not slow bleed across many small trades — that job
is now done by volatility targeting, which is the better tool for it anyway. If
you later want a hard "stop everything after a bad month" breaker, that's a
separate cooldown-style rule and a quick add.

## 4. Recommendation + what's next.

**We have a defensible entry.** Volatility-targeted regime momentum is honest,
robust out-of-sample, cuts drawdown in half everywhere, beats holding on BTC,
and preserves capital in crashes. For a hackathon judged on drawdown and
risk-adjusted performance with rule-adherence, that's a coherent, true story
backed by walk-forward evidence — not an overfit mirage.

Now the fork I held earlier is live, and this is the moment for it:

1. **Strategy-search engine (the big push).** We now have the safe scaffolding —
   walk-forward, benchmark, risk-adjusted scorecard — to search parameters
   (target_vol, trend window, vol lookback, rebalance band) and select on
   *out-of-sample Calmar/drawdown*, robust across tokens rather than fit to one.
   This is the multi-agent effort I flagged; it needs your explicit go-ahead
   (it's token-expensive). Worth it now that the thread has proven out.
2. **Or lock the entry and package it.** Freeze
   `mom_regime_voltgt` (+ a rebalance band), then build the Track-2 "strategy
   skill" wrapper, demo, and judge-facing write-up. Lower risk, ships sooner.

My honest lean: **a short, bounded search** to firm up the parameters and prove
the result isn't sensitive to my hand-picked numbers (target_vol=0.025,
SMA-100), **then package.** A sprawling search risks re-introducing overfitting,
which is the one thing our whole pitch is built against.

## 5. Caveats (unchanged honesty bar).

- **Costs are assumptions on the wrong venue** (PancakeSwap fees on Binance
  prices) — unchanged from earlier stages.
- **Hand-picked parameters.** target_vol, the SMA window, and the vol lookback
  were chosen by judgment, not searched. The result is robust across 4 tokens
  and 5 folds, which is reassuring, but a parameter search (decision 1) is what
  would actually prove it's not luck.
- **One historical path.** 2021–2026 is a single sequence of regimes; CAKE's
  collapse flatters the protection story. Promising, not guaranteed.
- **Trustworthy where it counts:** no look-ahead, costs on every fill, fresh
  strategy per fold, drawdown beaten out-of-sample in 5/5 windows. Honest.

---

🛑 **Stopping for review (S4).** Stage 3 is complete — the risk-adjusted entry is
built and validated. I'm holding on the strategy-search engine (token-expensive,
needs your explicit go-ahead) and on packaging until you pick the path in
section 4. Your call, Markus.

---
---

# FINDINGS — Stage 4: bounded search + packaged entry (P1–P4, 2026-06-03)

You picked the bounded search → package path. Done. **The entry is locked,
holdout-validated, and packaged for submission.**

## 1. The search was disciplined on purpose.

120 parameter configs (volatility target × trend window × vol lookback ×
rebalance band). Two guards against fooling ourselves:

- **Untouched holdout.** Each token's most recent 25% was held out. The search
  ranked configs on the first 75% only.
- **One config across all four tokens** — not the best per coin (that's
  curve-fitting). Picked the single set that's best *on average*, among those
  that beat buy-and-hold drawdown on every token.

The winner sits on a **stable plateau** (the top-8 configs cluster together), not
a lone lucky spike — exactly what you want to see.

## 2. The locked entry.

`VOL_TARGETED_REGIME_MOMENTUM` (frozen in `bnb_bot/presets.py`): volatility
target 0.015/day, 50-day trend filter, 30-day volatility lookback, 3% rebalance
band, risk-on (10% stop-loss, 20% drawdown breaker).

Full-window result (drawdown is the headline):

| Token | Strategy ret / maxDD | Buy & hold ret / maxDD |
| --- | --- | --- |
| BNB | +191% / **22%** | +1781% / 71% |
| BTC | +71% / **37%** | +151% / 77% |
| ETH | +35% / **36%** | +175% / 79% |
| CAKE | **+20%** / 36% | −92% / 98% |

Drawdown roughly a third to a half of buy-and-hold, positive on every token —
including CAKE, which holding would have nearly wiped out.

## 3. The honesty test it passed.

On the **untouched holdout** (data the search never saw), the entry beat
buy-and-hold's **drawdown on 4/4 tokens** and its **return on 3/4**. On BNB:
**+48% vs +2%, Sharpe 1.33 vs 0.29, Calmar 1.89 vs 0.02.** That's the result
that matters most — it wasn't fit to that data, and it held up. (The one return
miss was CAKE, which chopped sideways in the holdout; we still cut its drawdown
by two-thirds.)

## 4. What's packaged.

- **`bnb_bot/presets.py`** — the frozen entry, pinned by tests so it can't drift.
- **`scripts/run_entry.py`** — one command reproduces the headline
  (`reports/entry_summary.md`).
- **`scripts/search_params.py`** — re-runs the validated search.
- **`README.md`** — judge-facing: the pitch, the three honesty guards, the
  results, repro steps, and honest limits.
- **83 tests green; `black` clean.**

## 5. Where things stand — and what's left for you.

The Track-2 entry is **submission-ready as a backtest+report**: a disciplined,
honestly-validated risk-control strategy with a coherent story (we don't chase
the top, we don't eat the crash) backed by out-of-sample evidence.

Still genuinely yours to decide (all held, none started):

1. **The multi-agent strategy-search engine** — only worth it if you want to push
   the result further; it's the token-expensive option and needs an explicit go.
2. **The live execution layer** (Trust Wallet / BNB Chain) — out of scope this
   milestone by design, gated on your review.
3. **Submission polish** — a demo video / slide, or wiring the CMC live-quote
   path, if the hackathon format wants more than a repo.

My recommendation: **review the README and `reports/entry_summary.md`, and if
you're happy, this is a legitimate entry to submit.** Anything beyond that is
upside, not necessity.

---

🛑 **Stopping for review (P4).** Stage 4 complete — searched, locked, packaged,
all green. Nothing further runs without your go-ahead. Over to you, Markus.

---
---

# FINDINGS — Stage 5: portfolio backtest (PF1–PF2, 2026-06-03)

You asked for the biggest non-overfitting improvement: trade the locked entry as
a real **portfolio** across all four tokens, not one coin at a time. Built it —
and it produced both a strong result and an honest surprise.

## 1. Traded as a portfolio, it clearly beats holding.

| | Return | MaxDD | Sharpe | Calmar |
| --- | ---: | ---: | ---: | ---: |
| **Portfolio strategy** | **+99%** | 55% | 0.53 | 0.25 |
| Equal-weight buy & hold | +8% | 80% | 0.37 | 0.02 |

It wins on **every axis** vs the natural benchmark (an equal-weight hold of the
same four tokens), and beats hold's drawdown in **5 of 5 walk-forward folds**.
This is the "what you'd actually run" result — one shared book, the
total-exposure cap finally doing real work. See `docs/portfolio.png` and
`reports/portfolio_summary.md`.

## 2. The honest surprise: diversification did *not* lower drawdown.

I expected combining four sleeves to smooth the curve. It didn't: the portfolio's
drawdown (**55%**) is *higher* than the average single-token run (**33%**). Two
real reasons, neither flattering:

- **These tokens are correlated.** BNB/BTC/ETH (and CAKE in crashes) fall
  together, so holding all four diversifies far less than holding genuinely
  independent bets would.
- **The portfolio deploys idle cash.** A single-token run often sits ~60% in cash
  (vol targeting + regime gate). The portfolio puts that cash into the *other*
  tokens, so it runs more fully invested — which is exactly why its return is so
  much higher than holding, but also why it carries more drawdown.

So the portfolio's edge is **capital efficiency vs holding**, not a free-lunch
drawdown reduction. I corrected the write-up to say so rather than spin it. (The
engine *does* capture real diversification when assets are decorrelated — there's
a unit test proving it on anti-correlated synthetic series; this token set just
isn't decorrelated.)

## 3. Engineering notes.

- New `bnb_bot/portfolio.py`: shared-book multi-asset engine, per-symbol risk +
  a portfolio total-exposure cap, common-timeline alignment, sells-before-buys.
- Fill economics (`execute_delta`) were **extracted and shared** with the
  single-asset engine, with a test asserting a one-symbol portfolio reproduces
  the single engine bar-for-bar — so they can never silently diverge.
- 89 tests green; `black` clean.

## 4. Takeaway.

The submission now has two honest framings, both backed by the same trusted
engine: the **single-token entry** (tightest drawdown control, 22–37%) and the
**portfolio** (best return-vs-hold story, +99% vs +8%, runs hotter at 55% DD).
Either is a legitimate, defensible Track-2 entry. Nothing here required parameter
tuning, so no new overfitting risk was introduced.

---

🛑 **Stopping for review (Stage 5).** The portfolio improvement is done and
reported honestly, including where my hypothesis was wrong. Still held for your
explicit go-ahead: the multi-agent search engine, the live execution layer, and
any demo polish. Over to you, Markus.

---
---

# FINDINGS — Stage 6: robustness hardening (RB1–RB3, 2026-06-03)

Stress-tested the frozen entry against our two weakest caveats — no tuning. One
result is reassuringly strong; the other found a real weakness we needed to know.
`reports/robustness_summary.md`.

## 1. Out-of-universe: the entry generalizes (strong).

Ran the *frozen* config on **8 liquid tokens it was never searched on** (XRP,
ADA, DOGE, LINK, DOT, LTC, TRX, AVAX). It beat buy-and-hold's drawdown on
**8/8** — drawdowns of 29–61% vs holding's 69–98%. Highlights: DOT −19% vs
hold −86%; ADA +65% vs +34% at a third of the drawdown. The parameters were
chosen on BNB/CAKE/ETH/BTC only, so holding the drawdown edge on completely
unseen coins is the strongest evidence yet that the result isn't curve-fit.

## 2. Cost sensitivity: the return edge is fragile (real weakness).

| Costs | Strategy return | Strategy maxDD | Buy & hold return |
| ---: | ---: | ---: | ---: |
| 1× | +99% | 55% | +8% |
| 2× | **+1%** | 64% | +8% |
| 3× | **−47%** | 73% | +8% |

The portfolio strategy trades ~500 times; buy-and-hold trades once. So doubling
costs erases almost the entire return advantage and tripling turns it negative,
while holding is unaffected. **Crucially, the drawdown control survives at every
cost level** (still well below holding's 80% even at 3×) — it's the *return* edge
that's cost-fragile, not the risk story.

This matters because we charge PancakeSwap-style fees on Binance prices, and real
on-chain BSC slippage (especially at size) could plausibly be 2–3× our
assumption. Honest conclusion: **lead with the drawdown / capital-preservation
result (robust to costs); treat the headline return as best-case-cost and always
quote it with this caveat.**

The fix, if we pursue it, is *lower turnover* — a wider rebalance band or a
slower vol-targeting update. I did **not** apply it here: re-tuning a parameter to
rescue the return number is exactly the overfitting reflex our pitch rejects.
Flagged as a deliberate next step for your call, not a silent patch.

## 3. Takeaway.

Net, the entry came out of stress-testing *more* trustworthy, not less: it
generalizes to unseen tokens, and its core claim (drawdown control) holds even at
3× costs. The honest scar is that the eye-catching returns assume our cost model
is right. Both are now documented in the README and SUBMISSION so no number is
quoted without its caveat.

---

🛑 **Pausing here (Stage 6).** Robustness done and reported straight. The open,
operator-gated calls remain: lower-turnover variant (cheap, would harden returns
to cost), the multi-agent search engine, the live execution layer, GitHub + CI.
Say the word on any.

---
---

# FINDINGS — Stage 7: cost-robust re-lock (2026-06-03)

Stage 6 found the entry's returns were cost-fragile (it traded ~500×). Rather than
hand-pick a fix, I re-ran the disciplined search with that weakness in the
objective, and re-locked the entry to the validated winner.

## What changed.

`scripts/search_cost_robust.py`: same guards as the original search (train-only
ranking, one config across all tokens, drawdown gate, untouched holdout) plus two
changes that *target* cost-robustness without peeking — wider rebalance bands in
the grid, and **ranking under a conservative 2× cost assumption** so high-turnover
configs are penalized by the objective itself. 300 configs.

Winner, holdout-validated (drawdown beaten **4/4**, BNB Sharpe 1.26, ETH +39% vs
−38%): same `target_vol=0.015` and `trend_period=50`, but **`vol_lookback`
15** and **`rebalance_band` 0.15** (was 30 / 0.03). The wider band roughly
quarters turnover. The locked preset in `bnb_bot/presets.py` was updated to this
config; tests re-pin it.

## The payoff — the Stage 6 weakness is largely fixed, returns even improved.

Portfolio at escalating costs (was → now):

| Costs | Old return | New return |
| ---: | ---: | ---: |
| 1× | +99% | +85% |
| 2× | +1% | **+15%** |
| 3× | −47% | **−18%** |

It now **stays positive at 2× costs** and roughly halves the 3× loss, while
drawdown control is unchanged. And lower turnover *helped at 1× too* — the
single-token entry returns rose (BNB +191%→**+279%** at 23% drawdown, Calmar
**1.22 vs holding's 1.02**; ETH +35%→+77%; CAKE +20%→+34%). Out-of-universe
generalization still holds: drawdown beaten on **8/8** unseen tokens.

So lowering turnover was a near-free win: more cost-robust, higher return, same
risk control. (It's not literally free — the trade-off is the strategy reacts a
bit more slowly; the holdout confirms that didn't hurt out of sample.)

## Honesty note on method.

This re-tune is *not* the overfitting reflex I warned against in Stage 6. The
difference: I didn't pick `band=0.15` because it maximized full-data return; the
disciplined search picked it under a conservative cost objective, and it was
validated once on the untouched holdout. The original (band 0.03) search remains
recorded in `reports/search_summary.md`; the cost-robust one is in
`reports/search_cost_robust_summary.md`.

All regenerated artifacts (entry, portfolio, robustness summaries; both figures)
and the README/SUBMISSION numbers reflect the re-locked entry. 89 tests green.

---

🛑 **Pausing (Stage 7).** The entry is re-locked, cost-hardened, and all docs/
artifacts are consistent. Open operator-gated calls unchanged: multi-agent search
engine, live execution layer, GitHub + CI. Your move, Markus.
