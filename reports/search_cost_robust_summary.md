# Cost-robust parameter search summary

Window **2021-01-01 → 2026-06-01**, **1d** bars. Train/holdout split **75/25** per token; the search saw TRAIN only.

Searched **300** configs; **300** beat buy-and-hold drawdown on every token (the eligibility gate). Ranked by mean train Sharpe across tokens. One config chosen for all tokens (no per-token fit).

## Winning config

- **target_vol**: 0.015
- **trend_period**: 50
- **vol_lookback**: 15
- **rebalance_band**: 0.15
- mean train Sharpe across tokens: **0.556**, mean train drawdown: **33.2%**

## Top configs (train) — plateau check

| target_vol | trend | vol_lb | reb_band | mean Sharpe | mean DD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.015 | 50 | 15 | 0.15 | 0.556 | 33.2% |
| 0.015 | 50 | 30 | 0.1 | 0.551 | 34.7% |
| 0.015 | 50 | 30 | 0.06 | 0.533 | 34.6% |
| 0.015 | 50 | 20 | 0.15 | 0.527 | 35.0% |
| 0.015 | 150 | 30 | 0.1 | 0.521 | 27.4% |
| 0.02 | 50 | 30 | 0.1 | 0.519 | 42.5% |
| 0.015 | 50 | 30 | 0.15 | 0.509 | 34.9% |
| 0.02 | 50 | 30 | 0.15 | 0.508 | 43.9% |

## Holdout validation (untouched 25%) — winner only, scored once

| Symbol | Return | B&H | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | Calmar | B&H Calmar | DD beaten |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| BNB/USDT | 46.1% | 1.8% | 21.2% | 55.5% | 1.26 | 0.29 | 1.53 | 0.02 | yes |
| CAKE/USDT | -9.6% | 1.5% | 24.5% | 72.7% | -0.25 | 0.50 | -0.30 | 0.02 | yes |
| ETH/USDT | 39.3% | -38.5% | 20.4% | 62.3% | 1.02 | -0.13 | 1.36 | -0.48 | yes |
| BTC/USDT | -7.2% | -29.3% | 29.2% | 49.7% | -0.20 | -0.36 | -0.18 | -0.46 | yes |
