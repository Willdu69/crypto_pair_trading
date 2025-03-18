from collections import deque
from typing import Optional, Dict
import pandas as pd
import numpy as np
from nautilus_trader.core.nautilus_pyo3.model import OrderSide

from statsmodels.tsa.vector_ar.vecm import coint_johansen

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import BarType, Bar, InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.trading import Strategy
from tests.integration_tests.adapters.conftest import account
from tests.integration_tests.adapters.dydx.conftest import instrument_id


class PairTradingStrategyConfig(StrategyConfig, frozen=True):
	"""
	Minimal configuration for a cointegration-based pair trading strategy.
	"""
	instrument_id_1: InstrumentId
	instrument_id_2: InstrumentId
	bar_type: Dict[str, BarType]
	formation_window: int = 200
	zscore_threshold: float = 2.0
	exit_zscore_threshold: float = 0.5
	capital_to_risk_ratio: float = 0.01


class PairTradingStrategy(Strategy):
	"""
	Minimal pair trading strategy using cointegration (Johansen test).
	"""

	def __init__(self, config: PairTradingStrategyConfig):
		super().__init__(config)
		self.instrument1: Optional[Instrument] = None
		self.instrument2: Optional[Instrument] = None

		self.spread = deque(maxlen=config.formation_window)
		self.betas = {config.instrument_id_1: 1.0, config.instrument_id_2: -1.0}
		self.calc_pd = pd.DataFrame(columns=[f'price_{config.instrument_id_1}', f'price_{config.instrument_id_2}',
		                                     f'beta_{config.instrument_id_1}', f'beta_{config.instrument_id_2}',
		                                     'spread', 'z_score'])

	def on_start(self):
		"""Subscribes to market data and requests historical bars."""
		self.instrument1 = self.cache.instrument(self.config.instrument_id_1)
		self.instrument2 = self.cache.instrument(self.config.instrument_id_2)

		for instrument_id, bar_type in self.config.bar_type.items():
			self.subscribe_bars(bar_type)
			self.request_bars(bar_type, limit=self.config.formation_window)

	def on_bar(self, bar: Bar):
		"""Updates spread and betas, then checks for signals."""
		if not self._has_enough_bars():
			return
		self._update_betas()
		self._update_spread()

		if len(self.spread) < self.config.formation_window:
			return

		spread_array = np.array(self.spread)
		mean_spread = np.mean(spread_array)
		std_spread = np.std(spread_array, ddof=1)
		if std_spread == 0:
			return
		z_score = (spread_array[-1] - mean_spread) / std_spread

		if self._has_open_positions():
			if abs(z_score) < self.config.exit_zscore_threshold:
				self._close_all_positions()
		else:
			# Enter if z-score is beyond threshold
			if z_score > self.config.zscore_threshold:
				self.open_positions(OrderSide.SELL)
			elif z_score < -self.config.zscore_threshold:
				self.open_positions(OrderSide.BUY)

		list_to_append = [
			 self.cache.bar(self.config.bar_type[self.config.instrument_id_1]),
			 self.cache.bar(self.config.bar_type[self.config.instrument_id_2]),
			self.betas[self.config.instrument_id_1],
			self.betas[self.config.instrument_id_1],
			spread_array[-1],
			z_score
		]

		self.calc_pd.loc[len(self.calc_pd)] = list_to_append

	def _update_betas(self):
		"""Updates the cointegration hedge ratios using the Johansen test."""
		data = {}
		for instrument_id, bar_type in self.config.bar_type.items():
			bars = self.cache.bars(bar_type)[-self.config.formation_window:]
			data[instrument_id] = [bar.close.as_double() for bar in bars]

		try:
			df_prices = pd.DataFrame(data)
			johansen_res = coint_johansen(df_prices, det_order=0, k_ar_diff=1)
			evec = johansen_res.evec[:, 0]
			last_coeff = evec[-1]
			betas_array = -evec / last_coeff
			for i, instrument_id in enumerate(df_prices.columns):
				self.betas[instrument_id] = betas_array[i]
		except Exception as e:
			self.log.error(f"Failed to update betas: {e}")

	def _update_spread(self):
		"""Updates the spread using current betas and the latest bar prices."""
		spread_value = 0.0
		for instrument_id, bar_type in self.config.bar_type.items():
			latest_bar = self.cache.bar(bar_type, 0)
			if latest_bar is None:
				return
			price = latest_bar.close.as_double()
			spread_value += self.betas.get(instrument_id, 0.0) * price
		self.spread.append(spread_value)

	def get_current_equity(self):
		acc = self.cache.accounts()[0]
		return acc.balance_total().as_double()

	def open_positions(self, orderside: OrderSide):
		"""
		Submits two simple market orders:
		  - One short (SELL) for short_instrument
		  - One long (BUY) for long_instrument
		"""
		long_short_ratio = 1 if orderside == OrderSide.BUY else -1
		current_equity = self.get_current_equity()
		capital_to_risk = self.config.capital_to_risk_ratio * current_equity

		for _instrument_id, bar_type in self.config.bar_type.items():
			beta = self.betas[_instrument_id]
			quantity = (self.cache.bar(bar_type).close.as_double() / (capital_to_risk/2)) * beta * long_short_ratio
			order_side = OrderSide.BUY if beta > 0 else OrderSide.SELL
			self.order_factory.market(_instrument_id, order_side, abs(self.instrument1.maquantity))

	def _close_all_positions(self):
		"""Closes all open positions in the account."""
		for position in self.cache.positions_open():
			self.close_position(position)

	def _has_enough_bars(self) -> bool:
		"""Checks if we have enough bars for both instruments."""
		for bar_type in self.config.bar_type.values():
			if len(self.cache.bars(bar_type)) < self.config.formation_window:
				return False
		return True

	def _has_open_positions(self) -> bool:
		"""Checks if there are any open positions."""
		return len(self.cache.positions_open()) > 0

	def on_stop(self):
		"""Close positions and cancel orders on strategy stop."""
		self.calc_pd.to_csv('report/calc_pd.csv', index=False)
		self._close_all_positions()
