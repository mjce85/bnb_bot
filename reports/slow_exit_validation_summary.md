# Slow-exit (let-winners-run) — disciplined validation of the A/B lead

Entry with `StickyExit` (hold until the 50-day trend breaks) vs the locked entry (`RegimeGated`, exits on fast-EMA flip). Same EMA-12/26, same SMA-50, same vol target 0.015 / lookback 15 — **no new or tuned parameters.**

## 18-token generalization (2017-01-01+, full history)

- **SLOW-EXIT beats ENTRY on return on 8/18 tokens.**
- Drawdown beaten vs hold: **SLOW 18/18**, ENTRY 18/18 (does the slower exit keep the risk edge?).
- Average return: ENTRY 272.8% → **SLOW 279.3%**; average maxDD: ENTRY 41.7% → **SLOW 41.6%**.

| Token | ENTRY ret/DD | SLOW ret/DD | hold ret/DD |
| --- | --- | --- | --- |
| BTC/USDT | 1110.9%/37.2% | 1043.5%/37.2% | 1619.0%/83.3% |
| ETH/USDT | 575.1%/31.9% | 558.3%/31.9% | 583.9%/94.0% |
| BNB/USDT | 1100.7%/22.8% | 1236.1%/22.8% | 45128.8%/80.0% |
| CAKE/USDT | 33.7%/31.3% | 30.9%/31.3% | -92.5%/97.7% |
| XRP/USDT | -14.9%/59.6% | -17.3%/62.1% | 49.5%/85.3% |
| ADA/USDT | 429.1%/27.3% | 394.3%/28.8% | -3.2%/94.0% |
| DOGE/USDT | 857.2%/38.4% | 928.6%/35.3% | 2491.5%/92.3% |
| LINK/USDT | 211.8%/23.0% | 211.8%/23.0% | 1768.5%/90.2% |
| DOT/USDT | -3.8%/56.7% | -5.3%/56.7% | -62.0%/97.9% |
| LTC/USDT | -28.6%/68.4% | -27.2%/68.3% | -82.4%/93.7% |
| TRX/USDT | 376.4%/59.1% | 370.1%/59.1% | 626.1%/83.4% |
| AVAX/USDT | 64.5%/44.5% | 69.5%/45.8% | 68.2%/93.9% |
| ATOM/USDT | 9.8%/42.7% | 15.1%/42.7% | -48.5%/96.3% |
| XLM/USDT | 26.6%/34.0% | 39.5%/31.3% | -12.5%/90.8% |
| ETC/USDT | 70.0%/39.1% | 84.0%/39.7% | -44.7%/94.1% |
| EOS/USDT | -3.4%/50.4% | -8.0%/53.2% | -93.6%/97.5% |
| BCH/USDT | 16.6%/45.3% | 24.8%/41.4% | 39.0%/94.3% |
| FIL/USDT | 79.2%/38.6% | 79.2%/38.6% | -98.9%/99.7% |

## 4-token portfolio

| Variant | Window | Return | MaxDD | Sharpe | Calmar |
| --- | --- | ---: | ---: | ---: | ---: |
| ENTRY | full | 84.5% | 56.9% | 0.50 | 0.22 |
| ENTRY | holdout | -7.8% | 14.9% | -0.47 | -0.40 |
| SLOW-EXIT | full | 84.6% | 56.9% | 0.50 | 0.22 |
| SLOW-EXIT | holdout | -7.8% | 14.9% | -0.47 | -0.40 |
| hold | full | 8.2% | 79.7% | 0.37 | 0.02 |
| hold | holdout | -2.1% | 55.2% | 0.22 | -0.03 |
