# Portfolio summary

The locked entry **vol_targeted_regime_momentum** traded across 4 tokens on one shared book (2021-01-01 → 2026-06-01, 1d), vs an equal-weight buy-and-hold portfolio. Total-exposure cap 100.0%; risk-on. Metrics are equity-curve based (return, drawdown, Sharpe, Sortino, Calmar).

## Full window

| | Return | MaxDD | Sharpe | Sortino | Calmar |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Portfolio strategy** | 99.3% | 54.8% | 0.53 | 0.77 | 0.25 |
| Equal-weight buy & hold | 8.2% | 79.7% | 0.37 | 0.51 | 0.02 |

## Capital utilization & correlation (honest)

Portfolio max drawdown **54.8%** is *higher* than the average single-token strategy drawdown **32.8%** (per-token: 22.0%, 36.2%, 35.8%, 37.4%) — not lower. Two honest reasons: these tokens are highly correlated (they fall together, so combining them diversifies little), and the portfolio deploys the cash that single-token runs leave idle. That fuller deployment is exactly why portfolio *return* is far higher than equal-weight holding. The benefit here is **capital efficiency vs holding**, not drawdown reduction vs a single token. Decorrelated assets would smooth the curve (see `test_diversification_reduces_drawdown`); this token set isn't decorrelated.

## Walk-forward (5 independent folds) vs equal-weight hold

Drawdown beaten in **5/5** folds.

| Fold | Return | Hold | MaxDD | Hold MaxDD | DD beaten |
| ---: | ---: | ---: | ---: | ---: | :---: |
| 0 | 20.7% | -19.5% | 35.2% | 62.2% | yes |
| 1 | -7.3% | -27.6% | 38.3% | 66.0% | yes |
| 2 | 111.6% | 60.4% | 20.6% | 37.6% | yes |
| 3 | -15.1% | 7.2% | 33.9% | 42.8% | yes |
| 4 | 7.0% | -18.8% | 34.2% | 59.6% | yes |
