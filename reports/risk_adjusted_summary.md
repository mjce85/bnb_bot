# Risk-adjusted summary (S3)

Window **2021-01-01 → 2026-06-01**, **1d** bars, trend/regime SMA **100**, vol target **0.025/bar** over **20** bars, walk-forward **5 folds**.

All variants **risk-on** with the fixed drawdown breaker (S1) + 10% stop-loss. The question is risk-*adjusted* quality (drawdown, Sharpe, Calmar), not raw return — a long-only strategy won't out-return a bull market. Every fill pays swap fee + slippage + gas; signals causal.

## Full window vs buy & hold

| Symbol | Variant | Return | B&H | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | Calmar | B&H Calmar | Exposure | Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BNB/USDT | mom_regime | 132.9% | 1781.2% | 61.3% | 70.9% | 0.58 | 1.05 | 0.28 | 1.02 | 42.9% | 88 |
| BNB/USDT | mom_regime_voltgt | 184.2% | 1781.2% | 44.8% | 70.9% | 0.75 | 1.05 | 0.48 | 1.02 | 42.9% | 517 |
| BNB/USDT | trend_voltgt | 67.7% | 1781.2% | 60.1% | 70.9% | 0.45 | 1.05 | 0.17 | 1.02 | 50.7% | 637 |
| CAKE/USDT | mom_regime | -42.3% | -92.5% | 68.8% | 97.7% | 0.09 | 0.07 | -0.14 | -0.40 | 27.7% | 98 |
| CAKE/USDT | mom_regime_voltgt | 9.7% | -92.5% | 50.3% | 97.7% | 0.21 | 0.07 | 0.04 | -0.40 | 27.7% | 514 |
| CAKE/USDT | trend_voltgt | -18.8% | -92.5% | 54.2% | 97.7% | 0.05 | 0.07 | -0.07 | -0.40 | 36.3% | 672 |
| ETH/USDT | mom_regime | -19.4% | 175.0% | 72.5% | 79.3% | 0.14 | 0.63 | -0.05 | 0.26 | 38.0% | 108 |
| ETH/USDT | mom_regime_voltgt | 1.6% | 175.0% | 52.6% | 79.3% | 0.17 | 0.63 | 0.01 | 0.26 | 38.0% | 656 |
| ETH/USDT | trend_voltgt | 6.7% | 175.0% | 54.7% | 79.3% | 0.21 | 0.63 | 0.02 | 0.26 | 50.1% | 855 |
| BTC/USDT | mom_regime | 139.2% | 150.8% | 34.2% | 76.7% | 0.67 | 0.58 | 0.51 | 0.24 | 39.2% | 81 |
| BTC/USDT | mom_regime_voltgt | 110.1% | 150.8% | 30.8% | 76.7% | 0.63 | 0.58 | 0.48 | 0.24 | 39.2% | 391 |
| BTC/USDT | trend_voltgt | 48.8% | 150.8% | 39.2% | 76.7% | 0.39 | 0.58 | 0.19 | 0.24 | 49.1% | 500 |

## Walk-forward — consistency across unseen folds

Drawdown-wins = folds where the strategy's max drawdown was *smaller* than buy-and-hold's (the risk-adjusted bet). Return-wins = folds where it out-returned hold.

| Symbol | Variant | DD-wins | Return-wins |
| --- | --- | ---: | ---: |
| BNB/USDT | mom_regime | 5/5 | 3/5 |
| BNB/USDT | mom_regime_voltgt | 5/5 | 3/5 |
| BNB/USDT | trend_voltgt | 5/5 | 2/5 |
| CAKE/USDT | mom_regime | 5/5 | 3/5 |
| CAKE/USDT | mom_regime_voltgt | 5/5 | 5/5 |
| CAKE/USDT | trend_voltgt | 5/5 | 5/5 |
| ETH/USDT | mom_regime | 5/5 | 2/5 |
| ETH/USDT | mom_regime_voltgt | 5/5 | 2/5 |
| ETH/USDT | trend_voltgt | 5/5 | 2/5 |
| BTC/USDT | mom_regime | 5/5 | 2/5 |
| BTC/USDT | mom_regime_voltgt | 5/5 | 2/5 |
| BTC/USDT | trend_voltgt | 5/5 | 2/5 |
