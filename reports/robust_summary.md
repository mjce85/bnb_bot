# Robust redesign summary (R3)

Window **2021-01-01 → 2026-06-01**, **1d** bars, trend filter SMA **100**, walk-forward **5 folds**.

Headline numbers are **risk-off** (raw signal). Every fill pays swap fee + slippage + gas; signals are causal. The last two columns show the same strategy **risk-on**, included only to expose the breaker-lockout bug (see note at bottom): exposure collapses to ~2% and trades to ~3.

## Full window — strategy vs buy & hold (risk-off)

| Symbol | Strategy | Return | B&H | Excess | MaxDD | B&H MaxDD | Sharpe | Exposure | Trades | RiskOn Exp | RiskOn Trades |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BNB/USDT | trend_following | 1.3% | 1781.2% | -1779.9% | 80.3% | 70.9% | 0.25 | 50.7% | 117 | 2.0% | 3 |
| BNB/USDT | momentum_regime | 132.9% | 1781.2% | -1648.3% | 61.3% | 70.9% | 0.58 | 42.9% | 88 | 2.0% | 3 |
| BNB/USDT | meanrev_regime | -48.3% | 1781.2% | -1829.5% | 60.2% | 70.9% | -0.39 | 9.1% | 101 | 0.1% | 3 |
| CAKE/USDT | trend_following | -70.3% | -92.5% | 22.2% | 76.4% | 97.7% | -0.08 | 36.4% | 131 | 3.2% | 5 |
| CAKE/USDT | momentum_regime | -41.6% | -92.5% | 50.9% | 68.4% | 97.7% | 0.10 | 27.9% | 93 | 1.6% | 3 |
| CAKE/USDT | meanrev_regime | -24.6% | -92.5% | 67.9% | 44.7% | 97.7% | -0.16 | 6.4% | 70 | 4.4% | 42 |
| ETH/USDT | trend_following | -19.7% | 175.0% | -194.7% | 76.7% | 79.3% | 0.18 | 50.1% | 132 | 2.2% | 3 |
| ETH/USDT | momentum_regime | -13.9% | 175.0% | -188.9% | 70.6% | 79.3% | 0.17 | 38.1% | 106 | 2.1% | 3 |
| ETH/USDT | meanrev_regime | 16.7% | 175.0% | -158.3% | 44.9% | 79.3% | 0.24 | 11.9% | 112 | 0.2% | 3 |
| BTC/USDT | trend_following | 68.8% | 150.8% | -82.0% | 40.2% | 76.7% | 0.45 | 49.2% | 105 | 0.7% | 6 |
| BTC/USDT | momentum_regime | 129.8% | 150.8% | -21.0% | 36.7% | 76.7% | 0.65 | 39.3% | 81 | 0.8% | 6 |
| BTC/USDT | meanrev_regime | -21.4% | 150.8% | -172.2% | 25.6% | 76.7% | -0.19 | 10.4% | 110 | 2.2% | 25 |

## Walk-forward — folds that beat buy & hold

| Symbol | Strategy | Folds beaten | Mean excess/fold | Per-fold excess |
| --- | --- | ---: | ---: | --- |
| BNB/USDT | trend_following | 2/5 | -178.5% | -934.5%, -14.0%, 58.7%, -4.9%, 2.4% |
| BNB/USDT | momentum_regime | 3/5 | -166.5% | -901.1%, -7.0%, 43.5%, 4.5%, 27.9% |
| BNB/USDT | meanrev_regime | 2/5 | -206.6% | -945.8%, 19.9%, -91.4%, 2.0%, -17.6% |
| CAKE/USDT | trend_following | 3/5 | 34.7% | 52.1%, 8.3%, 135.9%, -11.2%, -11.6% |
| CAKE/USDT | momentum_regime | 3/5 | 46.4% | 63.0%, 12.7%, 164.7%, -4.8%, -3.6% |
| CAKE/USDT | meanrev_regime | 5/5 | 36.7% | 80.4%, 41.7%, 3.5%, 19.3%, 38.6% |
| ETH/USDT | trend_following | 2/5 | -59.1% | -269.0%, 20.7%, -49.8%, 38.0%, -35.6% |
| ETH/USDT | momentum_regime | 2/5 | -59.2% | -250.0%, 10.4%, -59.3%, 39.5%, -36.6% |
| ETH/USDT | meanrev_regime | 2/5 | -55.7% | -273.8%, 42.8%, -90.7%, 58.9%, -15.9% |
| BTC/USDT | trend_following | 2/5 | -15.0% | -45.9%, 52.4%, -69.0%, -13.4%, 1.0% |
| BTC/USDT | momentum_regime | 2/5 | -13.1% | -48.0%, 65.8%, -71.6%, -18.6%, 7.0% |
| BTC/USDT | meanrev_regime | 2/5 | -43.5% | -45.2%, 49.7%, -202.4%, -29.8%, 10.3% |

## KNOWN ISSUE — drawdown-breaker lockout

The `RiskOn Exp` / `RiskOn Trades` columns above show the bug: with the drawdown breaker active, exposure collapses to ~2% and trades to ~3 over five years. Cause: the breaker halts new entries while equity is >=20% below its peak, but once a strategy is forced into cash during a drawdown its cash balance is frozen and can never reclaim the old peak — so the breaker stays tripped permanently. The peak reference must reset (e.g. when the book goes flat). This is a risk-semantics decision for the operator; the headline numbers are risk-off so they are not affected.
