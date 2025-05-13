from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class MarketFilter:
    """Dataclass for filtering markets."""

    min_n_forecasters: int = 0
    min_comments_count: int = 0
    min_volume: float = 0.0
    only_open: bool = True


@dataclass
class PooledMarket:
    """Dataclass for a pooled market."""

    id: str  # Platform-prefixed ID, e.g., "gjopen_123", "polymarket_abc"
    question: str
    outcomes: list[str]  # ["Yes", "No"] or ["A", "B", "C"...]
    outcome_probabilities: list[float | None]  # Corresponding probs for outcomes
    formatted_outcomes: str  # e.g., "Yes: 60.0%; No: 40.0%"
    url: str  # Direct URL to the market
    published_at: datetime | None  # Publication/creation time (UTC if possible)
    source_platform: str  # Name of the source platform, e.g., "GJOpen", "Polymarket"

    # Optional fields, common across platforms
    volume: float | None = None  # Trading volume
    n_forecasters: int | None = None  # Number of unique predictors/bettors
    comments_count: int | None = None
    original_market_type: str | None = None  # e.g., "BINARY", "MULTIPLE_CHOICE"
    is_resolved: bool | None = None  # True if market is resolved

    # To store the original market object for further details if needed
    raw_market_data: Any | None = field(default=None, repr=False, compare=False)


class BaseMarket(ABC):
    """Abstract base class for platform-specific market data classes.
    Ensures that each platform-specific market can be converted to a PooledMarket.
    """

    @abstractmethod
    def to_pooled_market(self) -> PooledMarket:
        """Converts the platform-specific market data to the common
        PooledMarket format.
        """

    @classmethod
    def parse_datetime_flexible(cls, dt_str: str | datetime | None) -> datetime | None:
        """Parse a datetime string from a variety of formats."""
        # Try ISO format with 'Z' (UTC)
        if isinstance(dt_str, datetime):  # Already a datetime object
            return dt_str

        try:
            # Handle timezone-aware strings ending with Z
            if dt_str.endswith("Z"):
                # For formats like '2023-10-26T00:00:00Z' or '2023-07-15T20:38:13.044Z'
                # Stripping Z and adding UTC timezone info for fromisoformat
                # Or, ensure it's compatible by adding +00:00 if needed
                if "." in dt_str:
                    dt_obj = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                else:
                    dt_obj = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
                return dt_obj.replace(tzinfo=UTC)
            # Handle timezone-aware strings with offset
            elif (
                "+" in dt_str[10:] or "-" in dt_str[10:]
            ):  # Check for +/- in the time part
                return datetime.fromisoformat(dt_str)
            # Handle naive datetime strings
            else:
                # Try ISO format for naive datetime (e.g. fromisoformat handles
                # '2023-10-26T00:00:00')
                return datetime.fromisoformat(dt_str)
                # If it was truly naive, it remains naive.
                # If it needs to be UTC, caller should specify.
        except ValueError:
            # Fallback for other common formats if needed
            # Example: '2021-07-20 16:00:00' (less common in APIs)
            try:
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # print(f"Warning: Could not parse datetime string: {dt_str}")
                return None


class BaseScraper(ABC):
    """Abstract base class for platform-specific scrapers."""

    @abstractmethod
    async def fetch_markets(self, only_open: bool = True, **kwargs) -> list[Any]:
        """Fetches markets from the specific platform.

        Args:
            only_open: If True, fetches only open/active markets.
            **kwargs: Additional platform-specific parameters.

        Returns:
            A list of platform-specific market objects.
        """

    async def get_pooled_markets(
        self,
        only_open: bool = True,
        **kwargs,
    ) -> list[PooledMarket]:
        """Fetches markets and converts them to the PooledMarket format.

        Args:
            only_open: If True, fetches only open/active markets.
            **kwargs: Additional platform-specific parameters.

        Returns:
            A list of PooledMarket objects.
        """
        platform_specific_markets = await self.fetch_markets(
            only_open=only_open,
            **kwargs,
        )
        pooled_markets = []
        for market in platform_specific_markets:
            if hasattr(market, "to_pooled_market") and callable(
                market.to_pooled_market,
            ):
                try:
                    pooled_markets.append(market.to_pooled_market())
                except Exception:
                    getattr(market, "id", "unknown_id")
            else:
                getattr(market, "id", "unknown_id")
        return pooled_markets
