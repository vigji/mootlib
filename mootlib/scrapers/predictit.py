import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from mootlib.scrapers.common_markets import BaseMarket, BaseScraper, PooledMarket


@dataclass
class PredictItContract:
    """PredictIt contract dataclass."""

    id: int
    name: str
    last_trade_price: float | None  # API can return null
    best_buy_yes_cost: float | None
    best_sell_yes_cost: float | None

    @property
    def spread(self) -> float | None:
        """Calculate the spread between the best buy and sell prices."""
        if self.best_buy_yes_cost is not None and self.best_sell_yes_cost is not None:
            val = self.best_buy_yes_cost - self.best_sell_yes_cost
            return val if val >= 0 else None  # Spread shouldn't be negative
        return None

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> "PredictItContract":
        """Create PredictItContract from API data."""
        return cls(
            id=data["id"],
            name=data["name"],
            last_trade_price=data.get("lastTradePrice"),
            best_buy_yes_cost=data.get("bestBuyYesCost"),
            best_sell_yes_cost=data.get("bestSellYesCost"),
        )


@dataclass
class PredictItMarket(BaseMarket):
    """PredictIt market dataclass."""

    id: str  # Changed to str for "predictit_" prefix
    name: str  # This is the question
    url: str
    contracts: list[PredictItContract]
    api_timestamp: str | None  # Timestamp from API (string)
    status: str | None  # Market status from API, e.g., "Open", "Closed"

    # Derived fields
    outcomes: list[str] = field(init=False)
    outcome_prices: list[float | None] = field(init=False)
    formatted_outcomes: str = field(init=False)

    def __post_init__(self):
        # This logic was part of from_api_data, moved to post_init for clarity
        if len(self.contracts) == 1:  # Binary market (Yes/No for a single statement)
            contract = self.contracts[0]
            self.outcomes = ["Yes", "No"]  # Assuming standard binary interpretation
            yes_price = (
                contract.last_trade_price
                if contract.last_trade_price is not None
                else None
            )
            if yes_price is not None:
                self.outcome_prices = [
                    yes_price,
                    1.0 - yes_price if yes_price <= 1 else 0.0,
                ]  # ensure 0-1 range
            else:
                self.outcome_prices = [None, None]
        elif len(self.contracts) > 1:  # Multiple contracts, each is an outcome
            self.outcomes = [c.name for c in self.contracts]
            raw_prices = [c.last_trade_price for c in self.contracts]

            # Normalize prices if they are actual probabilities that should sum to 1
            # PredictIt contract prices are 0-100 cents, representing probability * 100
            # If these are individual independent contracts, normalization might not
            # be appropriate.
            # For now, assume they are probabilities that should be normalized
            # for multi-outcome.
            valid_prices = [p for p in raw_prices if p is not None]
            if valid_prices:
                total_price_sum = sum(valid_prices)
                if total_price_sum > 0:
                    self.outcome_prices = [
                        (p / total_price_sum if p is not None else None)
                        for p in raw_prices
                    ]
                else:  # Avoid division by zero if all valid prices are 0
                    self.outcome_prices = [
                        0.0 if p is not None else None for p in raw_prices
                    ]
            else:  # All prices are None
                self.outcome_prices = [None] * len(self.contracts)
        else:  # No contracts, undefined market
            self.outcomes = []
            self.outcome_prices = []

        # Format outcomes string
        if (
            self.outcomes
            and self.outcome_prices
            and len(self.outcomes) == len(self.outcome_prices)
        ):
            self.formatted_outcomes = "; ".join(
                [
                    f"{o}: {(p * 100):.1f}%" if p is not None else f"{o}: N/A"
                    for o, p in zip(self.outcomes, self.outcome_prices, strict=False)
                ],
            )
        else:
            self.formatted_outcomes = "N/A"

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> "PredictItMarket":
        """Create PredictItMarket from API data."""
        contracts_data = data.get("contracts", [])
        parsed_contracts = [PredictItContract.from_api_data(c) for c in contracts_data]

        return cls(
            id="predictit_" + str(data["id"]),
            name=data["name"],
            url=data["url"],
            contracts=parsed_contracts,
            api_timestamp=data.get("timeStamp"),  # API uses "timeStamp"
            status=data.get("status"),
        )

    def to_pooled_market(self) -> PooledMarket:
        """Convert PredictItMarket to PooledMarket."""
        market_status_lower = self.status.lower() if self.status else ""
        is_res = market_status_lower == "closed"  # PredictIt uses "Closed"

        # Infer original market type
        if len(self.contracts) == 1:
            original_type = "BINARY"
        elif len(self.contracts) > 1:
            original_type = "CATEGORICAL"  # Or "MULTIPLE_CONTRACT"
        else:
            original_type = "UNKNOWN"

        return PooledMarket(
            id=self.id,
            question=self.name,  # Market name is the question
            outcomes=self.outcomes,
            outcome_probabilities=self.outcome_prices,
            formatted_outcomes=self.formatted_outcomes,
            url=self.url,
            published_at=BaseMarket.parse_datetime_flexible(
                self.api_timestamp,
            ),  # Using API timestamp as proxy
            source_platform="PredictIt",
            volume=None,  # No volume directly
            n_forecasters=None,  # Not available
            comments_count=None,  # Not available
            original_market_type=original_type,
            is_resolved=is_res,
            raw_market_data=self,
        )


class PredictItScraper(BaseScraper):
    """Scraper for PredictIt markets."""

    API_URL = "https://www.predictit.org/api/marketdata/all/"

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0 (compatible; PythonScraper/1.0)"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _fetch_raw_data(self) -> dict[str, Any] | None:
        """Fetch raw data from PredictIt API."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 (compatible; PythonScraper/1.0)"},
            )

        try:
            async with self.session.get(self.API_URL, timeout=self.timeout) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError:
            return None
        except json.JSONDecodeError:
            return None

    async def fetch_markets(
        self,
        only_open: bool = True,
        **kwargs: Any,
    ) -> list[PredictItMarket]:
        """Fetch markets from PredictIt API.

        Args:
            only_open: If True, returns only open markets.
            **kwargs: Additional parameters (currently unused for PredictIt).

        Returns:
            A list of PredictItMarket objects.
        """
        raw_response_data = await self._fetch_raw_data()
        if not raw_response_data:
            return []

        api_markets_data = raw_response_data.get("markets", [])
        parsed_markets: list[PredictItMarket] = []

        for market_data_dict in api_markets_data:
            try:
                market_obj = PredictItMarket.from_api_data(market_data_dict)
                if only_open:
                    if market_obj.status and market_obj.status.lower() != "closed":
                        parsed_markets.append(market_obj)
                else:
                    parsed_markets.append(market_obj)
            except Exception:
                pass

        return parsed_markets


if __name__ == "__main__":

    async def _main() -> None:
        scraper = PredictItScraper()

        fetch_only_open_markets = True
        time.time()

        predictit_market_list = await scraper.fetch_markets(
            only_open=fetch_only_open_markets,
        )
        time.time()

        if predictit_market_list:
            # Example of getting pooled markets using the BaseScraper method
            pooled_markets = await scraper.get_pooled_markets(
                only_open=fetch_only_open_markets,
            )

            if pooled_markets:
                pass
            else:
                pass
        else:
            pass

    asyncio.run(_main())
