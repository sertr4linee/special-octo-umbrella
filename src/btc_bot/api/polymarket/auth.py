"""Polymarket authentication handling for L1 and L2 auth."""

import logging
from typing import Optional

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

from btc_bot.config.settings import PolymarketConfig

logger = logging.getLogger(__name__)


class PolymarketAuth:
    """
    Handles L1 (wallet-based) and L2 (API key) authentication for Polymarket.

    L1 Auth: Uses wallet private key for EIP-712 signatures.
             Proves ownership and control over the private key.
    L2 Auth: HMAC-SHA256 API keys derived from L1 signature.
             Used for faster request signing during trading.
    """

    def __init__(self, config: PolymarketConfig):
        """Initialize authentication handler.

        Args:
            config: Polymarket configuration with credentials.
        """
        self.config = config
        self._authenticated_client: Optional[ClobClient] = None
        self._readonly_client: Optional[ClobClient] = None
        self._api_creds: Optional[ApiCreds] = None

    def get_authenticated_client(self) -> ClobClient:
        """Creates and returns an authenticated CLOB client.

        This client can place orders and manage positions.
        Requires valid private key and funder address.

        Returns:
            Authenticated ClobClient instance.

        Raises:
            ValueError: If private key or funder address is not configured.
        """
        if self._authenticated_client is not None:
            return self._authenticated_client

        private_key = self.config.private_key.get_secret_value()
        if not private_key or private_key == "":
            raise ValueError(
                "Private key not configured. Set POLYMARKET__PRIVATE_KEY in .env"
            )

        if not self.config.funder_address:
            raise ValueError(
                "Funder address not configured. Set POLYMARKET__FUNDER_ADDRESS in .env"
            )

        logger.info("Initializing authenticated Polymarket client...")

        self._authenticated_client = ClobClient(
            host=self.config.host,
            key=private_key,
            chain_id=self.config.chain_id,
            signature_type=self.config.signature_type,
            funder=self.config.funder_address,
        )

        # Derive L2 API credentials from L1 signature
        # This only needs to be done once - credentials are deterministic
        logger.info("Deriving L2 API credentials...")
        self._api_creds = self._authenticated_client.create_or_derive_api_creds()
        self._authenticated_client.set_api_creds(self._api_creds)

        logger.info("Polymarket authentication successful")
        return self._authenticated_client

    def get_readonly_client(self) -> ClobClient:
        """Returns a read-only client (no authentication required).

        This client can fetch market data, prices, and orderbooks
        but cannot place orders.

        Returns:
            Read-only ClobClient instance.
        """
        if self._readonly_client is None:
            self._readonly_client = ClobClient(host=self.config.host)
            logger.debug("Read-only Polymarket client initialized")

        return self._readonly_client

    def get_api_credentials(self) -> Optional[ApiCreds]:
        """Get the derived API credentials.

        Returns:
            API credentials if authenticated, None otherwise.
        """
        return self._api_creds

    def is_authenticated(self) -> bool:
        """Check if the client is authenticated.

        Returns:
            True if authenticated with valid credentials.
        """
        return self._authenticated_client is not None and self._api_creds is not None
