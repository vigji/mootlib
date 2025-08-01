import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
from tqdm import tqdm

from mootlib.scrapers.common_markets import BaseScraper, MarketFilter, PooledMarket

DEFAULT_MARKET_FILTER = MarketFilter(min_n_forecasters=50)


@dataclass
class ManifoldAnswer:
    """Dataclass for Manifold answers."""

    text: str
    probability: float
    volume: float
    number_of_bets: int
    created_time: datetime

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> "ManifoldAnswer":
        """Create a ManifoldAnswer from API data."""
        return cls(
            text=data["text"],
            probability=data.get("probability", 0),
            volume=data.get("volume", 0),
            number_of_bets=len(data.get("bets", [])),
            created_time=datetime.fromtimestamp(data["createdTime"] / 1000),
        )


@dataclass
class ManifoldMarket:
    """Unified class for Manifold markets, handling different outcome types."""

    id: str
    question: str
    outcome_type: str
    created_time: datetime
    creator_name: str
    creator_username: str
    slug: str
    volume: float
    unique_bettor_count: int
    total_liquidity: float
    close_time: datetime | None
    last_updated_time: datetime
    tags: list[str]
    group_slugs: list[str]
    visibility: str
    resolution: str | None
    resolution_time: datetime | None
    outcomes: list[str]
    outcome_prices: list[float]
    formatted_outcomes: str
    # Binary specific
    probability: float | None = None
    initial_probability: float | None = None
    p: float | None = None
    total_shares: float | None = None
    pool: float | None = None
    # Multi-choice specific
    answers: list[ManifoldAnswer] | None = None

    def get_url(self) -> str:
        """Get the URL for the market."""
        return f"https://manifold.markets/{self.creator_username}/{self.slug}"

    def __str__(self) -> str:
        return f"{self.question} ({self.outcome_type})"

    @staticmethod
    def _format_outcomes(outcomes: list[str], prices: list[float]) -> str:
        """Format outcomes and prices into a string."""
        return "; ".join(
            [f"{o}: {(p * 100):.1f}%" for o, p in zip(outcomes, prices, strict=False)]
        )

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> "ManifoldMarket":
        """Create a ManifoldMarket from API data."""
        outcome_type = data["outcomeType"]

        outcomes = []
        outcome_prices = []
        probability = None
        initial_probability = None
        p_val = None
        total_shares = None
        pool_val = None
        answers_obj = None

        if outcome_type == "BINARY":
            probability = data.get("probability")
            initial_probability = data.get("initialProbability")
            p_val = data.get("p")
            total_shares = data.get("totalShares")
            pool_val = data.get("pool")
            outcomes = ["Yes", "No"]
            outcome_prices = [
                probability if probability is not None else 0.5,
                1 - probability if probability is not None else 0.5,
            ]
        elif outcome_type == "MULTIPLE_CHOICE":
            answers_data = data.get("answers", [])
            answers_obj = [ManifoldAnswer.from_api_data(ans) for ans in answers_data]
            outcomes = [ans.text for ans in answers_obj]
            outcome_prices = [ans.probability for ans in answers_obj]
        else:
            # Potentially handle other types or return None if unsupported
            return None

        formatted_outcomes_str = cls._format_outcomes(outcomes, outcome_prices)

        return cls(
            id="manifold_" + data["id"],
            question=data["question"],
            outcome_type=outcome_type,
            created_time=datetime.fromtimestamp(data["createdTime"] / 1000),
            creator_name=data["creatorName"],
            creator_username=data["creatorUsername"],
            slug=data["slug"],
            volume=data.get("volume", 0),
            unique_bettor_count=data.get("uniqueBettorCount", 0),
            total_liquidity=data.get("totalLiquidity", 0),
            close_time=(
                datetime.fromtimestamp(data["closeTime"] / 1000)
                if data.get("closeTime")
                else None
            ),
            last_updated_time=datetime.fromtimestamp(data["lastUpdatedTime"] / 1000),
            tags=data.get("tags", []),
            group_slugs=data.get("groupSlugs", []),
            visibility=data.get("visibility", "public"),
            resolution=data.get("resolution"),
            resolution_time=(
                datetime.fromtimestamp(data["resolutionTime"] / 1000)
                if data.get("resolutionTime")
                else None
            ),
            outcomes=outcomes,
            outcome_prices=outcome_prices,
            formatted_outcomes=formatted_outcomes_str,
            probability=probability,
            initial_probability=initial_probability,
            p=p_val,
            total_shares=total_shares,
            pool=pool_val,
            answers=answers_obj,
        )

    def to_pooled_market(self) -> PooledMarket:
        """Convert a ManifoldMarket to a PooledMarket."""
        is_res = bool(self.resolution and self.resolution != "MKT")

        return PooledMarket(
            id=self.id,
            question=self.question,
            outcomes=self.outcomes,
            outcome_probabilities=self.outcome_prices,
            formatted_outcomes=self.formatted_outcomes,
            url=f"https://manifold.markets/{self.creator_username}/{self.slug}",
            published_at=self.created_time,
            source_platform="Manifold",
            volume=self.volume,
            n_forecasters=self.unique_bettor_count,
            comments_count=None,
            original_market_type=self.outcome_type,
            is_resolved=is_res,
            raw_market_data=self,
        )


