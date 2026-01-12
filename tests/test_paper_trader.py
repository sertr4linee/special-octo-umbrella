"""Tests for paper trading simulation."""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from btc_bot.analysis.scoring import Direction
from btc_bot.trading.paper_trader import PaperTrade, PaperTrader


class TestPaperTrader:
    """Test suite for PaperTrader class."""

    @pytest.fixture
    def paper_trader(self) -> PaperTrader:
        """Create paper trader instance for testing."""
        return PaperTrader(initial_balance=1000.0)

    def test_initial_balance(self, paper_trader: PaperTrader):
        """Test initial balance is set correctly."""
        assert paper_trader.portfolio.current_balance == 1000.0
        assert paper_trader.portfolio.initial_balance == 1000.0
        assert paper_trader.portfolio.total_pnl == 0.0

    def test_execute_trade_deducts_balance(self, paper_trader: PaperTrader):
        """Test that executing a trade deducts from balance."""
        trade = paper_trader.execute_trade(
            market_question="Will BTC hit $50k?",
            direction=Direction.UP,
            amount=100.0,
            current_price=0.45,
            token_id="test_token_123",
            btc_price=45000.0,
        )

        assert paper_trader.portfolio.current_balance == 900.0
        assert trade.amount_usd == 100.0
        assert trade.direction == "YES"
        assert trade.status == "OPEN"

    def test_execute_trade_insufficient_balance(self, paper_trader: PaperTrader):
        """Test that trade fails with insufficient balance."""
        with pytest.raises(ValueError, match="Insufficient balance"):
            paper_trader.execute_trade(
                market_question="Will BTC hit $50k?",
                direction=Direction.UP,
                amount=2000.0,  # More than balance
                current_price=0.45,
                token_id="test_token_123",
                btc_price=45000.0,
            )

    def test_settle_winning_trade(self, paper_trader: PaperTrader):
        """Test settling a winning trade."""
        trade = paper_trader.execute_trade(
            market_question="Will BTC hit $50k?",
            direction=Direction.UP,
            amount=100.0,
            current_price=0.40,  # Entry price
            token_id="test_token_123",
            btc_price=45000.0,
        )

        # Settle as winner
        paper_trader.settle_trade(trade.id, won=True)

        settled_trade = paper_trader.portfolio.trades[0]
        assert settled_trade.status == "WON"
        assert settled_trade.pnl is not None
        assert settled_trade.pnl > 0  # Should profit

        # Balance should be higher than before the trade
        # Won: 100 / 0.40 = 250 shares * $1 = $250 payout
        # PnL = $250 - $100 = $150
        assert paper_trader.portfolio.current_balance == 1150.0

    def test_settle_losing_trade(self, paper_trader: PaperTrader):
        """Test settling a losing trade."""
        trade = paper_trader.execute_trade(
            market_question="Will BTC hit $50k?",
            direction=Direction.UP,
            amount=100.0,
            current_price=0.45,
            token_id="test_token_123",
            btc_price=45000.0,
        )

        # Settle as loser
        paper_trader.settle_trade(trade.id, won=False)

        settled_trade = paper_trader.portfolio.trades[0]
        assert settled_trade.status == "LOST"
        assert settled_trade.pnl == -100.0  # Lost entire stake

        # Balance should still be 900 (no payout)
        assert paper_trader.portfolio.current_balance == 900.0

    def test_win_rate_calculation(self, paper_trader: PaperTrader):
        """Test win rate calculation."""
        # Execute and settle multiple trades
        for i in range(4):
            trade = paper_trader.execute_trade(
                market_question=f"Test market {i}",
                direction=Direction.UP,
                amount=10.0,
                current_price=0.50,
                token_id=f"token_{i}",
                btc_price=45000.0,
            )
            # Win 3 out of 4
            paper_trader.settle_trade(trade.id, won=(i < 3))

        assert paper_trader.portfolio.win_rate == 0.75  # 3/4

    def test_portfolio_summary(self, paper_trader: PaperTrader):
        """Test portfolio summary generation."""
        paper_trader.execute_trade(
            market_question="Test market",
            direction=Direction.UP,
            amount=50.0,
            current_price=0.50,
            token_id="token_1",
            btc_price=45000.0,
        )

        summary = paper_trader.get_summary()

        assert "initial_balance" in summary
        assert "current_balance" in summary
        assert "total_pnl" in summary
        assert "win_rate" in summary
        assert "open_positions" in summary

    def test_persistence(self):
        """Test that portfolio persists to disk."""
        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test_portfolio.json"

            # Create trader and execute trade
            trader1 = PaperTrader(initial_balance=1000.0, save_path=save_path)
            trader1.execute_trade(
                market_question="Test",
                direction=Direction.UP,
                amount=100.0,
                current_price=0.50,
                token_id="token_1",
                btc_price=45000.0,
            )

            # Create new trader loading from same path
            trader2 = PaperTrader(initial_balance=1000.0, save_path=save_path)

            # Should have loaded the previous state
            assert len(trader2.portfolio.trades) == 1
            assert trader2.portfolio.current_balance == 900.0
