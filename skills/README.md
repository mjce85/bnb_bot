# CMC Skills — Cadence

This folder packages the bnb_bot strategy as a **CMC Skill** (the lightweight,
folder-based format from
[CoinMarketCap's official skills repo](https://github.com/coinmarketcap-official/skills-for-ai-agents-by-CoinMarketCap)):
a `SKILL.md` workflow doc an AI agent reads to operate the strategy.

## Skills

| Skill | What it does |
| --- | --- |
| [`risk-controlled-momentum/`](risk-controlled-momentum/SKILL.md) | Generate and honestly backtest a volatility-targeted, regime-gated momentum strategy; report drawdown / risk-adjusted performance vs buy-and-hold with no look-ahead, costs on every fill, and an untouched holdout. |

Unlike CoinMarketCap's example skills (which are *data-access* references for the
CMC API), this is a ***strategy* skill** — exactly the deliverable BNB HACK
Track 2 asks for ("Skills that generate backtestable trading strategies from
market data").

## Install

Copy the skill folder into your agent's skills directory:

```bash
cp -r skills/risk-controlled-momentum /path/to/your/skills/directory/
```

The skill drives the strategy engine in this repository (`bnb_bot/` + `scripts/`),
so it expects to run alongside the repo. See the skill's own workflow for the
one-time `venv` install and the commands it invokes.
