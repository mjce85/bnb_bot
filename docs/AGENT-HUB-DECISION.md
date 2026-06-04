# CMC Agent Hub — research + advisory (for the 2026-06-04 evening dig)

> **RESOLVED 2026-06-04 (Stage 11).** Decision made and built: wired in CMC's
> **Fear & Greed** index (free Basic tier, incl. historical for an honest
> backtest). We *tested* gating the strategy on F&G — it did **not** improve
> risk-adjusted performance (greed-cut throws away upside; the small fear-cut gain
> overlaps existing vol-targeting and the proposed alt-lag mechanism doesn't hold
> at daily resolution). So F&G ships as **live market context, not a trade
> trigger** (`scripts/live_context.py`); the locked entry is unchanged. Full
> account: FINDINGS.md Stage 11. The advisory below is preserved as written.

---

Markus asked me to research whether/how to wire the **CoinMarketCap Agent Hub**
into our Track 2 entry, so he can decide in the morning. Here's everything, ending
with a recommendation.

---

## 1. The short version

- The Agent Hub is real, well-documented, and **cheap to use** ($0.01/request via
  x402, no API key, no subscription).
- It exposes **12 tools**. Two of them line up almost exactly with our strategy's
  own logic (technical analysis: EMA/MACD/MA; and a market-wide trend tool) — so a
  CMC-backed signal path is a *natural*, honest fit, not a bolt-on.
- **It cannot power our backtest** (no deep free history), but it can power a
  **live "what would we do today" decision path** — which is exactly the
  demonstration that competes for the **"best use of CMC Data & Signal" +$2k**
  prize and matches CMC's Track 2 framing.
- **Recommendation: do it** — a bounded, ~half-day add of a live CMC signal
  adapter, keeping Binance/ccxt for the backtest. Details in §6.

## 2. The 12 Agent Hub tools (from the official MCP docs)

| # | Tool | Returns | Relevant to us? |
| --- | --- | --- | --- |
| 1 | Search Cryptocurrencies | fuzzy name/symbol/slug lookup | plumbing |
| 2 | Live Quotes | real-time price, mcap, volume, % moves | yes (live price) |
| 3 | Global Market Metrics | total mcap, 24h vol, **Fear & Greed**, **altcoin season**, **BTC/ETH dominance** | **yes (risk/regime overlay)** |
| 4 | **Crypto Technical Analysis** | **MA, EMA, MACD, RSI**, Fibonacci, support/resistance | **yes — this IS our momentum** |
| 5 | **Market Cap Technical Analysis** | the same TA applied to total-market cap | **yes — a market-wide regime gate** |
| 6 | Crypto Info | logos, descriptions, links, whitepaper | no |
| 7 | Latest News | recent per-coin news | optional sentiment |
| 8 | Concept Search | semantic search of crypto concepts/FAQs | no |
| 9 | Trending Narratives | hot sectors / narrative tokens | no (for us) |
| 10 | On-Chain Metrics | holder distribution, whale-vs-retail, fees | maybe (risk flag) |
| 11 | Derivatives Data | leverage, open interest, funding, liquidations | maybe (risk flag) |
| 12 | Macro Events | upcoming market-moving events | no |

**Important honesty note on the marketing.** CMC's launch copy advertises
"pre-computed signals: market regime, liquidity, ETF demand, cross-asset pressure,
risk flags." Those are **framings of what you derive from the 12 tools above**, not
discrete endpoints with those names (the academy article confirms they aren't
listed as discrete outputs). So "use CMC's regime signal" in practice means "use
tool #5 (market-cap TA) and/or tool #3 (global metrics) to define a regime." We
shouldn't claim to consume a named "regime signal" that isn't a real field.

## 3. Why this fits our strategy unusually well

Our locked entry is, in plain terms: **(a)** a regime gate — only hold when the
market trend is up; **(b)** EMA-12/26 momentum; **(c)** volatility-based sizing.

The Agent Hub hands us live versions of exactly (a) and (b):

- **(b) momentum** → tool #4 returns **EMA and MACD** directly. We could read CMC's
  EMA/MACD for the asset instead of computing our own on the live path.
- **(a) regime** → tool #5 (**Market Cap TA**) gives a *market-wide* trend read,
  and tool #3 gives **BTC dominance / Fear & Greed / altcoin-season** — a richer
  regime gate than our single-asset 50-day SMA. A natural upgrade: "go to cash if
  *either* our SMA gate *or* CMC's market regime says risk-off."

