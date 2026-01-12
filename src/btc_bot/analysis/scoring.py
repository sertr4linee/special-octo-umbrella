"""Multi-indicator scoring system for trading signals."""

import logging
from dataclasses import dataclass
from enum import Enum

from btc_bot.analysis.indicators import IndicatorValues
from btc_bot.config.constants import INDICATOR_WEIGHTS, Signal
from btc_bot.config.settings import IndicatorConfig

logger = logging.getLogger(__name__)


class Direction(str, Enum):
    """Trading direction prediction."""

    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


@dataclass
class SignalScore:
    """Trading signal with direction, confidence, and analysis."""

    direction: Direction
    confidence: float  # 0.0 to 1.0
    raw_score: float  # -1.0 to 1.0
    indicator_signals: dict[str, int]  # Individual indicator signals
    reasoning: str

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "direction": self.direction.value,
            "confidence": round(self.confidence, 3),
            "raw_score": round(self.raw_score, 3),
            "signals": self.indicator_signals,
            "reasoning": self.reasoning,
        }


class MultiIndicatorScorer:
    """
    Combines multiple technical indicators into a single trading signal.
    Uses weighted scoring system for robust predictions.

    Scoring:
    - Each indicator produces a signal: -2 (strong sell) to +2 (strong buy)
    - Signals are weighted and combined
    - Final score determines direction and confidence
    """

    def __init__(
        self,
        config: IndicatorConfig,
        weights: dict[str, float] | None = None,
    ):
        """Initialize scorer with configuration.

        Args:
            config: Indicator configuration for thresholds.
            weights: Custom weights for indicators (must sum to 1.0).
        """
        self.config = config
        self.weights = weights or INDICATOR_WEIGHTS

        # Validate weights sum to 1.0
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            logger.warning(f"Indicator weights sum to {weight_sum}, normalizing...")
            self.weights = {k: v / weight_sum for k, v in self.weights.items()}

    def calculate_signal(self, indicators: IndicatorValues) -> SignalScore:
        """
        Generates a trading signal based on all indicators.

        Args:
            indicators: Calculated indicator values.

        Returns:
            SignalScore with direction, confidence, and reasoning.
        """
        signals = {}
        reasoning_parts = []

        # RSI Signal
        rsi_signal = self._score_rsi(indicators.rsi)
        signals["rsi"] = rsi_signal
        reasoning_parts.append(
            f"RSI({indicators.rsi:.1f}): {self._signal_name(rsi_signal)}"
        )

        # MACD Signal
        macd_signal = self._score_macd(
            indicators.macd_line,
            indicators.macd_signal,
            indicators.macd_histogram,
        )
        signals["macd"] = macd_signal
        reasoning_parts.append(f"MACD: {self._signal_name(macd_signal)}")

        # EMA Crossover Signal
        ema_signal = self._score_ema_crossover(
            indicators.ema_short,
            indicators.ema_long,
            indicators.current_price,
        )
        signals["ema_crossover"] = ema_signal
        reasoning_parts.append(f"EMA: {self._signal_name(ema_signal)}")

        # Bollinger Bands Signal
        bb_signal = self._score_bollinger(
            indicators.current_price,
            indicators.bb_upper,
            indicators.bb_middle,
            indicators.bb_lower,
        )
        signals["bollinger"] = bb_signal
        reasoning_parts.append(f"BB: {self._signal_name(bb_signal)}")

        # Calculate weighted score
        weighted_score = sum(
            signals[ind] * self.weights[ind] for ind in signals
        )

        # Normalize to -1 to 1 range (max possible is ±2 * weight_sum = ±2)
        normalized_score = weighted_score / 2.0

        # Determine direction and confidence
        # Threshold of 0.1 to avoid trading on weak signals
        if normalized_score > 0.1:
            direction = Direction.UP
            confidence = min(abs(normalized_score), 1.0)
        elif normalized_score < -0.1:
            direction = Direction.DOWN
            confidence = min(abs(normalized_score), 1.0)
        else:
            direction = Direction.NEUTRAL
            confidence = 0.0

        signal_score = SignalScore(
            direction=direction,
            confidence=confidence,
            raw_score=normalized_score,
            indicator_signals=signals,
            reasoning=" | ".join(reasoning_parts),
        )

        logger.info(f"Signal calculated: {signal_score.to_dict()}")
        return signal_score

    def _score_rsi(self, rsi: float) -> int:
        """
        RSI scoring: oversold = bullish, overbought = bearish.

        Logic:
        - RSI < 30: Oversold, expect bounce up (STRONG_BUY)
        - RSI 30-40: Approaching oversold (BUY)
        - RSI 60-70: Approaching overbought (SELL)
        - RSI > 70: Overbought, expect drop (STRONG_SELL)
        """
        if rsi < self.config.rsi_oversold:
            return Signal.STRONG_BUY
        elif rsi < 40:
            return Signal.BUY
        elif rsi > self.config.rsi_overbought:
            return Signal.STRONG_SELL
        elif rsi > 60:
            return Signal.SELL
        return Signal.NEUTRAL

    def _score_macd(
        self,
        macd_line: float,
        signal_line: float,
        histogram: float,
    ) -> int:
        """
        MACD scoring: crossovers and histogram direction.

        Logic:
        - MACD above signal = bullish crossover
        - Histogram positive and increasing = strong momentum
        """
        score = 0

        # MACD line vs Signal line
        if macd_line > signal_line:
            score += 1  # Bullish
        elif macd_line < signal_line:
            score -= 1  # Bearish

        # Histogram direction (momentum)
        if histogram > 0:
            score += 1  # Positive momentum
        elif histogram < 0:
            score -= 1  # Negative momentum

        return max(Signal.STRONG_SELL, min(Signal.STRONG_BUY, score))

    def _score_ema_crossover(
        self,
        ema_short: float,
        ema_long: float,
        current_price: float,
    ) -> int:
        """
        EMA crossover scoring: short above long = bullish.

        Logic:
        - Short EMA > Long EMA = uptrend
        - Price above both EMAs = strong uptrend
        - Price below both EMAs = strong downtrend
        """
        score = 0

        # Short vs Long EMA (Golden Cross / Death Cross)
        if ema_short > ema_long:
            score += 1  # Bullish crossover
        elif ema_short < ema_long:
            score -= 1  # Bearish crossover

        # Price position relative to EMAs
        if current_price > ema_short > ema_long:
            score += 1  # Strong uptrend
        elif current_price < ema_short < ema_long:
            score -= 1  # Strong downtrend

        return max(Signal.STRONG_SELL, min(Signal.STRONG_BUY, score))

    def _score_bollinger(
        self,
        price: float,
        upper: float,
        middle: float,
        lower: float,
    ) -> int:
        """
        Bollinger Bands scoring: mean reversion signals.

        Logic:
        - Price below lower band = oversold, expect bounce (BUY)
        - Price above upper band = overbought, expect drop (SELL)
        - Price near middle = neutral
        """
        # Calculate position as percentage of band width
        band_width = upper - lower
        if band_width == 0:
            return Signal.NEUTRAL

        position = (price - lower) / band_width

        if price < lower:
            return Signal.STRONG_BUY  # Below lower band - oversold
        elif position < 0.3:
            return Signal.BUY  # Near lower band
        elif price > upper:
            return Signal.STRONG_SELL  # Above upper band - overbought
        elif position > 0.7:
            return Signal.SELL  # Near upper band
        return Signal.NEUTRAL

    def _signal_name(self, signal: int) -> str:
        """Convert signal integer to readable name."""
        names = {
            Signal.STRONG_BUY: "STRONG_BUY",
            Signal.BUY: "BUY",
            Signal.NEUTRAL: "NEUTRAL",
            Signal.SELL: "SELL",
            Signal.STRONG_SELL: "STRONG_SELL",
        }
        return names.get(signal, "UNKNOWN")
