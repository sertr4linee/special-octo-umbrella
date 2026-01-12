"""Technical indicator calculations using pandas-ta."""

import logging
from dataclasses import dataclass

import pandas as pd
import pandas_ta as ta

from btc_bot.config.settings import IndicatorConfig

logger = logging.getLogger(__name__)


@dataclass
class IndicatorValues:
    """Container for all calculated indicator values."""

    # RSI
    rsi: float

    # MACD
    macd_line: float
    macd_signal: float
    macd_histogram: float

    # EMA
    ema_short: float
    ema_long: float

    # Bollinger Bands
    bb_upper: float
    bb_middle: float
    bb_lower: float

    # Price
    current_price: float
    previous_price: float

    @property
    def price_change_pct(self) -> float:
        """Calculate price change percentage from previous candle."""
        if self.previous_price == 0:
            return 0.0
        return ((self.current_price - self.previous_price) / self.previous_price) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "rsi": round(self.rsi, 2),
            "macd_line": round(self.macd_line, 4),
            "macd_signal": round(self.macd_signal, 4),
            "macd_histogram": round(self.macd_histogram, 4),
            "ema_short": round(self.ema_short, 2),
            "ema_long": round(self.ema_long, 2),
            "bb_upper": round(self.bb_upper, 2),
            "bb_middle": round(self.bb_middle, 2),
            "bb_lower": round(self.bb_lower, 2),
            "current_price": round(self.current_price, 2),
            "price_change_pct": round(self.price_change_pct, 2),
        }


class TechnicalIndicators:
    """Calculates technical indicators using pandas-ta library."""

    def __init__(self, config: IndicatorConfig):
        """Initialize with indicator configuration.

        Args:
            config: Configuration for indicator parameters.
        """
        self.config = config

    def calculate_all(self, df: pd.DataFrame) -> IndicatorValues:
        """
        Calculates all technical indicators on OHLCV data.

        Args:
            df: DataFrame with 'open', 'high', 'low', 'close', 'volume' columns.

        Returns:
            IndicatorValues with all calculated indicators.

        Raises:
            ValueError: If DataFrame doesn't have required columns or enough data.
        """
        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"DataFrame must have columns: {required_cols}")

        min_periods = max(
            self.config.macd_slow,
            self.config.bb_period,
            self.config.ema_long,
            self.config.rsi_period,
        )

        if len(df) < min_periods:
            raise ValueError(
                f"Need at least {min_periods} data points, got {len(df)}"
            )

        close = df["close"]

        # Calculate RSI
        rsi = ta.rsi(close, length=self.config.rsi_period)

        # Calculate MACD
        macd = ta.macd(
            close,
            fast=self.config.macd_fast,
            slow=self.config.macd_slow,
            signal=self.config.macd_signal,
        )

        # Calculate EMAs
        ema_short = ta.ema(close, length=self.config.ema_short)
        ema_long = ta.ema(close, length=self.config.ema_long)

        # Calculate Bollinger Bands
        bbands = ta.bbands(
            close,
            length=self.config.bb_period,
            std=self.config.bb_std_dev,
        )

        # Get latest values (handle NaN for early periods)
        latest_rsi = self._safe_get_latest(rsi, 50.0)  # Default to neutral
        latest_ema_short = self._safe_get_latest(ema_short, close.iloc[-1])
        latest_ema_long = self._safe_get_latest(ema_long, close.iloc[-1])

        # MACD columns: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        macd_cols = macd.columns.tolist()
        macd_line = self._safe_get_latest(macd[macd_cols[0]], 0.0)
        macd_histogram = self._safe_get_latest(macd[macd_cols[1]], 0.0)
        macd_signal = self._safe_get_latest(macd[macd_cols[2]], 0.0)

        # Bollinger Bands columns: BBL, BBM, BBU, BBB, BBP
        bb_cols = bbands.columns.tolist()
        bb_lower = self._safe_get_latest(bbands[bb_cols[0]], close.iloc[-1] * 0.95)
        bb_middle = self._safe_get_latest(bbands[bb_cols[1]], close.iloc[-1])
        bb_upper = self._safe_get_latest(bbands[bb_cols[2]], close.iloc[-1] * 1.05)

        indicators = IndicatorValues(
            rsi=latest_rsi,
            macd_line=macd_line,
            macd_signal=macd_signal,
            macd_histogram=macd_histogram,
            ema_short=latest_ema_short,
            ema_long=latest_ema_long,
            bb_upper=bb_upper,
            bb_middle=bb_middle,
            bb_lower=bb_lower,
            current_price=close.iloc[-1],
            previous_price=close.iloc[-2] if len(close) > 1 else close.iloc[-1],
        )

        logger.debug(f"Indicators calculated: {indicators.to_dict()}")
        return indicators

    def _safe_get_latest(self, series: pd.Series, default: float) -> float:
        """Safely get the latest non-NaN value from a series."""
        if series is None or series.empty:
            return default

        latest = series.iloc[-1]
        if pd.isna(latest):
            # Try to find last valid value
            valid = series.dropna()
            if valid.empty:
                return default
            return float(valid.iloc[-1])

        return float(latest)

    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """Calculate RSI indicator only.

        Args:
            df: DataFrame with 'close' column.

        Returns:
            RSI series.
        """
        return ta.rsi(df["close"], length=self.config.rsi_period)

    def calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate MACD indicator only.

        Args:
            df: DataFrame with 'close' column.

        Returns:
            DataFrame with MACD, signal, and histogram.
        """
        return ta.macd(
            df["close"],
            fast=self.config.macd_fast,
            slow=self.config.macd_slow,
            signal=self.config.macd_signal,
        )

    def calculate_bollinger(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Bollinger Bands only.

        Args:
            df: DataFrame with 'close' column.

        Returns:
            DataFrame with upper, middle, lower bands.
        """
        return ta.bbands(
            df["close"],
            length=self.config.bb_period,
            std=self.config.bb_std_dev,
        )
