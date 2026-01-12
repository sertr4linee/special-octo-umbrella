"""FastAPI application for the trading bot web UI."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from btc_bot.analysis.indicators import TechnicalIndicators
from btc_bot.analysis.scoring import MultiIndicatorScorer
from btc_bot.api.binance.client import BinanceDataFetcher
from btc_bot.api.polymarket.auth import PolymarketAuth
from btc_bot.api.polymarket.client import PolymarketClient
from btc_bot.config.constants import INDICATOR_WEIGHTS
from btc_bot.config.settings import Settings, TradingMode, get_settings
from btc_bot.trading.executor import TradeExecutor, select_best_market
from btc_bot.trading.paper_trader import PaperTrader
from btc_bot.utils.logging import setup_logging

logger = logging.getLogger(__name__)

# Global state
class BotState:
    """Global state for the trading bot."""

    def __init__(self):
        self.settings: Optional[Settings] = None
        self.is_running: bool = False
        self.last_cycle: Optional[datetime] = None
        self.last_signal: Optional[dict] = None
        self.last_indicators: Optional[dict] = None
        self.last_btc_price: float = 0.0
        self.websocket_clients: list[WebSocket] = []
        self.paper_trader: Optional[PaperTrader] = None
        self.executor: Optional[TradeExecutor] = None
        self.binance: Optional[BinanceDataFetcher] = None
        self.indicators: Optional[TechnicalIndicators] = None
        self.scorer: Optional[MultiIndicatorScorer] = None
        self.polymarket: Optional[PolymarketClient] = None
        self._trading_task: Optional[asyncio.Task] = None

    def initialize(self):
        """Initialize bot components."""
        self.settings = get_settings()

        # Data fetcher
        self.binance = BinanceDataFetcher(self.settings.binance)

        # Technical analysis
        self.indicators = TechnicalIndicators(self.settings.indicators)
        self.scorer = MultiIndicatorScorer(self.settings.indicators, INDICATOR_WEIGHTS)

        # Polymarket client
        poly_auth = PolymarketAuth(self.settings.polymarket)
        self.polymarket = PolymarketClient(poly_auth, self.settings.polymarket)

        # Paper trader
        if self.settings.trading.mode == TradingMode.PAPER:
            self.paper_trader = PaperTrader(initial_balance=1000.0, save_path=Path("paper_trades.json"))

        # Executor
        self.executor = TradeExecutor(self.polymarket, self.paper_trader, self.settings.trading)

        logger.info("Bot components initialized")


bot_state = BotState()


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# Lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    setup_logging(level="INFO")
    bot_state.initialize()
    logger.info("Web UI started")
    yield
    # Cleanup
    if bot_state._trading_task:
        bot_state._trading_task.cancel()
    logger.info("Web UI stopped")


# Create FastAPI app
app = FastAPI(
    title="Polymarket BTC Bot",
    description="Bitcoin prediction trading bot dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

# Setup static files and templates
WEB_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")


# Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/status")
async def get_status():
    """Get bot status."""
    portfolio_summary = {}
    if bot_state.paper_trader:
        portfolio_summary = bot_state.paper_trader.get_summary()

    return {
        "is_running": bot_state.is_running,
        "mode": bot_state.settings.trading.mode.value if bot_state.settings else "unknown",
        "last_cycle": bot_state.last_cycle.isoformat() if bot_state.last_cycle else None,
        "btc_price": bot_state.last_btc_price,
        "trade_amount": bot_state.settings.trading.trade_amount_usd if bot_state.settings else 0,
        "interval_minutes": bot_state.settings.trading.interval_minutes if bot_state.settings else 15,
        "confidence_threshold": bot_state.settings.trading.min_score_threshold if bot_state.settings else 0.6,
        "portfolio": portfolio_summary,
    }


@app.get("/api/signal")
async def get_signal():
    """Get last trading signal."""
    return {
        "signal": bot_state.last_signal,
        "indicators": bot_state.last_indicators,
        "btc_price": bot_state.last_btc_price,
        "timestamp": bot_state.last_cycle.isoformat() if bot_state.last_cycle else None,
    }


@app.get("/api/trades")
async def get_trades():
    """Get recent trades."""
    if not bot_state.paper_trader:
        return {"trades": []}

    trades = bot_state.paper_trader.get_recent_trades(limit=20)
    return {
        "trades": [t.to_dict() for t in trades],
    }


@app.get("/api/price")
async def get_btc_price():
    """Get current BTC price."""
    try:
        if bot_state.binance:
            price = bot_state.binance.get_current_price()
            stats = bot_state.binance.get_24h_stats()
            return {
                "price": price,
                "change_24h": stats["price_change_pct"],
                "high_24h": stats["high_24h"],
                "low_24h": stats["low_24h"],
            }
    except Exception as e:
        logger.error(f"Failed to get BTC price: {e}")

    return {"price": 0, "change_24h": 0, "high_24h": 0, "low_24h": 0}


@app.post("/api/start")
async def start_bot():
    """Start the trading bot."""
    if bot_state.is_running:
        return {"status": "already_running"}

    bot_state.is_running = True
    bot_state._trading_task = asyncio.create_task(trading_loop())

    await manager.broadcast({"type": "status", "is_running": True})
    return {"status": "started"}


@app.post("/api/stop")
async def stop_bot():
    """Stop the trading bot."""
    if not bot_state.is_running:
        return {"status": "already_stopped"}

    bot_state.is_running = False
    if bot_state._trading_task:
        bot_state._trading_task.cancel()
        bot_state._trading_task = None

    await manager.broadcast({"type": "status", "is_running": False})
    return {"status": "stopped"}


@app.post("/api/run-once")
async def run_once():
    """Run a single trading cycle."""
    result = await run_trading_cycle()
    return result


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_json({
            "type": "init",
            "is_running": bot_state.is_running,
            "btc_price": bot_state.last_btc_price,
        })

        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)


async def run_trading_cycle() -> dict:
    """Execute a single trading cycle."""
    logger.info("=" * 60)
    logger.info("TRADING CYCLE START")
    logger.info("=" * 60)

    result = {
        "status": "completed",
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        # Step 1: Fetch BTC data
        df = bot_state.binance.get_historical_klines()
        btc_price = bot_state.binance.get_current_price()
        bot_state.last_btc_price = btc_price

        # Broadcast price update
        await manager.broadcast({
            "type": "price",
            "price": btc_price,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Step 2: Calculate indicators
        indicator_values = bot_state.indicators.calculate_all(df)
        bot_state.last_indicators = indicator_values.to_dict()

        # Step 3: Generate signal
        signal = bot_state.scorer.calculate_signal(indicator_values)
        bot_state.last_signal = signal.to_dict()

        # Broadcast signal update
        await manager.broadcast({
            "type": "signal",
            "signal": bot_state.last_signal,
            "indicators": bot_state.last_indicators,
            "btc_price": btc_price,
        })

        result["signal"] = bot_state.last_signal
        result["indicators"] = bot_state.last_indicators
        result["btc_price"] = btc_price

        # Step 4: Find markets
        markets = await bot_state.polymarket.find_bitcoin_markets()

        if not markets:
            logger.warning("No Bitcoin markets found")
            result["trade"] = {"status": "SKIPPED", "reason": "no_markets"}
        else:
            # Step 5: Select and trade
            market = select_best_market(markets)

            if market:
                trade_result = bot_state.executor.execute(market, signal, btc_price)
                result["trade"] = trade_result

                # Broadcast trade
                await manager.broadcast({
                    "type": "trade",
                    "trade": trade_result,
                    "market": market.question,
                })
            else:
                result["trade"] = {"status": "SKIPPED", "reason": "no_suitable_market"}

        bot_state.last_cycle = datetime.utcnow()

        # Broadcast portfolio update
        if bot_state.paper_trader:
            await manager.broadcast({
                "type": "portfolio",
                "portfolio": bot_state.paper_trader.get_summary(),
            })

    except Exception as e:
        logger.error(f"Trading cycle failed: {e}", exc_info=True)
        result["status"] = "error"
        result["error"] = str(e)

    logger.info("=" * 60)
    return result


async def trading_loop():
    """Main trading loop."""
    interval = bot_state.settings.trading.interval_minutes * 60

    while bot_state.is_running:
        try:
            await run_trading_cycle()
        except Exception as e:
            logger.error(f"Trading loop error: {e}")

        # Wait for next interval
        await asyncio.sleep(interval)


def main():
    """Entry point for the web UI."""
    setup_logging(level="INFO")
    logger.info("Starting Polymarket BTC Bot Web UI...")
    uvicorn.run(
        "btc_bot.web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
