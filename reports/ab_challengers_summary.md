# A/B tournament — entry vs creative challengers

Daily 2021→2026, 4-token shared book. Identical costs, risk overlay, and rebalance band (0.15) for all; parameters by convention, not searched. Holdout = last 25% of the (continuously-warmed) run.

## Portfolio — FULL window

| Strategy | Return | MaxDD | Sharpe | Calmar |
| --- | ---: | ---: | ---: | ---: |
| ENTRY (vol-tgt regime mom) | 84.5% | 56.9% | 0.50 | 0.22 |
| donchian 20/10 breakout | 57.3% | 64.3% | 0.42 | 0.14 |
| tsmom 365d | 20.8% | 56.9% | 0.28 | 0.06 |
| rotation (dual-mom top2/90d) | -62.5% | 77.1% | -0.12 | -0.22 |
| equal-weight hold | 8.2% | 79.7% | 0.37 | 0.02 |

## Portfolio — HOLDOUT tail (last 25%)

| Strategy | Return | MaxDD | Sharpe | Calmar |
| --- | ---: | ---: | ---: | ---: |
| ENTRY (vol-tgt regime mom) | -7.8% | 14.9% | -0.47 | -0.40 |
| donchian 20/10 breakout | -37.6% | 50.4% | -0.41 | -0.60 |
| tsmom 365d | -35.9% | 44.1% | -0.93 | -0.65 |
| rotation (dual-mom top2/90d) | -14.1% | 45.7% | -0.05 | -0.24 |
| equal-weight hold | -2.1% | 55.2% | 0.22 | -0.03 |

## Per token — FULL window return / maxDD (Calmar)

| Token | ENTRY | donchian | tsmom | buy & hold |
| --- | --- | --- | --- | --- |
| BNB/USDT | 278.8% / 22.8% (1.22) | 1303.1% / 40.9% (1.54) | -1.6% / 57.7% (-0.01) | 1781.2% / 70.9% (1.02) |
| CAKE/USDT | 33.7% / 31.3% (0.18) | -3.0% / 81.9% (-0.01) | -84.7% / 87.9% (-0.34) | -92.5% / 97.7% (-0.40) |
| ETH/USDT | 76.7% / 31.9% (0.35) | 24.3% / 63.5% (0.06) | 12.4% / 49.1% (0.04) | 175.0% / 79.3% (0.26) |
| BTC/USDT | 73.1% / 37.3% (0.29) | 32.1% / 56.5% (0.09) | 191.6% / 28.1% (0.78) | 150.8% / 76.7% (0.24) |
