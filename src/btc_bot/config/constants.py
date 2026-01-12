"""Application constants and default values."""

from enum import IntEnum


class Signal(IntEnum):
    """Trading signal strength levels."""

    STRONG_SELL = -2
    SELL = -1
    NEUTRAL = 0
    BUY = 1
    STRONG_BUY = 2


# Indicator weights for multi-indicator scoring system
# Must sum to 1.0
INDICATOR_WEIGHTS = {
    "rsi": 0.25,
    "macd": 0.30,
    "ema_crossover": 0.25,
    "bollinger": 0.20,
}

# Polymarket Bitcoin market filters
BTC_MARKET_TAGS = ["Bitcoin", "BTC", "Crypto", "Cryptocurrency"]
BTC_MARKET_KEYWORDS = ["bitcoin", "btc", "price"]

# Price direction keywords for market filtering
DIRECTION_KEYWORDS = {
    "up": ["above", "over", "reach", "hit", "exceed", "higher"],
    "down": ["below", "under", "drop", "fall", "lower"],
}

# Binance kline intervals
KLINE_INTERVAL_15M = "15m"
KLINE_INTERVAL_1H = "1h"
KLINE_INTERVAL_4H = "4h"

# Default lookback periods for indicator calculation
DEFAULT_LOOKBACK_PERIODS = 100

# Rate limiting
POLYMARKET_RATE_LIMIT_ORDERS_PER_MIN = 60
BINANCE_RATE_LIMIT_REQUESTS_PER_MIN = 1200

# Paper trading defaults
PAPER_TRADING_INITIAL_BALANCE = 1000.0

# Logging format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
