"""Paper trading simulation for testing strategies without real money."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from btc_bot.analysis.scoring import Direction
from btc_bot.config.constants import PAPER_TRADING_INITIAL_BALANCE

logger = logging.getLogger(__name__)


@dataclass
class PaperTrade:
    """Represents a simulated trade."""

    id: str
    timestamp: datetime
    market_question: str
    direction: str  # "YES" or "NO"
    prediction: Direction  # UP or DOWN
    amount_usd: float
    entry_price: float
    token_id: str
    btc_price_at_entry: float
    status: str = "OPEN"  # OPEN, WON, LOST, EXPIRED
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    settled_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "market_question": self.market_question,
            "direction": self.direction,
            "prediction": self.prediction.value,
            "amount_usd": self.amount_usd,
            "entry_price": self.entry_price,
            "token_id": self.token_id,
            "btc_price_at_entry": self.btc_price_at_entry,
            "status": self.status,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "settled_at": self.settled_at.isoformat() if self.settled_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PaperTrade":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            market_question=data["market_question"],
            direction=data["direction"],
            prediction=Direction(data["prediction"]),
            amount_usd=data["amount_usd"],
            entry_price=data["entry_price"],
            token_id=data["token_id"],
            btc_price_at_entry=data["btc_price_at_entry"],
            status=data["status"],
            exit_price=data.get("exit_price"),
            pnl=data.get("pnl"),
            settled_at=(
                datetime.fromisoformat(data["settled_at"])
                if data.get("settled_at")
                else None
            ),
        )


@dataclass
class PaperPortfolio:
    """Paper trading portfolio tracking."""

    initial_balance: float = PAPER_TRADING_INITIAL_BALANCE
    current_balance: float = PAPER_TRADING_INITIAL_BALANCE
    trades: list[PaperTrade] = field(default_factory=list)

    @property
    def total_pnl(self) -> float:
        """Total profit/loss."""
        return self.current_balance - self.initial_balance

    @property
    def total_pnl_pct(self) -> float:
        """Total P&L as percentage."""
        if self.initial_balance == 0:
            return 0.0
        return (self.total_pnl / self.initial_balance) * 100

    @property
    def win_rate(self) -> float:
        """Win rate for settled trades."""
        settled = [t for t in self.trades if t.status in ("WON", "LOST")]
        if not settled:
            return 0.0
        wins = sum(1 for t in settled if t.status == "WON")
        return wins / len(settled)

    @property
    def open_positions(self) -> list[PaperTrade]:
        """Get all open trades."""
        return [t for t in self.trades if t.status == "OPEN"]

    @property
    def total_trades(self) -> int:
        """Total number of trades."""
        return len(self.trades)

    @property
    def settled_trades(self) -> int:
        """Number of settled trades."""
        return len([t for t in self.trades if t.status != "OPEN"])

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "trades": [t.to_dict() for t in self.trades],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PaperPortfolio":
        """Create from dictionary."""
        portfolio = cls(
            initial_balance=data["initial_balance"],
            current_balance=data["current_balance"],
        )
        portfolio.trades = [PaperTrade.from_dict(t) for t in data.get("trades", [])]
        return portfolio


class PaperTrader:
    """
    Simulates trading without real money.
    Tracks positions, P&L, and win rate.
    """

    def __init__(
        self,
        initial_balance: float = PAPER_TRADING_INITIAL_BALANCE,
        save_path: Optional[Path] = None,
    ):
        """Initialize paper trader.

        Args:
            initial_balance: Starting balance in USD.
            save_path: Optional path to persist portfolio state.
        """
        self.save_path = save_path
        self.portfolio = self._load_or_create_portfolio(initial_balance)
        self._trade_counter = len(self.portfolio.trades)

        logger.info(
            f"Paper trader initialized. Balance: ${self.portfolio.current_balance:.2f}"
        )

    def _load_or_create_portfolio(self, initial_balance: float) -> PaperPortfolio:
        """Load existing portfolio or create new one."""
        if self.save_path and self.save_path.exists():
            try:
                with open(self.save_path) as f:
                    data = json.load(f)
                logger.info(f"Loaded portfolio from {self.save_path}")
                return PaperPortfolio.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load portfolio: {e}")

        return PaperPortfolio(
            initial_balance=initial_balance,
            current_balance=initial_balance,
        )

    def _save_portfolio(self):
        """Save portfolio to disk."""
        if self.save_path:
            try:
                self.save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.save_path, "w") as f:
                    json.dump(self.portfolio.to_dict(), f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to save portfolio: {e}")

    def execute_trade(
        self,
        market_question: str,
        direction: Direction,
        amount: float,
        current_price: float,
        token_id: str,
        btc_price: float,
    ) -> PaperTrade:
        """
        Simulates a trade execution.

        Args:
            market_question: Description of the market.
            direction: UP means buy YES token, DOWN means buy NO token.
            amount: USD amount to trade.
            current_price: Current token price (0.0 to 1.0).
            token_id: Token being bought.
            btc_price: Current BTC price for reference.

        Returns:
            The executed PaperTrade.

        Raises:
            ValueError: If insufficient balance.
        """
        if amount > self.portfolio.current_balance:
            raise ValueError(
                f"Insufficient balance: ${self.portfolio.current_balance:.2f} "
                f"< ${amount:.2f}"
            )

        outcome = "YES" if direction == Direction.UP else "NO"
        self._trade_counter += 1

        trade = PaperTrade(
            id=f"paper_{self._trade_counter:06d}",
            timestamp=datetime.utcnow(),
            market_question=market_question,
            direction=outcome,
            prediction=direction,
            amount_usd=amount,
            entry_price=current_price,
            token_id=token_id,
            btc_price_at_entry=btc_price,
        )

        # Deduct from balance
        self.portfolio.current_balance -= amount
        self.portfolio.trades.append(trade)

        self._save_portfolio()

        logger.info(
            f"PAPER TRADE EXECUTED:\n"
            f"  ID: {trade.id}\n"
            f"  Market: {market_question[:60]}...\n"
            f"  Direction: {outcome} (predict {direction.value})\n"
            f"  Amount: ${amount:.2f}\n"
            f"  Entry Price: {current_price:.4f}\n"
            f"  BTC Price: ${btc_price:,.2f}\n"
            f"  Remaining Balance: ${self.portfolio.current_balance:.2f}"
        )

        return trade

    def settle_trade(self, trade_id: str, won: bool, exit_price: float = 1.0):
        """
        Settles a trade when the market resolves.

        Args:
            trade_id: ID of the trade to settle.
            won: Whether the prediction was correct.
            exit_price: Final price (1.0 for winner, 0.0 for loser).
        """
        trade = next((t for t in self.portfolio.trades if t.id == trade_id), None)
        if not trade:
            logger.warning(f"Trade {trade_id} not found")
            return

        if trade.status != "OPEN":
            logger.warning(f"Trade {trade_id} already settled: {trade.status}")
            return

        trade.exit_price = exit_price
        trade.settled_at = datetime.utcnow()

        if won:
            # Winner gets $1 per share
            shares = trade.amount_usd / trade.entry_price
            payout = shares * 1.0
            trade.pnl = payout - trade.amount_usd
            trade.status = "WON"
        else:
            trade.pnl = -trade.amount_usd
            trade.status = "LOST"

        # Update balance
        self.portfolio.current_balance += trade.amount_usd + trade.pnl

        self._save_portfolio()

        logger.info(
            f"TRADE SETTLED:\n"
            f"  ID: {trade_id}\n"
            f"  Status: {trade.status}\n"
            f"  PnL: ${trade.pnl:+.2f}\n"
            f"  New Balance: ${self.portfolio.current_balance:.2f}"
        )

    def get_summary(self) -> dict:
        """Returns portfolio summary."""
        return {
            "initial_balance": self.portfolio.initial_balance,
            "current_balance": round(self.portfolio.current_balance, 2),
            "total_pnl": round(self.portfolio.total_pnl, 2),
            "total_pnl_pct": f"{self.portfolio.total_pnl_pct:+.1f}%",
            "total_trades": self.portfolio.total_trades,
            "settled_trades": self.portfolio.settled_trades,
            "win_rate": f"{self.portfolio.win_rate:.1%}",
            "open_positions": len(self.portfolio.open_positions),
        }

    def get_open_positions(self) -> list[PaperTrade]:
        """Get all open positions."""
        return self.portfolio.open_positions

    def get_recent_trades(self, limit: int = 10) -> list[PaperTrade]:
        """Get most recent trades."""
        return sorted(
            self.portfolio.trades,
            key=lambda t: t.timestamp,
            reverse=True,
        )[:limit]
