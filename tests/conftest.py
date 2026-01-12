"""Pytest configuration and fixtures."""

import pandas as pd
import pytest

from btc_bot.config.settings import IndicatorConfig, Settings, TradingConfig, TradingMode


@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """Generate sample OHLCV data for testing."""
    import numpy as np

    np.random.seed(42)
    n_periods = 100

    # Generate realistic BTC price data
    base_price = 45000
    returns = np.random.normal(0, 0.01, n_periods)
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        "open": prices * (1 + np.random.uniform(-0.005, 0.005, n_periods)),
        "high": prices * (1 + np.random.uniform(0, 0.01, n_periods)),
        "low": prices * (1 - np.random.uniform(0, 0.01, n_periods)),
        "close": prices,
        "volume": np.random.uniform(100, 1000, n_periods),
    })

    df.index = pd.date_range(end=pd.Timestamp.now(), periods=n_periods, freq="15min")
    return df


@pytest.fixture
def indicator_config() -> IndicatorConfig:
    """Default indicator configuration for testing."""
    return IndicatorConfig()


@pytest.fixture
def trading_config() -> TradingConfig:
    """Paper trading configuration for testing."""
    return TradingConfig(
        mode=TradingMode.PAPER,
        trade_amount_usd=10.0,
        interval_minutes=15,
        min_score_threshold=0.6,
    )


@pytest.fixture
def test_settings(trading_config) -> Settings:
    """Test settings with paper trading mode."""
    settings = Settings()
    settings.trading = trading_config
    return settings
