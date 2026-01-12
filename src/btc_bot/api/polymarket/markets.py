"""Polymarket market discovery and filtering for Bitcoin markets."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from py_clob_client.client import ClobClient

from btc_bot.config.constants import BTC_MARKET_KEYWORDS

logger = logging.getLogger(__name__)


@dataclass
class BitcoinMarket:
    """Represents a Bitcoin price prediction market on Polymarket."""

    condition_id: str
    question: str
    description: str
    yes_token_id: str
    no_token_id: str
    end_date: datetime
    resolution_source: str
    current_yes_price: float
    current_no_price: float
    volume: float
    liquidity: float

    @property
    def spread(self) -> float:
        """Calculate the market spread (deviation from 1.0)."""
        return abs((self.current_yes_price + self.current_no_price) - 1.0)

    @property
    def is_liquid(self) -> bool:
        """Check if market has sufficient liquidity (spread < 10%)."""
        return self.spread < 0.10


class MarketDiscovery:
    """
    Discovers and filters Bitcoin price prediction markets.
    Uses both Gamma API (metadata) and CLOB API (prices).
    """

    def __init__(self, gamma_host: str, clob_client: ClobClient):
        """Initialize market discovery.

        Args:
            gamma_host: Gamma API base URL for market metadata.
            clob_client: CLOB client for price data.
        """
        self.gamma_host = gamma_host
        self.clob_client = clob_client

    async def find_bitcoin_markets(self) -> list[BitcoinMarket]:
        """
        Finds active Bitcoin price prediction markets.

        Filters by:
        - Contains Bitcoin/BTC keywords
        - Active status (not resolved)
        - Has valid token IDs

        Returns:
            List of BitcoinMarket objects sorted by liquidity.
        """
        logger.info("Searching for active Bitcoin markets...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Query Gamma API for crypto markets
            response = await client.get(
                f"{self.gamma_host}/markets",
                params={
                    "closed": "false",
                    "limit": 100,
                },
            )
            response.raise_for_status()
            markets_data = response.json()

        btc_markets = []
        for market in markets_data:
            if self._is_bitcoin_price_market(market):
                parsed = self._parse_market(market)
                if parsed:
                    btc_markets.append(parsed)

        # Sort by liquidity (volume) descending
        btc_markets.sort(key=lambda m: m.volume, reverse=True)

        logger.info(f"Found {len(btc_markets)} active Bitcoin markets")
        return btc_markets

    def _is_bitcoin_price_market(self, market: dict) -> bool:
        """Check if market is a Bitcoin price prediction market."""
        question = market.get("question", "").lower()
        description = market.get("description", "").lower()
        tags = [t.lower() for t in market.get("tags", [])]

        # Check for Bitcoin keywords
        text_to_check = f"{question} {description}"
        has_btc_keyword = any(kw in text_to_check for kw in BTC_MARKET_KEYWORDS)

        # Check tags
        has_btc_tag = any(
            tag in tags for tag in ["bitcoin", "btc", "crypto", "cryptocurrency"]
        )

        # Must have price-related keywords
        price_keywords = ["price", "above", "below", "reach", "hit", "exceed"]
        has_price_keyword = any(kw in text_to_check for kw in price_keywords)

        return (has_btc_keyword or has_btc_tag) and has_price_keyword

    def _parse_market(self, market: dict) -> Optional[BitcoinMarket]:
        """Parse market data into BitcoinMarket object."""
        try:
            # Get token IDs
            clob_token_ids = market.get("clobTokenIds", [])
            if len(clob_token_ids) < 2:
                return None

            # Get outcome prices
            outcome_prices = market.get("outcomePrices", [])
            if len(outcome_prices) < 2:
                yes_price = 0.5
                no_price = 0.5
            else:
                yes_price = float(outcome_prices[0]) if outcome_prices[0] else 0.5
                no_price = float(outcome_prices[1]) if outcome_prices[1] else 0.5

            # Parse end date
            end_date_str = market.get("endDate") or market.get("end_date_iso")
            if end_date_str:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            else:
                end_date = datetime.max

            return BitcoinMarket(
                condition_id=market.get("conditionId", ""),
                question=market.get("question", ""),
                description=market.get("description", ""),
                yes_token_id=clob_token_ids[0],
                no_token_id=clob_token_ids[1],
                end_date=end_date,
                resolution_source=market.get("resolutionSource", "Binance"),
                current_yes_price=yes_price,
                current_no_price=no_price,
                volume=float(market.get("volume", 0) or 0),
                liquidity=float(market.get("liquidity", 0) or 0),
            )
        except (KeyError, ValueError, IndexError) as e:
            logger.warning(f"Failed to parse market: {e}")
            return None

    def get_market_prices(self, token_id: str) -> dict:
        """Gets current bid/ask/midpoint for a token.

        Args:
            token_id: The token ID to get prices for.

        Returns:
            Dict with midpoint, buy, and sell prices.
        """
        try:
            return {
                "midpoint": float(self.clob_client.get_midpoint(token_id) or 0),
                "buy": float(self.clob_client.get_price(token_id, side="BUY") or 0),
                "sell": float(self.clob_client.get_price(token_id, side="SELL") or 0),
            }
        except Exception as e:
            logger.warning(f"Failed to get prices for {token_id}: {e}")
            return {"midpoint": 0.5, "buy": 0.5, "sell": 0.5}

    def get_orderbook(self, token_id: str) -> dict:
        """Fetches the current orderbook for analysis.

        Args:
            token_id: The token ID to get orderbook for.

        Returns:
            Orderbook data with bids and asks.
        """
        try:
            return self.clob_client.get_order_book(token_id)
        except Exception as e:
            logger.warning(f"Failed to get orderbook for {token_id}: {e}")
            return {"bids": [], "asks": []}
