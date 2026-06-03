# Baseline summary (T8)

Window **2024-06-01 → 2026-06-01**, timeframe **1h**, split **70/30** (in-sample head / out-of-sample tail).

Risk-off baseline (raw strategy weight). Every fill pays swap fee + slippage + gas. Signals causal; fills at next open.

| Symbol | Strategy | Window | Return | MaxDD | Sharpe | Sortino | Calmar | WinRate | Trades | Bars |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BNB/USDT | momentum | in_sample | -54.56% | 72.71% | -1.26 | -1.80 | -0.59 | 14.94% | 629 | 12264 |
| BNB/USDT | momentum | out_of_sample | -61.88% | 67.31% | -5.05 | -6.62 | -1.19 | 9.38% | 291 | 5256 |
| BNB/USDT | mean_reversion | in_sample | -91.39% | 91.81% | -4.18 | -5.37 | -0.90 | 19.45% | 996 | 12264 |
| BNB/USDT | mean_reversion | out_of_sample | -71.07% | 71.49% | -5.80 | -7.35 | -1.22 | 17.75% | 442 | 5256 |
| CAKE/USDT | momentum | in_sample | 75.14% | 45.26% | 0.90 | 1.46 | 1.09 | 18.44% | 582 | 12264 |
| CAKE/USDT | momentum | out_of_sample | -55.04% | 60.09% | -3.02 | -4.14 | -1.23 | 14.46% | 252 | 5256 |
| CAKE/USDT | mean_reversion | in_sample | -98.92% | 99.01% | -4.32 | -5.58 | -0.97 | 25.33% | 916 | 12264 |
| CAKE/USDT | mean_reversion | out_of_sample | -74.16% | 74.91% | -4.75 | -6.35 | -1.20 | 22.18% | 429 | 5256 |
| ETH/USDT | momentum | in_sample | -67.91% | 75.28% | -1.54 | -2.24 | -0.74 | 13.58% | 646 | 12264 |
| ETH/USDT | momentum | out_of_sample | -63.08% | 65.59% | -3.91 | -5.30 | -1.24 | 13.94% | 249 | 5256 |
| ETH/USDT | mean_reversion | in_sample | -94.03% | 94.22% | -4.00 | -5.05 | -0.92 | 25.47% | 1053 | 12264 |
| ETH/USDT | mean_reversion | out_of_sample | -75.92% | 76.28% | -5.05 | -6.51 | -1.19 | 23.74% | 421 | 5256 |
| BTC/USDT | momentum | in_sample | -63.58% | 66.57% | -2.04 | -2.86 | -0.77 | 12.72% | 596 | 12264 |
| BTC/USDT | momentum | out_of_sample | -68.54% | 69.62% | -6.27 | -8.24 | -1.23 | 9.79% | 294 | 5256 |
| BTC/USDT | mean_reversion | in_sample | -89.16% | 89.61% | -4.86 | -6.44 | -0.89 | 14.99% | 977 | 12264 |
| BTC/USDT | mean_reversion | out_of_sample | -72.78% | 72.86% | -6.40 | -8.10 | -1.22 | 17.02% | 427 | 5256 |
