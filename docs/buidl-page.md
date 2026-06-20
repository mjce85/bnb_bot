# DoraHacks BUIDL page copy — bnb_bot

Paste-ready copy for the BNB HACK Track 2 submission. Fields below map to the
DoraHacks BUIDL form. Numbers match `README.md` / `SUBMISSION.md` and the demo
video.

---

## Project name

**bnb_bot — a backtest you can actually trust**

(If a short standalone name is needed: `bnb_bot`. The subtitle is the hook.)

## Tagline / one-liner

> A backtestable BNB-ecosystem strategy that wins on the one axis you can actually
> control — risk — and proves it on data it was never tuned on.

## Track

**Track 2 — Strategy Skills** (backtestable strategy, no live execution)

## Links

- **Repo:** https://github.com/mjce85/bnb_bot
- **Demo video:** _(paste unlisted YouTube / Drive link)_
- **Reproduce:** one command — see README / `SUBMISSION.md`

---

## Full description (paste into the description box)

## The problem

Most "winning" crypto backtests are fiction. They peek at the future, ignore
fees, or get tuned until they look good on the one slice of history the author
happened to test. In a bull market it's easy to show a big number and impossible
to know if it means anything.

`bnb_bot` is the opposite: a strategy whose backtest you can **trust**, that wins
on **risk**, and that holds up out of sample.

## What it is

An event-driven Python engine that generates and backtests strategies for liquid
BNB-ecosystem tokens. The submitted entry is **volatility-targeted, regime-gated
momentum**:

- **Momentum** rides uptrends.
- A **regime gate** sits in cash whenever price is below its long-term trend — so
  it never fights a sustained downturn.
- **Volatility targeting** sizes for constant risk: lean in when calm, scale down
  when wild.
- A **risk layer** (stop-loss + drawdown breaker) backstops the position.

## Results (daily, 2021–2026, BNB / CAKE / ETH / BTC)

- **Max drawdown 23–37% vs buy-and-hold's 71–98%** — roughly a third — while
  staying profitable on every token, including CAKE (−92% buy-and-hold).
- **Out-of-sample holdout:** drawdown beaten on **4/4** tokens, return on 3/4. On
  BNB's untouched holdout: **+46% vs +2%, Sharpe 1.26 vs 0.29**; on ETH **+39% vs −38%**.
- **It generalizes:** run *frozen* — zero retuning — on **18 liquid tokens** back
  to 2017 (through the 2018 bear), it beat buy-and-hold's drawdown on **18/18**,
  cutting drawdown roughly in half on average.
- **It beat real competition:** in a fair bake-off against Donchian breakout,
  time-series momentum, and dual-momentum rotation on the identical rig, the entry
  won the portfolio outright on return, drawdown, and Calmar; the flashy rotation
  collapsed (−63%).
- **Costs survive stress:** returns hold up at **2× our assumed costs**, drawdown
  control holds at **3×**.

## Why you can trust the numbers

The backtester is built so it structurally cannot commit the three classic
backtest lies, and each guard is enforced in code and tested (**131 tests**):

1. **No look-ahead** — a signal at bar *t* uses only data ≤ *t*; fills happen at
   the next bar's open.
2. **Costs on every fill** — swap fee + slippage + gas, always.
3. **Overfitting guarded** — a bounded parameter search with an untouched 25%
   holdout and one config chosen across all tokens.

## CoinMarketCap Agent Hub integration

This entry is built **on** the CoinMarketCap agent layer, not just next to it:

- **Pre-built Skill** — the entire strategy is packaged as a CMC Skill
  (`skills/risk-controlled-momentum/SKILL.md`) that emits a backtestable strategy
  spec on demand.
- **Live CMC data** — pulls CoinMarketCap's **Fear & Greed index + BTC dominance**
  as live market context (`scripts/live_context.py`).
- **Used honestly** — we backtested *gating* the strategy on Fear & Greed, found it
  does **not** improve risk-adjusted returns, and report that. So CMC data informs
  as context — it never acts as a hidden trigger.

→ Eligible for **Best Use of Agent Hub**: a working CMC Skill driven by live CMC
data, with the integration's honesty proven in the backtests themselves.

## What we learned

There is no easy long-only alpha in liquid crypto — we proved it to ourselves with
blunt negative results. But there *is* a durable edge in **discipline**: cutting
drawdown in half, consistently and out-of-sample, is a real, defensible product —
even when raw return trails a roaring bull market. We lead with the risk story,
not the return.

## Reproduce in one command

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python scripts/run_entry.py   # headline result
./venv/bin/python -m pytest -q           # 131 honesty/correctness tests
```

---

## Submission checklist

- [ ] BUIDL page created, Track 2 selected
- [ ] Repo link added
- [ ] Demo video uploaded (unlisted) + link pasted
- [ ] Description pasted
- [ ] No token launch / fundraise / airdrop before results (compliant by design)
- [ ] Submitted before **21 Jun 2026, 12:00 UTC**
