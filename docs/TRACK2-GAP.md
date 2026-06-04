# Track 2 conformance — gap analysis & handoff (2026-06-04)

Captured from web research so a fresh session can resume. **This is the open
question that matters more than any further analysis.**

## What Track 2 actually asks for

- **"Build CMC Skills that generate trading strategies from market data. Ship a
  backtestable spec, not a live agent. Think quant research."**
- Track 2 = **$6,000 prize, 3 winners**.
- Judged on **returns, max drawdown, risk-adjusted performance, rule adherence**,
  by a discretionary expert panel (technical execution, originality, real-world
  relevance).
- **CRITICAL:** *"The agent runs against a held-out market window AFTER submission
  lock."* → judges re-run our strategy on fresh, unseen data post-submission.
  This is exactly what our no-lookahead / holdout / walk-forward discipline was
  built for — strong validation of the approach. It also means **robustness and
  no-overfitting matter more than a pretty in-sample number** (our whole thesis).
- Extra $6k special prizes for best use of each partner tool (CMC Agent Hub,
  Trust Wallet Agent Kit, BNB AI Agent SDK) — so **using the CMC Agent Hub is
  rewarded, not strictly required**.

## What a "CMC Skill" is (from the official repo + docs)

- Open-source template repo: **github.com/coinmarketcap-official/skills-for-ai-agents-by-CoinMarketCap**
- A Skill is **lightweight**: a **folder** containing a **`SKILL.md`** (a markdown
  workflow/instructions doc) + implementation code + integration config. Install =
  *"copy the skill folder to your agent's skills directory."* No heavy framework.
- Four flavors: **CLI**, **MCP** (Model Context Protocol, real-time data),
  **x402** (pay-per-request, $0.01 USDC on Base), **API** (direct REST).
- Example skill paths seen: `skills/market-report/SKILL.md`,
  `skills/crypto-research/SKILL.md`, `skills/cmc-mcp/SKILL.md`,
  `skills/cmc-api-crypto/SKILL.md`.
- The CMC **Agent Hub / Data API** serves *pre-computed* signals (market regime,
  liquidity, ETF demand, cross-asset pressure, risk flags) in an LLM-friendly
  format, via a single MCP endpoint (12 tools) / x402 / CLI / REST.

## The gap (what we have vs. what's asked)

| Track 2 wants | We have | Status |
| --- | --- | --- |
| Backtestable spec, not a live agent | Validated strategy + honest backtest engine + formal `STRATEGY-SPEC.md` | ✅ done |
| Quant-research rigor; survives a post-lock held-out window | Holdout, 18/18 generalization, bootstrap, regime, cost tests | ✅ strong |
| Packaged as a **CMC Skill** (folder + `SKILL.md`) | `skills/risk-controlled-momentum/SKILL.md` in the real CMC format | ✅ **done (Stage 10, 2026-06-04)** |
| Data via **CMC Agent Hub / Data API** (+ pre-computed indicators) | Binance via `ccxt`; our own indicators | ⚠️ **the live decision** — see below |

**Update 2026-06-04:** the socket is now built. The strategy is packaged as a
CMC Skill and the formal spec is written. The remaining open question is the
data/Agent-Hub one — and submission research sharpened it.

**Sharpened finding on the Agent Hub (matters for the decision):** CoinMarketCap's
own Track 2 page describes the expected deliverable as *"a backtestable spec
**using the CMC Agent Hub & Data API**, with pre-computed indicators and Skills
Marketplace integration."* So consuming CMC data is more central to Track 2 than
this doc originally assumed — likely the difference between a *technically
eligible* entry (a CMC Skill satisfies the hard ≥1-sponsor-capability rule) and a
*"best use of CMC Data & Signal"* contender (+$2k special prize). Recommend
reconsidering whether to wire the Agent Hub in as the next build step.

**Submission mechanics (confirmed):** submit on DoraHacks
(`dorahacks.io/hackathon/bnbhack-twt-cmc`); lock **21 Jun 2026 12:00 UTC**. Track 2
prizes: $3k / $2k / $1k, plus three $2k special prizes (CMC Data & Signal, Trust
Wallet Agent Kit, BNB AI Agent SDK) that stack.

## Next steps — status (updated 2026-06-04, Stage 10)

1. ✅ **Read an actual example `SKILL.md`.** DONE — fetched `cmc-api-crypto/
   SKILL.md`; format captured (YAML frontmatter + workflow body + `references/`).
2. ✅ **Package our entry as a CMC Skill.** DONE —
   `skills/risk-controlled-momentum/SKILL.md` + `skills/README.md` (install).
3. ⚠️ **THE LIVE DECISION — the data / Agent Hub question.** Still open, and now
   the highest-value open item (see the sharpened finding above). Keep Binance/
   ccxt for *historical backtest* (CMC free tier lacks deep history) regardless;
   the question is whether to *also consume CMC Agent Hub signals* on the
   decision path — mapping our regime/momentum to CMC's pre-computed regime/risk
   flags. This competes for the $2k "best use of CMC Data & Signal" prize and
   matches CMC's own Track 2 framing. Operator call; needs a free-tier-vs-paid/
   x402 check on Agent Hub access first.
4. ✅ **`STRATEGY-SPEC.md`.** DONE — formal self-contained spec at repo root.
5. ✅ **Confirm submission mechanics.** DONE — DoraHacks, lock 21 Jun 12:00 UTC;
   prizes and rules captured above.

## Sources
- https://pro.coinmarketcap.com/api/documentation/ai-agent-hub/skills/overview
- https://github.com/coinmarketcap-official/skills-for-ai-agents-by-CoinMarketCap
- https://coinmarketcap.com/api/documentation/ai-agent-hub
- https://dorahacks.io/hackathon/bnbhack-twt-cmc
- https://coinmarketcap.com/api/hackathon/