This is a genuine, defensible integration — we'd be using CMC data to *improve the
regime gate that is already the heart of our edge*, not stapling an unrelated API
call on for show. Judges can see the seam is real.

## 4. Access & pricing (the practical part)

Four ways in:

| Path | Auth | Cost | Best for us? |
| --- | --- | --- | --- |
| **x402** | **none** (wallet pays) | **$0.01 USDC/request on Base** | **Yes — cleanest.** No subscription, no tier worries; a demo is a handful of calls = a few cents. Needs a Base wallet w/ a little USDC. |
| MCP | CMC API key | depends on plan | works if free tier covers the TA tools (unconfirmed — see §5) |
| REST API | CMC API key | depends on plan | fine for scripted calls if the key tier allows |
| CMC CLI | CMC API key | depends on plan | terminal demos |

**Free tier (Basic):** free forever, 15,000 credits/month, 30+ endpoints — but
**historical OHLCV and the richer TA generally sit behind paid plans**. So:

- For **history / backtest** → the free tier is *not* enough; **keep Binance/ccxt**
  (which is why we used it in the first place — this is unchanged and correct).
- For a **live signal demo** → either the free key (if it covers the TA tools) or,
  more reliably, **x402 at a penny a call**.

## 5. The one thing to verify before building

**Does our existing free CMC key reach the Agent Hub TA tools (#4, #5), or do they
need a paid plan?** I couldn't confirm this definitively from the docs — CMC's
standard TA/historical endpoints are usually paid. **Mitigation:** the **x402 path
sidesteps the question entirely** (no key, no plan, $0.01/call), so even if the free
key falls short, the integration is still cheap and viable. I did not probe the
live endpoint with a key unattended.

## 6. Recommendation

**Build a bounded "live CMC signal adapter" — yes.** Concretely:

1. **Keep the backtest exactly as-is** (Binance/ccxt history, our own indicators,
   all the honesty guards). Untouched. This protects the validated result.
2. **Add a small live-decision module** (e.g. `bnb_bot/cmc_signals.py`) that, for
   "today", pulls from the Agent Hub:
   - market regime from **Market Cap TA (#5)** + **Global Metrics (#3)**,
   - the asset's **EMA/MACD (#4)**,
   and maps them onto our existing regime-gate + momentum logic to emit a live
   target weight — the same `signal()` contract our strategy already uses.
3. **Wire it behind a flag / separate script** (`scripts/live_signal.py`) so it's a
   clearly-labelled live path, never mixed into the backtest. Demonstrates "here's
   what the strategy says to do *right now*, powered by CMC."
4. **Access via x402** ($0.01/call) to avoid the tier question; document the cost.
5. **Update the SKILL.md** to document the CMC-powered live path as a second
   workflow ("Step: get today's signal from the CMC Agent Hub").

**Effort:** roughly half a day. **Risk:** low — it's additive, doesn't touch the
backtest, and fails loud if the API is unreachable (no silent fallback). **Upside:**
turns us from "technically eligible" into a real **"best use of CMC Data & Signal"**
contender (+$2k) and matches the Track 2 framing judges read against.

**What I would NOT do:** try to run the *backtest* on CMC data (no honest deep
history on the free tier), or claim to consume named "regime/risk" signals that
aren't real fields (use the actual TA/global-metrics tools and describe them
truthfully).

## 7. Open question for Markus (morning)

1. **Green-light the live CMC signal adapter?** (my recommendation: yes, bounded as
   §6.)
2. **Access:** OK to use **x402** (needs a Base wallet with a few dollars of USDC),
   or do you want me to first test whether your existing free CMC key reaches the
   TA tools?
3. Anything you'd want the live demo to *show* specifically (one token? the
   portfolio? a side-by-side "our SMA regime vs CMC's regime"?).

## Sources
- https://coinmarketcap.com/api/documentation/ai-agent-hub/mcp (the 12 tools)
- https://coinmarketcap.com/api/documentation/ai-agent-hub (access methods)
- https://pro.coinmarketcap.com/api/documentation/ai-agent-hub/skills/overview
- https://coinmarketcap.com/academy/article/coinmarketcap-ai-agent-hub-now-live
- https://coinmarketcap.com/api/pricing/ (free Basic tier: 15k credits, history paid)