class ManifoldScraper(BaseScraper):
    """Scraper for Manifold markets."""

    LIMIT = 1000
    BASE_URL = "https://api.manifold.markets/v0/markets"
    BASE_URL_MARKET_DETAILS = "https://api.manifold.markets/v0/market"

    def __init__(self, max_concurrent: int = 5, api_key: str | None = None) -> None:
        self.max_concurrent = max_concurrent
        self.session: aiohttp.ClientSession | None = None
        self.api_key = api_key
        self.headers = {}
        if self.api_key:
            self.headers["Authorization"] = f"Key {self.api_key}"

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @staticmethod
    def _create_market(data: dict[str, Any]) -> ManifoldMarket | None:
        """Create appropriate market type from API data."""
        try:
            return ManifoldMarket.from_api_data(data)
        except Exception:
            return None

    async def _fetch_raw_markets_list(
        self,
        before: str | None = None,
        only_open: bool = True,
    ) -> list[dict[str, Any]]:
        """Fetch a list of markets from API, with optional pagination and open status
        filter.
        """
        params: dict[str, Any] = {
            "limit": self.LIMIT,
            "sort": "created-time",
            "order": "desc",
        }
        if before:
            params["before"] = before

        all_markets_batch = []
        try:
            async with self.session.get(
                self.BASE_URL,
                params=params,
                headers=self.headers,
            ) as response:
                response.raise_for_status()
                markets_page = await response.json()
                if not markets_page:
                    return []  # No more markets

                if only_open:
                    all_markets_batch = [
                        m for m in markets_page if not m.get("isResolved", False)
                    ]
                else:
                    all_markets_batch = markets_page

        except aiohttp.ClientError:
            return []
        return all_markets_batch

    async def _get_market_details(self, market_id: str) -> dict[str, Any] | None:
        """Fetch details for a specific market."""
        # Ensure we use the original ID for the API call
        original_id = market_id.replace("manifold_", "")
        base_url = f"{self.BASE_URL_MARKET_DETAILS}/{original_id}"
        try:
            async with self.session.get(base_url, headers=self.headers) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError:
            return None

    async def fetch_markets(
        self,
        only_open: bool = True,
        min_unique_bettors: int = DEFAULT_MARKET_FILTER.min_n_forecasters,
        min_volume: float = DEFAULT_MARKET_FILTER.min_volume,
        **kwargs: Any,
    ) -> list[ManifoldMarket]:
        """Get filtered markets that meet the criteria."""
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.headers)

        raw_markets_list_paginated: list[dict[str, Any]] = []
        last_market_id: str | None = None
        markets_fetched_count = 0

        while True:
            current_batch = await self._fetch_raw_markets_list(
                before=last_market_id,
                only_open=only_open,  # batch_limit,
            )
            if not current_batch:
                break
            raw_markets_list_paginated.extend(current_batch)
            markets_fetched_count += len(current_batch)

            last_market_id = current_batch[-1]["id"]
        if not raw_markets_list_paginated:
            return []

        markets_to_fetch_details_for_ids: list[str] = []
        for m_summary in raw_markets_list_paginated:
            if (
                (only_open and m_summary.get("isResolved", False))
                or m_summary.get("uniqueBettorCount", 0) < min_unique_bettors
                or m_summary.get("volume", 0) < min_volume
                or m_summary.get("outcomeType") not in ["BINARY", "MULTIPLE_CHOICE"]
            ):
                continue
            markets_to_fetch_details_for_ids.append(m_summary["id"])

        processed_markets: list[ManifoldMarket] = []
        for i in tqdm(
            range(0, len(markets_to_fetch_details_for_ids), self.max_concurrent),
            desc="Fetching Manifold market details",
        ):
            batch_ids = markets_to_fetch_details_for_ids[i : i + self.max_concurrent]
            tasks = [self._get_market_details(market_id) for market_id in batch_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for _market_id_original, full_data_or_exc in zip(
                batch_ids, results, strict=False
            ):
                if isinstance(full_data_or_exc, Exception) or not full_data_or_exc:
                    continue

                market_obj = self._create_market(full_data_or_exc)
                if market_obj:
                    if only_open and (
                        market_obj.resolution and market_obj.resolution != "MKT"
                    ):
                        continue
                    if (
                        market_obj.unique_bettor_count >= min_unique_bettors
                        and market_obj.volume >= min_volume
                    ):
                        processed_markets.append(market_obj)

        return processed_markets


if __name__ == "__main__":

    async def _main() -> None:
        async with ManifoldScraper(max_concurrent=5) as client:
            open_markets = await client.fetch_markets(
                only_open=True,
            )
            if open_markets:
                pass

                [m.to_pooled_market() for m in open_markets]

    asyncio.run(_main())
