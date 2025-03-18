# crypto_pair_trading

## Overview

This repository contains a Python-based implementation of a statistical arbitrage strategy focused on cryptocurrency pairs. The core objective is to exploit temporary deviations from the historical correlation between two cryptocurrencies. This is achieved by identifying cointegrated pairs, calculating a spread, and then generating trading signals when the spread deviates significantly from its historical mean.

## Methodology

The strategy employs the following key steps:

1.  **Cointegration Analysis:** Statistical tests are used to identify pairs of cryptocurrencies that exhibit cointegration, indicating a long-term equilibrium relationship. This step is crucial for ensuring that the spread between the pair is mean-reverting.
2.  **Spread Calculation:** Once a cointegrated pair is identified, the spread is calculated as a linear combination of the prices of the two cryptocurrencies. The coefficients of this linear combination are determined based on the cointegration relationship.
3.  **Trading Signal Generation:** Trading signals are generated based on the deviation of the spread from its historical mean. A threshold-based approach is used, where buy and sell signals are triggered when the spread deviates by a certain number of standard deviations.
4.  **Backtesting and Performance Evaluation:** The strategy's performance is evaluated through backtesting using historical cryptocurrency price data. Key performance metrics, such as total return, Sharpe ratio, and maximum drawdown, are calculated to assess the strategy's effectiveness.

## Implementation Details

The implementation leverages Python and several key libraries:

* **Pandas:** For data manipulation and analysis.
* **NumPy:** For numerical computations.
* **Statsmodels:** For statistical modeling, including cointegration tests.

The repository includes scripts for:

* Running backtests of the pair trading strategy (`run_backtest.py`).
* Executing the core pair trading logic (`strategies/pair_trading.py`).
* Generating reports on account,orders, positions, etc.

## Results

Backtesting results, included in the `report` directory, demonstrate the potential profitability of the proposed pair trading strategy. The strategy exhibits positive returns and a favorable risk-adjusted performance as evidenced by the Sharpe ratio. Detailed reports provide insights into the strategy's performance, including order execution, position management, and overall account valuation.
