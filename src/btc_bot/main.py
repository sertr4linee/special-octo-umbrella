"""Main application orchestrator for the Polymarket BTC trading bot."""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from btc_bot.analysis.indicators import TechnicalIndicators
from btc_bot.analysis.scoring import Direction, MultiIndicatorScorer
from btc_bot.api.binance.client import BinanceDataFetcher
from btc_bot.api.polymarket.auth import PolymarketAuth
from btc_bot.api.polymarket.client import PolymarketClient
from btc_bot.config.constants import INDICATOR_WEIGHTS
from btc_bot.config.settings import Settings, TradingMode, get_settings
from btc_bot.scheduler.job_scheduler import TradingScheduler
from btc_bot.trading.executor import TradeExecutor, select_best_market
from btc_bot.trading.paper_trader import PaperTrader
from btc_bot.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class TradingBot:
    """Main application orchestrator for the trading bot."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the trading bot.

        Args:
            settings: Application settings. If None, loads from environment.
        """
        self.settings = settings or get_settings()
        self._shutdown_event = asyncio.Event()

        # Initialize components
        self._init_components()

    def _init_components(self):
        """Initialize all bot components."""
        # Data fetcher
        self.binance = BinanceDataFetcher(self.settings.binance)

        # Technical analysis
        self.indicators = TechnicalIndicators(self.settings.indicators)
        self.scorer = MultiIndicatorScorer(
            self.settings.indicators,
            INDICATOR_WEIGHTS,
        )

        # Polymarket client
        self.poly_auth = PolymarketAuth(self.settings.polymarket)
        self.polymarket = PolymarketClient(self.poly_auth, self.settings.polymarket)

        # Paper trader (if in paper mode)
        self.paper_trader: Optional[PaperTrader] = None
        if self.settings.trading.mode == TradingMode.PAPER:
            save_path = Path("paper_trades.json")
            self.paper_trader = PaperTrader(
                initial_balance=1000.0,
                save_path=save_path,
            )

        # Trade executor
        self.executor = TradeExecutor(
            self.polymarket,
            self.paper_trader,
            self.settings.trading,
        )

        # Scheduler
        self.scheduler = TradingScheduler(self.settings.trading.interval_minutes)

    async def trading_cycle(self):
        """Single trading cycle - runs every interval."""
        logger.info("\n" + "=" * 70)
        logger.info("TRADING CYCLE START")
        logger.info("=" * 70)

        try:
            # Step 1: Fetch Bitcoin price data
            logger.info("Step 1: Fetching BTC price data from Binance...")
            df = self.binance.get_historical_klines()
            current_price = self.binance.get_current_price()
            logger.info(f"Current BTC price: ${current_price:,.2f}")

            # Step 2: Calculate technical indicators
            logger.info("Step 2: Calculating technical indicators...")
            indicator_values = self.indicators.calculate_all(df)
            logger.info(f"Indicators: {indicator_values.to_dict()}")

            # Step 3: Generate trading signal
            logger.info("Step 3: Generating trading signal...")
            signal = self.scorer.calculate_signal(indicator_values)
            logger.info(
                f"Signal: {signal.direction.value} "
                f"(confidence: {signal.confidence:.2%})"
            )
            logger.info(f"Analysis: {signal.reasoning}")

            # Step 4: Find Bitcoin markets on Polymarket
            logger.info("Step 4: Discovering Bitcoin markets...")
            markets = await self.polymarket.find_bitcoin_markets()

            if not markets:
                logger.warning("No active Bitcoin markets found on Polymarket")
                self._log_cycle_end("NO_MARKETS")
                return

            logger.info(f"Found {len(markets)} Bitcoin market(s)")

            # Step 5: Select best market
            logger.info("Step 5: Selecting optimal market...")
            market = select_best_market(markets)

            if not market:
                logger.warning("No suitable market found (all too illiquid or expired)")
                self._log_cycle_end("NO_SUITABLE_MARKET")
                return

            logger.info(f"Selected market: {market.question}")
            logger.info(
                f"Market prices: YES={market.current_yes_price:.4f}, "
                f"NO={market.current_no_price:.4f}, spread={market.spread:.2%}"
            )

            # Step 6: Execute trade
            logger.info("Step 6: Executing trade...")
            result = self.executor.execute(market, signal, current_price)

            # Step 7: Log results
            if result["status"] == "EXECUTED":
                logger.info(f"Trade executed successfully: {result}")
                if self.paper_trader:
                    summary = self.paper_trader.get_summary()
                    logger.info(f"Portfolio summary: {summary}")
            else:
                logger.info(f"Trade skipped: {result.get('reason', 'unknown')}")

            self._log_cycle_end(result["status"])

        except Exception as e:
            logger.error(f"Trading cycle failed: {e}", exc_info=True)
            self._log_cycle_end("ERROR")

    def _log_cycle_end(self, status: str):
        """Log end of trading cycle."""
        next_run = self.scheduler.get_next_run_time()
        next_run_str = next_run.strftime("%H:%M:%S UTC") if next_run else "N/A"

        logger.info("=" * 70)
        logger.info(f"TRADING CYCLE END - Status: {status}")
        logger.info(f"Next cycle: {next_run_str}")
        logger.info("=" * 70 + "\n")

    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run_async(self):
        """Run the bot asynchronously."""
        logger.info("\n" + "#" * 70)
        logger.info("POLYMARKET BTC PREDICTION BOT")
        logger.info("#" * 70)
        logger.info(f"Mode: {self.settings.trading.mode.value.upper()}")
        logger.info(f"Trade amount: ${self.settings.trading.trade_amount_usd}")
        logger.info(f"Interval: {self.settings.trading.interval_minutes} minutes")
        logger.info(f"Confidence threshold: {self.settings.trading.min_score_threshold:.0%}")
        logger.info("#" * 70 + "\n")

        # Start scheduler
        self.scheduler.start(self.trading_cycle, run_immediately=True)

        # Set daily reset callback
        async def daily_reset():
            logger.info("Midnight reset: clearing daily trade counter")
            self.executor.reset_daily_counter()

        self.scheduler.set_daily_reset_callback(daily_reset)

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Graceful shutdown
        logger.info("Shutting down...")
        self.scheduler.stop()
        logger.info("Bot stopped")

    def run(self):
        """Run the bot (blocking)."""
        setup_logging(level="INFO")
        self._setup_signal_handlers()

        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)


def main():
    """Entry point for the trading bot."""
    bot = TradingBot()
    bot.run()


if __name__ == "__main__":
    main()
