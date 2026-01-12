"""High-level Polymarket client wrapper for trading operations."""

import logging
from typing import Optional

from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

from btc_bot.api.polymarket.auth import PolymarketAuth
from btc_bot.api.polymarket.markets import BitcoinMarket, MarketDiscovery
from btc_bot.config.settings import PolymarketConfig

logger = logging.getLogger(__name__)


class PolymarketClient:
    """High-level wrapper for Polymarket trading operations."""

    def __init__(self, auth: PolymarketAuth, config: PolymarketConfig):
        """Initialize Polymarket client.

        Args:
            auth: Authentication handler for L1/L2 auth.
            config: Polymarket configuration.
        """
        self.auth = auth
        self.config = config
        self.market_discovery = MarketDiscovery(
            config.gamma_host,
            auth.get_readonly_client(),
        )

    def place_market_order(
        self,
        token_id: str,
        amount: float,
        side: str,  # "YES" or "NO"
    ) -> dict:
        """
        Places a Fill-or-Kill market order.

        Args:
            token_id: The token to buy.
            amount: Dollar amount to spend.
            side: "YES" for UP prediction, "NO" for DOWN prediction.

        Returns:
            Order response from Polymarket.

        Raises:
            ValueError: If client is not authenticated.
        """
        if not self.auth.is_authenticated():
            # Trigger authentication
            self.auth.get_authenticated_client()

        client = self.auth.get_authenticated_client()

        logger.info(
            f"Placing market order: {side} token, amount=${amount:.2f}, token_id={token_id[:16]}..."
        )

        # Create market order with Fill-or-Kill type
        order = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
        )

        # Build and sign the order
        signed_order = client.create_market_order(order)

        # Post the order
        response = client.post_order(signed_order, OrderType.FOK)

        logger.info(f"Order submitted: {response}")
        return response

    def place_limit_order(
        self,
        token_id: str,
        amount: float,
        price: float,
        side: str,
    ) -> dict:
        """
        Places a limit order (Good-Til-Cancelled).

        Args:
            token_id: The token to buy/sell.
            amount: Number of shares.
            price: Limit price (0.0 to 1.0).
            side: "BUY" or "SELL".

        Returns:
            Order response from Polymarket.
        """
        client = self.auth.get_authenticated_client()

        from py_clob_client.clob_types import OrderArgs
        from py_clob_client.order_builder.constants import BUY as BUY_SIDE, SELL as SELL_SIDE

        order_side = BUY_SIDE if side.upper() == "BUY" else SELL_SIDE

        order = OrderArgs(
            token_id=token_id,
            price=price,
            size=amount,
            side=order_side,
        )

        signed_order = client.create_order(order)
        response = client.post_order(signed_order, OrderType.GTC)

        logger.info(f"Limit order submitted: {response}")
        return response

    def cancel_order(self, order_id: str) -> dict:
        """Cancel an open order.

        Args:
            order_id: The order ID to cancel.

        Returns:
            Cancellation response.
        """
        client = self.auth.get_authenticated_client()
        response = client.cancel(order_id)
        logger.info(f"Order cancelled: {order_id}")
        return response

    def cancel_all_orders(self) -> dict:
        """Cancel all open orders.

        Returns:
            Cancellation response.
        """
        client = self.auth.get_authenticated_client()
        response = client.cancel_all()
        logger.info("All orders cancelled")
        return response

    def get_open_orders(self) -> list:
        """Get all open orders.

        Returns:
            List of open orders.
        """
        client = self.auth.get_authenticated_client()
        return client.get_orders()

    def get_positions(self) -> list:
        """Get current positions.

        Returns:
            List of positions with token holdings.
        """
        client = self.auth.get_authenticated_client()
        # Note: This may require additional API setup
        try:
            return client.get_positions()
        except Exception as e:
            logger.warning(f"Failed to get positions: {e}")
            return []

    async def find_bitcoin_markets(self) -> list[BitcoinMarket]:
        """Find active Bitcoin prediction markets.

        Returns:
            List of Bitcoin markets sorted by liquidity.
        """
        return await self.market_discovery.find_bitcoin_markets()

    def get_market_prices(self, market: BitcoinMarket) -> dict:
        """Get current prices for both YES and NO tokens.

        Args:
            market: The Bitcoin market to get prices for.

        Returns:
            Dict with yes_price and no_price.
        """
        yes_prices = self.market_discovery.get_market_prices(market.yes_token_id)
        no_prices = self.market_discovery.get_market_prices(market.no_token_id)

        return {
            "yes_price": yes_prices["midpoint"],
            "no_price": no_prices["midpoint"],
            "yes_buy": yes_prices["buy"],
            "yes_sell": yes_prices["sell"],
            "no_buy": no_prices["buy"],
            "no_sell": no_prices["sell"],
        }
