# %%

import json
import time
from dataclasses import dataclass
from datetime import datetime  # , timedelta # timedelta not used

# import numpy as np # Not explicitly used
# from openai import OpenAI # Not used
from functools import cache
from typing import Any

import aiohttp
import dotenv

# from py_clob_client.client import ClobClient, TradeParams # Not used in this version
# from py_clob_client.constants import POLYGON # Not used in this version
from tqdm import tqdm

from mootlib.scrapers.common_markets import (
    BaseMarket,
    BaseScraper,
    MarketFilter,
    PooledMarket,
)

# Load environment variables if .env file exists
dotenv.load_dotenv()

GAMMA_API_BASE_URL = "https://gamma-api.polymarket.com"


DEFAULT_MARKET_FILTER = MarketFilter(
    min_volume=10000,
    only_open=True,
)


@cache
def _parse_outcomes_string(outcomes_str: str) -> list[str]:
    if not outcomes_str or not isinstance(outcomes_str, str):
        return []
    try:
        parsed_outcomes = json.loads(outcomes_str)
        if isinstance(parsed_outcomes, list):
            return [str(o) for o in parsed_outcomes]
        return []
    except json.JSONDecodeError:
        return []


def _format_outcomes_polymarket(
    outcomes: list[str],
    prices: list[float] | None = None,
) -> str:
    if not outcomes:
        return "N/A"
    if not prices or len(outcomes) != len(prices):
        return "; ".join([f"{name}: N/A" for name in outcomes])
    return "; ".join(
        [
            (
                f"{name}: {(price * 100):.1f}% prob"
                if price is not None
                else f"{name}: N/A"
            )
            for name, price in zip(outcomes, prices, strict=False)
        ],
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_str(value: Any, default: str = "") -> str:
    """Safe string conversion."""
    if value is None:
        return default
    return str(value)


@dataclass
class PolymarketMarket(BaseMarket):
    """Polymarket market dataclass."""

    id: str
    question: str
    slug: str
    description: str
    outcomes: list[str]
    outcome_prices: list[float | None] | None  # Prices <-> outcomes, can have None
    formatted_outcomes: str
    url: str
    total_volume: float
    liquidity: float
    end_date: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    active: bool  # From API
    closed: bool  # From API, used for is_resolved
    resolution_source: str | None
    # Store raw API type if available for more accurate original_market_type
    raw_market_type: str | None = None

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> "PolymarketMarket":
        """Create PolymarketMarket from API data."""
        raw_outcomes = data.get("outcomes", "[]")
        parsed_outcomes_list = _parse_outcomes_string(raw_outcomes)

        raw_outcome_prices_payload = data.get("outcomePrices")
        parsed_outcome_prices_list: list[float | None] = []

        temp_prices_for_parsing = []
        if isinstance(raw_outcome_prices_payload, str):
            try:
                potential_list = json.loads(raw_outcome_prices_payload)
                if isinstance(potential_list, list):
                    temp_prices_for_parsing = potential_list
            except json.JSONDecodeError:
                pass  # Keep temp_prices_for_parsing empty
        elif isinstance(raw_outcome_prices_payload, list):
            temp_prices_for_parsing = raw_outcome_prices_payload

        # Ensure prices list matches outcomes length, padding with None if necessary
        if temp_prices_for_parsing:
            num_outcomes = len(parsed_outcomes_list)
            parsed_outcome_prices_list = [
                (_safe_float(p) if p is not None else None)
                for p in temp_prices_for_parsing[:num_outcomes]
            ]
            # Pad with None if API provided fewer prices than outcomes
            if len(parsed_outcome_prices_list) < num_outcomes:
                parsed_outcome_prices_list.extend(
                    [None] * (num_outcomes - len(parsed_outcome_prices_list)),
                )
        else:  # No prices provided or parse failed
            parsed_outcome_prices_list = [None] * len(parsed_outcomes_list)

        formatted_outcomes_str = _format_outcomes_polymarket(
            parsed_outcomes_list,
            parsed_outcome_prices_list,
        )

        total_volume = _safe_float(data.get("volume"))
        if total_volume == 0.0:
            total_volume = _safe_float(data.get("volumeNum"))

        liquidity = _safe_float(data.get("liquidityAmm")) + _safe_float(
            data.get("liquidityClob"),
        )
        if liquidity == 0.0:
            liquidity = _safe_float(data.get("liquidity"))
        if liquidity == 0.0:
            liquidity = _safe_float(data.get("liquidityNum"))

        slug_val = _safe_str(data.get("slug"))
        market_url = f"https://polymarket.com/event/{slug_val}" if slug_val else ""

        return cls(
            id="polymarket_" + _safe_str(data.get("id")),
            question=_safe_str(data.get("question")),
            slug=slug_val,
            description=_safe_str(data.get("description")),
            outcomes=parsed_outcomes_list,
            outcome_prices=(
                parsed_outcome_prices_list
                if any(p is not None for p in parsed_outcome_prices_list)
                else None
            ),
            formatted_outcomes=formatted_outcomes_str,
            url=market_url,
            total_volume=total_volume,
            liquidity=liquidity,
            end_date=BaseMarket.parse_datetime_flexible(data.get("endDate")),
            created_at=BaseMarket.parse_datetime_flexible(data.get("createdAt")),
            updated_at=BaseMarket.parse_datetime_flexible(data.get("updatedAt")),
            active=bool(data.get("active", False)),
            closed=bool(data.get("closed", False)),
            resolution_source=(
                _safe_str(data.get("resolutionSource"))
                if data.get("resolutionSource")
                else None
            ),
            raw_market_type=_safe_str(
                data.get("category"),
            ),
        )

    def to_pooled_market(self) -> PooledMarket:
        """Convert PolymarketMarket to PooledMarket."""
        # Determine original_market_type based on raw_market_type or outcomes
        market_type = self.raw_market_type
        if not market_type:
            if len(self.outcomes) == 2:
                # Basic check for common binary outcome names (case-insensitive)
                norm_outcomes = [o.lower() for o in self.outcomes]
                if ("yes" in norm_outcomes and "no" in norm_outcomes) or (
                    "true" in norm_outcomes and "false" in norm_outcomes
                ):
                    market_type = "BINARY"
                else:
                    market_type = (
                        "CATEGORICAL"  # Or other generic term for 2-outcome non-binary
                    )
            elif len(self.outcomes) > 2:
                market_type = "CATEGORICAL"  # Multiple choice
            else:
                market_type = "UNKNOWN"  # Or None

        return PooledMarket(
            id=self.id,
            question=self.question,
            outcomes=self.outcomes,
            outcome_probabilities=(
                self.outcome_prices
                if self.outcome_prices
                else [None] * len(self.outcomes)
            ),
            formatted_outcomes=self.formatted_outcomes,
            url=self.url,
            published_at=self.created_at,  # Use created_at as published_at
            source_platform="Polymarket",
            volume=self.total_volume,
            n_forecasters=None,  # Not available in the Polymarket API data struct
            comments_count=None,  # Not directly available
            original_market_type=market_type,
            is_resolved=self.closed,
            raw_market_data=self,
        )


class PolymarketGammaScraper(BaseScraper):
    """Scraper for Polymarket Gamma markets."""

    BASE_URL = GAMMA_API_BASE_URL
    LIMIT_PER_PAGE = 500

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _fetch_page_data(self, limit: int, offset: int) -> list[dict[str, Any]]:
        if not self.session:
            self.session = aiohttp.ClientSession()

        params = {"limit": limit, "offset": offset}
        try:
            async with self.session.get(
                f"{self.BASE_URL}/markets",
                params=params,
                timeout=self.timeout,
            ) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError:
            return []
        except json.JSONDecodeError:
            return []

    # Note: Async, but internal calls are effectively synchronous due to fetch_page_data
    async def _fetch_all_raw_markets(
        self,
        max_requests: int = 200,
    ) -> list[dict[str, Any]]:
        all_raw_market_data: list[dict[str, Any]] = []
        offset = 0

        # tqdm is not async-friendly by default, consider alternatives or careful
        # usage in async.
        # For this refactor, keeping it but noting potential issues in highly
        # concurrent scenarios.
        for i in tqdm(range(max_requests), desc="Fetching Polymarket pages"):
            raw_data_list = await self._fetch_page_data(
                limit=self.LIMIT_PER_PAGE,
                offset=offset,
            )
            if not raw_data_list:
                break
            all_raw_market_data.extend(raw_data_list)
            if len(raw_data_list) < self.LIMIT_PER_PAGE:
                break
            offset += self.LIMIT_PER_PAGE
            if i == max_requests - 1:
                pass
        return all_raw_market_data

    async def fetch_markets(
        self,
        only_open: bool = True,
        min_volume: float = DEFAULT_MARKET_FILTER.min_volume,
        **kwargs: Any,
    ) -> list[PolymarketMarket]:
        """Fetch markets from Polymarket Gamma API and parse them into PolymarketMarket
        objects.

        Args:
            only_open: Whether to return only open markets (where closed is False).
            min_volume: Minimum volume to include in the returned markets, in USD.
            **kwargs: Supports 'max_requests' (int, default 200) and
                      'limit_per_page' (int, default 100).

        Returns:
            A list of PolymarketMarket objects.
        """
        max_requests = kwargs.get("max_requests", 200)

        raw_markets_data = await self._fetch_all_raw_markets(max_requests=max_requests)

        parsed_markets: list[PolymarketMarket] = []
        if not raw_markets_data:
            # print("No raw market data fetched from Gamma API.")
            return []

        for market_data_dict in raw_markets_data:
            try:
                market_obj = PolymarketMarket.from_api_data(market_data_dict)
                if only_open and market_obj.closed:
                    continue

                if market_obj.total_volume < min_volume:
                    continue

                parsed_markets.append(market_obj)

            except Exception:
                pass

        # print(f"Successfully parsed {len(parsed_markets)} markets.")
        return parsed_markets


if __name__ == "__main__":
    import asyncio  # For async main

    async def _run_polymarket_scraper() -> None:
        scraper = PolymarketGammaScraper()
        fetch_active = True
        time.time()

        polymarket_list = await scraper.fetch_markets(
            only_open=fetch_active,
        )

        time.time()

        if polymarket_list:
            pooled_markets = await scraper.get_pooled_markets()

            if pooled_markets:
                pass
            else:
                pass
        else:
            pass

    asyncio.run(_run_polymarket_scraper())
