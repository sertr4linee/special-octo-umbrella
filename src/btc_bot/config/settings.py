"""Configuration management using Pydantic Settings."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    """Trading mode: paper (simulation) or live (real money)."""

    PAPER = "paper"
    LIVE = "live"


class PolymarketConfig(BaseModel):
    """Polymarket API configuration."""

    host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"
    chain_id: int = 137  # Polygon mainnet
    private_key: SecretStr = SecretStr("")
    funder_address: str = ""
    signature_type: int = 0  # 0=EOA, 1=Magic, 2=Gnosis Safe


class BinanceConfig(BaseModel):
    """Binance API configuration for price data."""

    base_url: str = "https://api.binance.com"
    symbol: str = "BTCUSDT"


class TradingConfig(BaseModel):
    """Trading parameters configuration."""

    mode: TradingMode = TradingMode.PAPER
    trade_amount_usd: float = Field(default=10.0, ge=1.0, le=10000.0)
    interval_minutes: int = Field(default=15, ge=1, le=60)
    max_daily_trades: int = Field(default=96, ge=1)
    min_score_threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class IndicatorConfig(BaseModel):
    """Technical indicator parameters."""

    # RSI
    rsi_period: int = Field(default=14, ge=2)
    rsi_overbought: float = Field(default=70.0, ge=50.0, le=100.0)
    rsi_oversold: float = Field(default=30.0, ge=0.0, le=50.0)

    # MACD
    macd_fast: int = Field(default=12, ge=2)
    macd_slow: int = Field(default=26, ge=2)
    macd_signal: int = Field(default=9, ge=2)

    # EMA Crossover
    ema_short: int = Field(default=9, ge=2)
    ema_long: int = Field(default=21, ge=2)

    # Bollinger Bands
    bb_period: int = Field(default=20, ge=2)
    bb_std_dev: float = Field(default=2.0, ge=0.5, le=4.0)


class Settings(BaseSettings):
    """Main application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    polymarket: PolymarketConfig = PolymarketConfig()
    binance: BinanceConfig = BinanceConfig()
    trading: TradingConfig = TradingConfig()
    indicators: IndicatorConfig = IndicatorConfig()


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
