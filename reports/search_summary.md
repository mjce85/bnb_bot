# Parameter search summary (P1)

Window **2021-01-01 → 2026-06-01**, **1d** bars. Train/holdout split **75/25** per token; the search saw TRAIN only.

Searched **120** configs; **120** beat buy-and-hold drawdown on every token (the eligibility gate). Ranked by mean train Sharpe across tokens. One config chosen for all tokens (no per-token fit).

## Winning config

- **target_vol**: 0.015
- **trend_period**: 50
- **vol_lookback**: 30
- **rebalance_band**: 0.03
- mean train Sharpe across tokens: **0.658**, mean train drawdown: **31.7%**

## Top configs (train) — plateau check

| target_vol | trend | vol_lb | reb_band | mean Sharpe | mean DD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.015 | 50 | 30 | 0.03 | 0.658 | 31.7% |
| 0.015 | 50 | 30 | 0.0 | 0.631 | 32.0% |
| 0.02 | 50 | 30 | 0.03 | 0.628 | 39.5% |
| 0.015 | 150 | 30 | 0.03 | 0.623 | 24.1% |
| 0.02 | 50 | 30 | 0.0 | 0.609 | 39.7% |
| 0.015 | 50 | 20 | 0.03 | 0.609 | 31.0% |
| 0.015 | 150 | 30 | 0.0 | 0.597 | 24.4% |
| 0.02 | 150 | 30 | 0.03 | 0.595 | 30.9% |

## Holdout validation (untouched 25%) — winner only, scored once

| Symbol | Return | B&H | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | Calmar | B&H Calmar | DD beaten |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| BNB/USDT | 48.3% | 1.8% | 17.9% | 55.5% | 1.33 | 0.29 | 1.89 | 0.02 | yes |
| CAKE/USDT | -15.9% | 1.5% | 24.9% | 72.7% | -0.57 | 0.50 | -0.50 | 0.02 | yes |
| ETH/USDT | 16.4% | -38.5% | 19.6% | 62.3% | 0.67 | -0.13 | 0.61 | -0.48 | yes |
| BTC/USDT | -11.7% | -29.3% | 29.1% | 49.7% | -0.41 | -0.36 | -0.30 | -0.46 | yes |
