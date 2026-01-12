"""Binance API client for fetching Bitcoin price data."""

import logging
from datetime import datetime, timedelta

import pandas as pd
from binance.client import Client

from btc_bot.config.constants import DEFAULT_LOOKBACK_PERIODS, KLINE_INTERVAL_15M
from btc_bot.config.settings import BinanceConfig

logger = logging.getLogger(__name__)


class BinanceDataFetcher:
    """
    Fetches Bitcoin price data from Binance.
    No API key required for public market data.
    """

    def __init__(self, config: BinanceConfig):
        """Initialize the Binance client.

        Args:
            config: Binance configuration with symbol and base URL.
        """
        self.config = config
        # No API key needed for public data
        self.client = Client()
        logger.info(f"Binance client initialized for {config.symbol}")

    def get_historical_klines(
        self,
        interval: str = KLINE_INTERVAL_15M,
        lookback_periods: int = DEFAULT_LOOKBACK_PERIODS,
    ) -> pd.DataFrame:
        """
        Fetches historical candlestick (OHLCV) data.

        Args:
            interval: Kline interval (default 15m to match trading interval).
            lookback_periods: Number of candles to fetch.

        Returns:
            DataFrame with columns: open, high, low, close, volume.
        """
        # Calculate start time based on interval
        interval_minutes = self._interval_to_minutes(interval)
        start_time = datetime.utcnow() - timedelta(minutes=interval_minutes * lookback_periods)
        start_str = start_time.strftime("%d %b %Y %H:%M:%S")

        logger.debug(f"Fetching {lookback_periods} klines for {self.config.symbol} @ {interval}")

        klines = self.client.get_historical_klines(
            symbol=self.config.symbol,
            interval=interval,
            start_str=start_str,
        )

        if not klines:
            raise ValueError(f"No kline data returned for {self.config.symbol}")

        df = pd.DataFrame(
            klines,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )

        # Convert numeric columns
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        # Convert timestamps
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        df.set_index("open_time", inplace=True)

        # Return only OHLCV columns
        result = df[["open", "high", "low", "close", "volume"]].copy()
        logger.info(f"Fetched {len(result)} klines, latest close: ${result['close'].iloc[-1]:,.2f}")

        return result

    def get_current_price(self) -> float:
        """Gets the current BTC spot price.

        Returns:
            Current price as float.
        """
        ticker = self.client.get_symbol_ticker(symbol=self.config.symbol)
        price = float(ticker["price"])
        logger.debug(f"Current {self.config.symbol} price: ${price:,.2f}")
        return price

    def get_24h_stats(self) -> dict:
        """Gets 24-hour price statistics.

        Returns:
            Dict with price change, high, low, volume stats.
        """
        stats = self.client.get_ticker(symbol=self.config.symbol)
        return {
            "price_change_pct": float(stats["priceChangePercent"]),
            "high_24h": float(stats["highPrice"]),
            "low_24h": float(stats["lowPrice"]),
            "volume_24h": float(stats["volume"]),
            "last_price": float(stats["lastPrice"]),
        }

    def _interval_to_minutes(self, interval: str) -> int:
        """Convert interval string to minutes."""
        multipliers = {"m": 1, "h": 60, "d": 1440, "w": 10080}
        unit = interval[-1]
        value = int(interval[:-1])
        return value * multipliers.get(unit, 1)
