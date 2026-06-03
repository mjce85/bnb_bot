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
| Backtestable spec, not a live agent | Validated strategy + honest backtest engine | ✅ done (the hard part) |
| Quant-research rigor; survives a post-lock held-out window | Holdout, 18/18 generalization, bootstrap, regime, cost tests | ✅ strong |
| Packaged as a **CMC Skill** (folder + `SKILL.md`) | Standalone Python repo | ❌ **need to package** |
| Data via **CMC Agent Hub / Data API** (+ pre-computed indicators) | Binance via `ccxt`; our own indicators | ⚠️ optional but rewarded; decide |

**We have the right brain, not yet the right socket.**

## Proposed next steps (next session)

1. **Read an actual example `SKILL.md`** from the repo (e.g. `market-report`,
   `cmc-api-crypto`) to learn the exact format/fields. (WebFetch the raw file.)
2. **Package our entry as a CMC Skill**: a `skill/` folder + `SKILL.md` that
   documents the strategy workflow (the regime+momentum gates, vol sizing, risk,
   the backtest + held-out evaluation), pointing at our existing Python as the
   implementation. Likely an **API-integration Skill**.
3. **Decide the data question**: keep Binance/ccxt for *historical backtest*
   (CMC free tier lacks deep history) but show we can *consume CMC Agent Hub
   signals* for the live/decision path — that ticks the "best use of CMC Agent
   Hub" special-prize box. Could map our regime/momentum to CMC's pre-computed
   regime/risk flags as an alternative signal source.
4. **`STRATEGY-SPEC.md`** — formal self-contained "backtestable spec" (the literal
   deliverable). 
5. Confirm exact submission mechanics on DoraHacks (register/submit page).

## Sources
- https://pro.coinmarketcap.com/api/documentation/ai-agent-hub/skills/overview
- https://github.com/coinmarketcap-official/skills-for-ai-agents-by-CoinMarketCap
- https://coinmarketcap.com/api/documentation/ai-agent-hub
- https://dorahacks.io/hackathon/bnbhack-twt-cmc
- https://coinmarketcap.com/api/hackathon/
