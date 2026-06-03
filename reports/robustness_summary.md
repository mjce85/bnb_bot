# Robustness summary (Stage 6)

Locked entry **vol_targeted_regime_momentum**, daily, 2021-01-01 → 2026-06-01. No parameter tuning — these are stress tests of the frozen config.

## 1. Cost sensitivity — portfolio vs equal-weight buy & hold

Base costs: 0.25% swap + 10 bps slippage + $0.30 gas, scaled 1–3×. The strategy trades far more than holding, so higher costs hit it harder — this shows how much edge survives.

| Costs | Strat return | Strat MaxDD | Strat Calmar | Hold return | Hold MaxDD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1× | 99.3% | 54.8% | 0.25 | 8.2% | 79.7% |
| 2× | 1.4% | 63.8% | 0.00 | 8.3% | 79.8% |
| 3× | -47.0% | 73.2% | -0.15 | 8.3% | 79.9% |

## 2. Out-of-universe — frozen entry on tokens it was never searched on

Drawdown beaten on **8/8** unseen tokens. The entry's parameters were chosen on BNB/CAKE/ETH/BTC only; holding the drawdown edge on coins it never saw is evidence it isn't curve-fit to the original four.

| Token | Return | B&H | MaxDD | B&H MaxDD | Calmar | B&H Calmar | DD beaten |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| XRP/USDT | 18.5% | 461.1% | 45.0% | 83.3% | 0.07 | 0.45 | yes |
| ADA/USDT | 64.7% | 34.3% | 28.9% | 92.2% | 0.33 | 0.06 | yes |
| DOGE/USDT | 117.9% | 1668.0% | 38.9% | 92.3% | 0.40 | 0.76 | yes |
| LINK/USDT | -16.7% | -23.1% | 38.3% | 90.3% | -0.09 | -0.05 | yes |
| DOT/USDT | -19.2% | -86.0% | 49.2% | 97.9% | -0.08 | -0.31 | yes |
| LTC/USDT | -50.7% | -59.1% | 60.6% | 88.9% | -0.20 | -0.17 | yes |
| TRX/USDT | 268.0% | 1207.9% | 52.1% | 69.6% | 0.52 | 0.87 | yes |
| AVAX/USDT | 23.5% | 145.5% | 37.2% | 93.9% | 0.11 | 0.19 | yes |
