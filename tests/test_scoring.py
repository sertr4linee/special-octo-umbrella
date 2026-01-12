"""Tests for the multi-indicator scoring system."""

import pytest

from btc_bot.analysis.indicators import IndicatorValues
from btc_bot.analysis.scoring import Direction, MultiIndicatorScorer, SignalScore
from btc_bot.config.constants import INDICATOR_WEIGHTS
from btc_bot.config.settings import IndicatorConfig


class TestMultiIndicatorScorer:
    """Test suite for MultiIndicatorScorer class."""

    @pytest.fixture
    def scorer(self, indicator_config: IndicatorConfig) -> MultiIndicatorScorer:
        """Create scorer instance for testing."""
        return MultiIndicatorScorer(indicator_config, INDICATOR_WEIGHTS)

    def test_bullish_signal(self, scorer: MultiIndicatorScorer):
        """Test that oversold conditions produce bullish signal."""
        indicators = IndicatorValues(
            rsi=25.0,  # Oversold
            macd_line=100.0,
            macd_signal=80.0,  # MACD above signal
            macd_histogram=20.0,  # Positive histogram
            ema_short=45000.0,
            ema_long=44500.0,  # Short above long (bullish)
            bb_upper=46000.0,
            bb_middle=45000.0,
            bb_lower=44000.0,
            current_price=43500.0,  # Below lower band (oversold)
            previous_price=43600.0,
        )

        signal = scorer.calculate_signal(indicators)

        assert signal.direction == Direction.UP
        assert signal.confidence > 0.5

    def test_bearish_signal(self, scorer: MultiIndicatorScorer):
        """Test that overbought conditions produce bearish signal."""
        indicators = IndicatorValues(
            rsi=80.0,  # Overbought
            macd_line=80.0,
            macd_signal=100.0,  # MACD below signal
            macd_histogram=-20.0,  # Negative histogram
            ema_short=44500.0,
            ema_long=45000.0,  # Short below long (bearish)
            bb_upper=46000.0,
            bb_middle=45000.0,
            bb_lower=44000.0,
            current_price=47000.0,  # Above upper band (overbought)
            previous_price=46800.0,
        )

        signal = scorer.calculate_signal(indicators)

        assert signal.direction == Direction.DOWN
        assert signal.confidence > 0.5

    def test_neutral_signal(self, scorer: MultiIndicatorScorer):
        """Test that mixed conditions produce neutral signal."""
        indicators = IndicatorValues(
            rsi=50.0,  # Neutral
            macd_line=100.0,
            macd_signal=100.0,  # Equal (neutral)
            macd_histogram=0.0,
            ema_short=45000.0,
            ema_long=45000.0,  # Equal (neutral)
            bb_upper=46000.0,
            bb_middle=45000.0,
            bb_lower=44000.0,
            current_price=45000.0,  # At middle (neutral)
            previous_price=45000.0,
        )

        signal = scorer.calculate_signal(indicators)

        # Should be close to neutral or low confidence
        assert signal.confidence < 0.3 or signal.direction == Direction.NEUTRAL

    def test_signal_score_to_dict(self, scorer: MultiIndicatorScorer):
        """Test SignalScore to_dict conversion."""
        indicators = IndicatorValues(
            rsi=50.0,
            macd_line=100.0,
            macd_signal=100.0,
            macd_histogram=0.0,
            ema_short=45000.0,
            ema_long=45000.0,
            bb_upper=46000.0,
            bb_middle=45000.0,
            bb_lower=44000.0,
            current_price=45000.0,
            previous_price=45000.0,
        )

        signal = scorer.calculate_signal(indicators)
        result = signal.to_dict()

        assert isinstance(result, dict)
        assert "direction" in result
        assert "confidence" in result
        assert "signals" in result
        assert "reasoning" in result

    def test_custom_weights(self, indicator_config: IndicatorConfig):
        """Test scorer with custom weights."""
        custom_weights = {
            "rsi": 0.5,  # Heavy RSI weight
            "macd": 0.2,
            "ema_crossover": 0.2,
            "bollinger": 0.1,
        }

        scorer = MultiIndicatorScorer(indicator_config, custom_weights)

        # RSI oversold should have strong impact
        indicators = IndicatorValues(
            rsi=20.0,  # Very oversold
            macd_line=80.0,
            macd_signal=100.0,  # Bearish MACD
            macd_histogram=-20.0,
            ema_short=44500.0,
            ema_long=45000.0,  # Bearish EMA
            bb_upper=46000.0,
            bb_middle=45000.0,
            bb_lower=44000.0,
            current_price=45500.0,  # Neutral BB
            previous_price=45400.0,
        )

        signal = scorer.calculate_signal(indicators)

        # Should still be bullish due to heavy RSI weight
        assert signal.direction == Direction.UP
