"""Tests for technical indicator calculations."""

import pandas as pd
import pytest

from btc_bot.analysis.indicators import IndicatorValues, TechnicalIndicators
from btc_bot.config.settings import IndicatorConfig


class TestTechnicalIndicators:
    """Test suite for TechnicalIndicators class."""

    def test_calculate_all_returns_indicator_values(
        self, sample_ohlcv_data: pd.DataFrame, indicator_config: IndicatorConfig
    ):
        """Test that calculate_all returns valid IndicatorValues."""
        indicators = TechnicalIndicators(indicator_config)
        result = indicators.calculate_all(sample_ohlcv_data)

        assert isinstance(result, IndicatorValues)
        assert 0 <= result.rsi <= 100
        assert result.current_price > 0
        assert result.ema_short > 0
        assert result.ema_long > 0
        assert result.bb_lower < result.bb_middle < result.bb_upper

    def test_calculate_all_with_insufficient_data(self, indicator_config: IndicatorConfig):
        """Test that calculate_all raises error with insufficient data."""
        indicators = TechnicalIndicators(indicator_config)

        # Create DataFrame with too few rows
        df = pd.DataFrame({
            "open": [100],
            "high": [101],
            "low": [99],
            "close": [100.5],
            "volume": [1000],
        })

        with pytest.raises(ValueError, match="Need at least"):
            indicators.calculate_all(df)

    def test_calculate_all_missing_columns(self, indicator_config: IndicatorConfig):
        """Test that calculate_all raises error with missing columns."""
        indicators = TechnicalIndicators(indicator_config)

        df = pd.DataFrame({
            "close": [100] * 50,
            # Missing open, high, low, volume
        })

        with pytest.raises(ValueError, match="must have columns"):
            indicators.calculate_all(df)

    def test_indicator_values_to_dict(self):
        """Test IndicatorValues to_dict conversion."""
        values = IndicatorValues(
            rsi=45.5,
            macd_line=100.0,
            macd_signal=95.0,
            macd_histogram=5.0,
            ema_short=45000.0,
            ema_long=44500.0,
            bb_upper=46000.0,
            bb_middle=45000.0,
            bb_lower=44000.0,
            current_price=45100.0,
            previous_price=45000.0,
        )

        result = values.to_dict()

        assert isinstance(result, dict)
        assert result["rsi"] == 45.5
        assert "price_change_pct" in result

    def test_price_change_percentage(self):
        """Test price change percentage calculation."""
        values = IndicatorValues(
            rsi=50,
            macd_line=0,
            macd_signal=0,
            macd_histogram=0,
            ema_short=100,
            ema_long=100,
            bb_upper=110,
            bb_middle=100,
            bb_lower=90,
            current_price=105,
            previous_price=100,
        )

        assert values.price_change_pct == 5.0  # 5% increase
