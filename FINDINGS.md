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
