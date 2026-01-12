"""Trade execution logic for both paper and live trading."""

import logging
from typing import Optional

from btc_bot.analysis.scoring import Direction, SignalScore
from btc_bot.api.polymarket.client import PolymarketClient
from btc_bot.api.polymarket.markets import BitcoinMarket
from btc_bot.config.settings import TradingConfig, TradingMode
from btc_bot.trading.paper_trader import PaperTrader

logger = logging.getLogger(__name__)


class TradeExecutor:
    """
    Executes trades on Polymarket (paper or live).
    Handles order placement, confirmation, and error handling.
    """

    def __init__(
        self,
        polymarket_client: PolymarketClient,
        paper_trader: Optional[PaperTrader],
        config: TradingConfig,
    ):
        """Initialize trade executor.

        Args:
            polymarket_client: Client for Polymarket API.
            paper_trader: Paper trader instance (required for paper mode).
            config: Trading configuration.
        """
        self.client = polymarket_client
        self.paper_trader = paper_trader
        self.config = config
        self._daily_trades = 0

    def execute(
        self,
        market: BitcoinMarket,
        signal: SignalScore,
        btc_price: float,
    ) -> dict:
        """
        Executes a trade based on the signal.

        Args:
            market: The Bitcoin market to trade on.
            signal: The trading signal with direction and confidence.
            btc_price: Current BTC price for reference.

        Returns:
            Dict with execution status and details.
        """
        # Check for neutral signal
        if signal.direction == Direction.NEUTRAL:
            logger.info("Signal is NEUTRAL - skipping trade")
            return {
                "status": "SKIPPED",
                "reason": "neutral_signal",
                "signal": signal.to_dict(),
            }

        # Check confidence threshold
        if signal.confidence < self.config.min_score_threshold:
            logger.info(
                f"Confidence {signal.confidence:.2f} below threshold "
                f"{self.config.min_score_threshold} - skipping trade"
            )
            return {
                "status": "SKIPPED",
                "reason": "low_confidence",
                "confidence": signal.confidence,
                "threshold": self.config.min_score_threshold,
            }

        # Check daily trade limit
        if self._daily_trades >= self.config.max_daily_trades:
            logger.warning(
                f"Daily trade limit reached ({self.config.max_daily_trades})"
            )
            return {
                "status": "SKIPPED",
                "reason": "daily_limit_reached",
                "daily_trades": self._daily_trades,
            }

        # Determine which token to buy based on direction
        if signal.direction == Direction.UP:
            token_id = market.yes_token_id
            outcome = "YES"
            price = market.current_yes_price
        else:
            token_id = market.no_token_id
            outcome = "NO"
            price = market.current_no_price

        amount = self.config.trade_amount_usd

        # Log trade intent
        logger.info(
            f"\n{'='*60}\n"
            f"EXECUTING TRADE\n"
            f"{'='*60}\n"
            f"Market: {market.question}\n"
            f"Direction: {outcome} (predicting {signal.direction.value})\n"
            f"Amount: ${amount:.2f}\n"
            f"Token Price: {price:.4f}\n"
            f"Confidence: {signal.confidence:.2%}\n"
            f"Analysis: {signal.reasoning}\n"
            f"BTC Price: ${btc_price:,.2f}\n"
            f"Mode: {self.config.mode.value.upper()}\n"
            f"{'='*60}"
        )

        # Execute based on mode
        if self.config.mode == TradingMode.PAPER:
            result = self._execute_paper(
                market, signal, token_id, outcome, price, amount, btc_price
            )
        else:
            result = self._execute_live(market, token_id, outcome, amount)

        # Increment daily trade counter
        if result.get("status") == "EXECUTED":
            self._daily_trades += 1

        return result

    def _execute_paper(
        self,
        market: BitcoinMarket,
        signal: SignalScore,
        token_id: str,
        outcome: str,
        price: float,
        amount: float,
        btc_price: float,
    ) -> dict:
        """Execute paper trade."""
        if not self.paper_trader:
            raise ValueError("Paper trader not initialized for paper mode")

        try:
            trade = self.paper_trader.execute_trade(
                market_question=market.question,
                direction=signal.direction,
                amount=amount,
                current_price=price,
                token_id=token_id,
                btc_price=btc_price,
            )

            return {
                "status": "EXECUTED",
                "mode": "PAPER",
                "trade_id": trade.id,
                "outcome": outcome,
                "amount": amount,
                "price": price,
                "direction": signal.direction.value,
                "confidence": signal.confidence,
            }

        except ValueError as e:
            logger.error(f"Paper trade failed: {e}")
            return {
                "status": "FAILED",
                "mode": "PAPER",
                "error": str(e),
            }

    def _execute_live(
        self,
        market: BitcoinMarket,
        token_id: str,
        outcome: str,
        amount: float,
    ) -> dict:
        """Execute live trade on Polymarket."""
        try:
            response = self.client.place_market_order(
                token_id=token_id,
                amount=amount,
                side=outcome,
            )

            logger.info(f"Live order response: {response}")

            return {
                "status": "EXECUTED",
                "mode": "LIVE",
                "response": response,
                "outcome": outcome,
                "amount": amount,
                "token_id": token_id,
            }

        except Exception as e:
            logger.error(f"Live trade execution failed: {e}", exc_info=True)
            return {
                "status": "FAILED",
                "mode": "LIVE",
                "error": str(e),
            }

    def reset_daily_counter(self):
        """Reset daily trade counter (call at midnight)."""
        logger.info(f"Resetting daily trade counter (was {self._daily_trades})")
        self._daily_trades = 0

    def get_daily_trades(self) -> int:
        """Get current daily trade count."""
        return self._daily_trades


def select_best_market(markets: list[BitcoinMarket]) -> Optional[BitcoinMarket]:
    """
    Selects the best market to trade based on liquidity and timing.

    Selection criteria (in order):
    1. Sufficient liquidity (spread < 10%)
    2. Reasonable time to resolution
    3. Highest volume

    Args:
        markets: List of Bitcoin markets.

    Returns:
        Best market to trade, or None if no suitable market.
    """
    if not markets:
        return None

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    scored_markets = []
    for market in markets:
        score = 0

        # Liquidity score (lower spread = better)
        if market.spread < 0.02:
            score += 3
        elif market.spread < 0.05:
            score += 2
        elif market.spread < 0.10:
            score += 1
        else:
            continue  # Skip illiquid markets

        # Time to resolution score
        try:
            hours_to_resolution = (
                market.end_date - now
            ).total_seconds() / 3600

            if 0.25 <= hours_to_resolution <= 1:
                score += 3  # 15min - 1hr ideal for 15min trading
            elif 1 < hours_to_resolution <= 4:
                score += 2
            elif 4 < hours_to_resolution <= 24:
                score += 1
            elif hours_to_resolution <= 0:
                continue  # Skip expired markets
        except Exception:
            pass  # If we can't parse date, don't score on it

        # Volume bonus
        if market.volume > 10000:
            score += 1

        scored_markets.append((score, market))

    if not scored_markets:
        return None

    # Return highest scoring market
    return max(scored_markets, key=lambda x: x[0])[1]
