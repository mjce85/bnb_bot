# Robustness summary (Stage 6)

Locked entry **vol_targeted_regime_momentum**, daily, 2021-01-01 → 2026-06-01. No parameter tuning — these are stress tests of the frozen config.

## 1. Cost sensitivity — portfolio vs equal-weight buy & hold

Base costs: 0.25% swap + 10 bps slippage + $0.30 gas, scaled 1–3×. The strategy trades far more than holding, so higher costs hit it harder — this shows how much edge survives.

| Costs | Strat return | Strat MaxDD | Strat Calmar | Hold return | Hold MaxDD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1× | 84.5% | 56.9% | 0.22 | 8.2% | 79.7% |
| 2× | 15.2% | 64.4% | 0.04 | 8.3% | 79.8% |
| 3× | -18.3% | 72.1% | -0.05 | 8.3% | 79.9% |

## 2. Out-of-universe — frozen entry on tokens it was never searched on

Drawdown beaten on **8/8** unseen tokens. The entry's parameters were chosen on BNB/CAKE/ETH/BTC only; holding the drawdown edge on coins it never saw is evidence it isn't curve-fit to the original four.

| Token | Return | B&H | MaxDD | B&H MaxDD | Calmar | B&H Calmar | DD beaten |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| XRP/USDT | -18.0% | 461.1% | 59.6% | 83.3% | -0.06 | 0.45 | yes |
| ADA/USDT | 103.9% | 34.3% | 27.4% | 92.2% | 0.51 | 0.06 | yes |
| DOGE/USDT | 109.6% | 1668.0% | 38.4% | 92.3% | 0.38 | 0.76 | yes |
| LINK/USDT | -20.8% | -23.1% | 23.0% | 90.3% | -0.18 | -0.05 | yes |
| DOT/USDT | -31.0% | -86.0% | 56.7% | 97.9% | -0.12 | -0.31 | yes |
| LTC/USDT | -60.9% | -59.1% | 68.5% | 88.9% | -0.23 | -0.17 | yes |
| TRX/USDT | 232.8% | 1207.9% | 59.1% | 69.6% | 0.42 | 0.87 | yes |
| AVAX/USDT | -9.1% | 145.5% | 44.5% | 93.9% | -0.04 | 0.19 | yes |
