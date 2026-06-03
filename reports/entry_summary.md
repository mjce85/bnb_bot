# Entry summary — locked submission strategy

Preset **vol_targeted_regime_momentum**: volatility-targeted, regime-gated momentum.

- target_vol **0.015**/bar, trend SMA **50**, vol lookback **15**, rebalance band **0.15**
- risk: position cap 100.0%, stop-loss 10.0%, drawdown breaker 20.0%
- window **2021-01-01 → 2026-06-01**, **1d** bars; every fill pays swap fee + slippage + gas; signals causal (no look-ahead).

| Symbol | Return | B&H | MaxDD | B&H MaxDD | Sharpe | B&H Sharpe | Calmar | B&H Calmar |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BNB/USDT | 278.8% | 1781.2% | 22.8% | 70.9% | 1.11 | 1.05 | 1.22 | 1.02 |
| CAKE/USDT | 33.7% | -92.5% | 31.3% | 97.7% | 0.36 | 0.07 | 0.18 | -0.40 |
| ETH/USDT | 76.7% | 175.0% | 31.9% | 79.3% | 0.55 | 0.63 | 0.35 | 0.26 |
| BTC/USDT | 73.1% | 150.8% | 37.3% | 76.7% | 0.57 | 0.58 | 0.29 | 0.24 |
