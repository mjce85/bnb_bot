# bnb_bot

Track 2 entry for **BNB HACK — AI Trading Agent** (CoinMarketCap × Trust
Wallet × BNB Chain, June 2026): a strategy engine that produces
**backtestable** trading strategies for BNB-chain / liquid tokens, judged on
returns, drawdown, and risk-adjusted performance.

Sibling to `imx_bot` (NFT trading) and `sol_bot`. Reuses their *discipline* —
backtest honesty + circuit-breaker risk control — not their code.

## Status

Scaffold sprint. See [`PLAN.md`](PLAN.md) for the task list and
[`CLAUDE.md`](CLAUDE.md) for the hard rules (no live trading this milestone,
fail-loud, guard the three backtest lies).

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pytest                       # correctness gate — must be green
python scripts/run_backtest.py --help
```

## Data

Historical OHLCV comes from `ccxt` (Binance spot, free, no key) cached as
parquet under `data/` (gitignored). No CoinMarketCap paid tier required;
the CMC free-tier key is used only for *live* latest quotes, later.
