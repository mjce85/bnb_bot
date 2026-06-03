# Entry summary — locked submission strategy

Preset **vol_targeted_regime_momentum**: volatility-targeted, regime-gated momentum.

- target_vol **0.015**/bar, trend SMA **50**, vol lookback **30**, rebalance band **0.03**
- risk: position cap 100.0%, stop-loss 10.0%, drawdown breaker 20.0%
- window **2021-01-01 → 2026-06-01**, **1d** bars; every fill pays swap fee + slippage + gas; signals causal (no look-ahead).

| Symbol | Return | B&H | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | Calmar | B&H Calmar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BNB/USDT | 191.5% | 1781.2% | 22.0% | 70.9% | 0.96 | 1.05 | 0.99 | 1.02 |
| CAKE/USDT | 19.6% | -92.5% | 36.2% | 97.7% | 0.27 | 0.07 | 0.10 | -0.40 |
| ETH/USDT | 34.9% | 175.0% | 35.8% | 79.3% | 0.37 | 0.63 | 0.16 | 0.26 |
| BTC/USDT | 71.3% | 150.8% | 37.4% | 76.7% | 0.57 | 0.58 | 0.28 | 0.24 |
