from decimal import Decimal
import datetime as dt
import pandas as pd
import time
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.config import LoggingConfig, RiskEngineConfig
from nautilus_trader.model import InstrumentId, Venue, Symbol
from nautilus_trader.model import BarType
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.currencies import USD, BTC, ETH
from nautilus_trader.model import Price, Quantity, Money
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.model.enums import AccountType, OmsType, BarAggregation, PriceType
from nautilus_trader.model.data import Bar
from nautilus_trader.analysis.reporter import ReportProvider

from strategies.pair_trading import PairTradingStrategy, PairTradingStrategyConfig

# Initialize backtest engine configuration
engine_config = BacktestEngineConfig(
	trader_id="BACKTESTER-001",
	logging=LoggingConfig(log_level="INFO"),
	risk_engine=RiskEngineConfig(bypass=True),
)

# Build backtest engine
engine = BacktestEngine(config=engine_config)

# Define the instrument
venue = Venue("BINANCE")
instrument_id_btc = InstrumentId(symbol=Symbol("BTC/USD"), venue=venue)
instrument_id_eth = InstrumentId(symbol=Symbol("ETH/USD"), venue=venue)

# Get current timestamp in nanoseconds
current_ns = int(time.time() * 1e9)

# Create CryptoInstrument
btc_usd_instrument = CurrencyPair(
	instrument_id=instrument_id_btc,
	raw_symbol=Symbol("BTCUSD"),
	base_currency=BTC,
	quote_currency=USD,
	price_precision=6,  # USD cents precision
	size_precision=6,  # BTC satoshi precision
	price_increment=Price.from_str("0.000001"),
	size_increment=Quantity.from_str("0.000001"),
	ts_event=current_ns,
	ts_init=current_ns,
)

eth_usd_instrument = CurrencyPair(
	instrument_id=instrument_id_eth,
	raw_symbol=Symbol("ETHUSD"),
	base_currency=ETH,
	quote_currency=USD,
	price_precision=6,  # USD cents precision
	size_precision=6,  # BTC satoshi precision
	price_increment=Price.from_str("0.000001"),
	size_increment=Quantity.from_str("0.000001"),
	ts_event=current_ns,
	ts_init=current_ns,
)

fill_model = FillModel(
	prob_fill_on_limit=0.2,
	prob_fill_on_stop=0.95,
	prob_slippage=0.5,
	random_seed=42,
)

# Add venue and instrument
engine.add_venue(
	venue=venue,
	oms_type=OmsType.NETTING,
	account_type=AccountType.MARGIN,
	base_currency=USD,
	starting_balances=[Money(100000, USD)],
	fill_model=fill_model,
	# fee_model=BinanceFeeModel(), marche pas mdr jsp pq
)

engine.add_instrument(btc_usd_instrument)
engine.add_instrument(eth_usd_instrument)


# Load OHLC data from CSV
def load_ohlc_from_csv(file_path: str, instrument_id, instrument) -> list[Bar]:
	df = pd.read_csv(file_path, parse_dates=['timestamp'], index_col=['timestamp'])

	# Convert numeric columns
	price_cols = ['open', 'high', 'low', 'close']
	df[price_cols] = df[price_cols].apply(pd.to_numeric, errors='coerce')

	# Clean price relationships
	df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)
	df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
	df['open'] = df[['open', 'close']].mean(axis=1)  # For open=nan cases

	# Drop invalid rows
	df = df.dropna(subset=price_cols)

	# Create bar type for 1-minute intervals
	bar_type = BarType.from_str(f"{instrument_id}-1-MINUTE-LAST-EXTERNAL")

	# Create data wrangler
	wrangler = BarDataWrangler(
		bar_type=bar_type,
		instrument=instrument,
	)

	# Process dataframe into bars
	return wrangler.process(
		data=df,
		# default_volume=1_000_000.0,  # Default volume if missing
		ts_init_delta=0,
	)


# Load and add data
ohlc_bars_btc = load_ohlc_from_csv("data/usdcusdt_ohlcv.csv", instrument_id_btc, btc_usd_instrument)
ohlc_bars_eth = load_ohlc_from_csv("data/usdpusdt_ohlcv.csv", instrument_id_eth, eth_usd_instrument)
engine.add_data(ohlc_bars_btc)
engine.add_data(ohlc_bars_eth)

# Configure and add strategy
strategy_config = PairTradingStrategyConfig(
	instrument_id_1=instrument_id_btc,
	instrument_id_2=instrument_id_eth,
	bar_type={
		instrument_id_btc: BarType.from_str(f"{instrument_id_btc}-1-MINUTE-LAST-EXTERNAL"),
		instrument_id_eth: BarType.from_str(f"{instrument_id_eth}-1-MINUTE-LAST-EXTERNAL")
	},
	zscore_threshold=1.5,
)

strategy = PairTradingStrategy(config=strategy_config)
engine.add_strategy(strategy)

# Run the backtest
engine.run(start=dt.datetime(2024, 1, 2), end= dt.datetime(2024, 2, 20))

# Generate reports
orders_fills_report = engine.trader.generate_order_fills_report()
positions_report = engine.trader.generate_positions_report()
account_report = engine.trader.generate_account_report(venue=Venue("BINANCE"))

# Print reports
print("\n" + "-" * 100)
print("Orders/Fills Report:")
print(orders_fills_report)
orders_fills_report.to_csv('report/orders_fills_report.csv')

print("\n" + "-" * 100)
print("Positions Report:")
print(positions_report)
positions_report.to_csv('report/positions_report.csv')

print("\n" + "-" * 100)
print("Account Report:")
print(account_report)
account_report.to_csv('report/account_report.csv')

engine.dispose()
