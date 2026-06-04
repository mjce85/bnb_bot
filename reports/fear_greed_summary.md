# Fear & Greed overlay — does CMC sentiment improve the entry?

Entry **with vs without** a Fear & Greed gate (step to cash when F&G ≥ 75, the standard 'Extreme Greed' boundary; not tuned).

**Proxy quality:** alternative.me vs CMC F&G correlate **0.894** over **1070** overlapping days — so alternative.me is a sound stand-in for extending the backtest before CMC's index begins (2023-06-29).

- alternative.me F&G: 2018-02-01 → 2026-06-04 · CMC F&G: 2023-06-29 → 2026-06-03
- F&G lookup is strictly pre-bar (no look-ahead); overlay only ever cuts exposure; backtest is otherwise the locked entry.

## Per token — FULL window (2021-01-01 → 2026-06-01), alternative.me F&G

| Token / variant | Return | MaxDD | Sharpe | Calmar |
| --- | ---: | ---: | ---: | ---: |
| BNB/USDT — no gate | 278.8% | 22.8% | 1.11 | 1.22 |
| BNB/USDT — +F&G gate | 101.4% | 23.8% | 0.69 | 0.58 |
| BNB/USDT — buy & hold | 1781.2% | 70.9% | 1.05 | 1.02 |
| CAKE/USDT — no gate | 33.7% | 31.3% | 0.36 | 0.18 |
| CAKE/USDT — +F&G gate | -16.3% | 35.0% | -0.08 | -0.09 |
| CAKE/USDT — buy & hold | -92.5% | 97.7% | 0.07 | -0.40 |
| ETH/USDT — no gate | 76.7% | 31.9% | 0.55 | 0.35 |
| ETH/USDT — +F&G gate | 39.5% | 37.7% | 0.38 | 0.17 |
| ETH/USDT — buy & hold | 175.0% | 79.3% | 0.63 | 0.26 |
| BTC/USDT — no gate | 73.1% | 37.3% | 0.57 | 0.29 |
| BTC/USDT — +F&G gate | 61.5% | 37.2% | 0.53 | 0.25 |
| BTC/USDT — buy & hold | 150.8% | 76.7% | 0.58 | 0.24 |

## Per token — CMC window (2023-07-01 → 2026-06-01), CMC vs alternative.me

| Token / variant | Return | MaxDD | Sharpe | Calmar |
| --- | ---: | ---: | ---: | ---: |
| BNB/USDT — no gate | 140.9% | 22.8% | 1.27 | 1.54 |
| BNB/USDT — +F&G (CMC) | 73.3% | 28.7% | 0.92 | 0.72 |
| BNB/USDT — +F&G (alt.me) | 63.9% | 23.8% | 0.85 | 0.78 |
| CAKE/USDT — no gate | 28.5% | 31.3% | 0.48 | 0.29 |
| CAKE/USDT — +F&G (CMC) | -11.0% | 36.5% | -0.10 | -0.11 |
| CAKE/USDT — +F&G (alt.me) | -3.9% | 34.9% | 0.03 | -0.04 |
| ETH/USDT — no gate | 66.7% | 29.9% | 0.81 | 0.64 |
| ETH/USDT — +F&G (CMC) | 53.9% | 25.1% | 0.74 | 0.64 |
| ETH/USDT — +F&G (alt.me) | 37.9% | 21.9% | 0.58 | 0.53 |
| BTC/USDT — no gate | 94.4% | 29.2% | 1.08 | 0.88 |
| BTC/USDT — +F&G (CMC) | 79.1% | 29.2% | 1.04 | 0.76 |
| BTC/USDT — +F&G (alt.me) | 71.5% | 30.1% | 0.96 | 0.68 |

## Portfolio (what you'd actually run)

| Variant | Return | MaxDD | Sharpe | Calmar |
| --- | ---: | ---: | ---: | ---: |
| FULL, no gate (2021-01-01+) | 84.5% | 56.9% | 0.50 | 0.22 |
| FULL, +F&G gate (alt.me) | -2.5% | 31.1% | 0.01 | -0.02 |
| FULL, equal-weight hold | 8.2% | 79.7% | 0.37 | 0.02 |
| CMC-window, no gate (2023-07-01+) | 107.6% | 43.5% | 0.94 | 0.65 |
| CMC-window, +F&G (CMC) | 70.7% | 35.1% | 0.73 | 0.57 |
| CMC-window, +F&G (alt.me) | 71.6% | 32.6% | 0.73 | 0.62 |
