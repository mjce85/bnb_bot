# Portfolio summary

The locked entry **vol_targeted_regime_momentum** traded across 4 tokens on one shared book (2021-01-01 → 2026-06-01, 1d), vs an equal-weight buy-and-hold portfolio. Total-exposure cap 100.0%; risk-on. Metrics are equity-curve based (return, drawdown, Sharpe, Sortino, Calmar).

## Full window

| | Return | MaxDD | Sharpe | Sortino | Calmar |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Portfolio strategy** | 84.5% | 56.9% | 0.50 | 0.73 | 0.22 |
| Equal-weight buy & hold | 8.2% | 79.7% | 0.37 | 0.51 | 0.02 |

## Capital utilization & correlation (honest)

Portfolio max drawdown **56.9%** is *higher* than the average single-token strategy drawdown **30.8%** (per-token: 22.8%, 31.3%, 31.9%, 37.3%) — not lower. Two honest reasons: these tokens are highly correlated (they fall together, so combining them diversifies little), and the portfolio deploys the cash that single-token runs leave idle. That fuller deployment is exactly why portfolio *return* is far higher than equal-weight holding. The benefit here is **capital efficiency vs holding**, not drawdown reduction vs a single token. Decorrelated assets would smooth the curve (see `test_diversification_reduces_drawdown`); this token set isn't decorrelated.

## Walk-forward (5 independent folds) vs equal-weight hold

Drawdown beaten in **5/5** folds.

| Fold | Return | Hold | MaxDD | Hold MaxDD | DD beaten |
| ---: | ---: | ---: | ---: | ---: | :---: |
| 0 | 22.8% | -19.5% | 35.0% | 62.2% | yes |
| 1 | -6.6% | -27.6% | 39.3% | 66.0% | yes |
| 2 | 117.2% | 60.4% | 21.4% | 37.6% | yes |
| 3 | -9.2% | 7.2% | 28.5% | 42.8% | yes |
| 4 | 9.0% | -18.8% | 31.7% | 59.6% | yes |
