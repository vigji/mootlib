import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from mootlib.scrapers.common_markets import PooledMarket
from mootlib.scrapers.gjopen import GoodJudgmentOpenScraper
from mootlib.scrapers.manifold_markets import ManifoldScraper
from mootlib.scrapers.metaculus import MetaculusScraper
from mootlib.scrapers.polymarket_gamma import PolymarketGammaScraper
from mootlib.scrapers.predictit import PredictItScraper


def _save_markets_to_cache(markets: list[PooledMarket], platform: str) -> Path:
    """Save markets to a cache file with timestamp."""
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cache_file = cache_dir / f"{platform}_{timestamp}.json"

    # Convert markets to dict, handling datetime serialization
    market_dicts = []
    for market in markets:
        market_dict = market.__dict__.copy()
        market_dict.pop("raw_market_data", None)

        # Convert datetime to string if present
        if "published_at" in market_dict and market_dict["published_at"] is not None:
            market_dict["published_at"] = market_dict["published_at"].isoformat()

        market_dicts.append(market_dict)

    with cache_file.open("w") as f:
        json.dump(market_dicts, f, indent=2)

    return cache_file


async def _fetch_platform_markets(
    scraper,
    only_open: bool,
) -> tuple[str, list[PooledMarket]]:
    """Fetch markets from a single platform."""
    platform_name = scraper.__class__.__name__.replace("Scraper", "")
    time.time()

    try:
        async with scraper:  # Use async context manager for proper session handling
            markets = await scraper.get_pooled_markets(only_open=only_open)

            # Save to cache
            _save_markets_to_cache(markets, platform_name)

            time.time()
            return platform_name, markets
    except Exception:
        return platform_name, []


async def _fetch_all_markets(only_open: bool = True) -> list[PooledMarket]:
    """Fetch markets from all available platforms in parallel.

    Args:
        only_open: If True, fetches only open markets.

    Returns:
        List of PooledMarket objects from all platforms.
    """
    scrapers = [
        GoodJudgmentOpenScraper(),
        ManifoldScraper(),
        PolymarketGammaScraper(),
        PredictItScraper(),
        MetaculusScraper(),
    ]

    # Fetch from all platforms in parallel
    results = await asyncio.gather(
        *[_fetch_platform_markets(scraper, only_open) for scraper in scrapers],
        return_exceptions=True,  # Handle exceptions gracefully
    )

    # Combine results, handling any exceptions
    all_markets: list[PooledMarket] = []
    for result in results:
        if isinstance(result, Exception):
            continue
        platform_name, markets = result
        all_markets.extend(markets)

    return all_markets


def _create_markets_dataframe(markets: list[PooledMarket]) -> pd.DataFrame:
    """Convert a list of PooledMarket objects to a pandas DataFrame.

    Args:
        markets: List of PooledMarket objects.

    Returns:
        DataFrame with all market data.
    """
    # Convert to list of dicts, excluding raw_market_data
    market_dicts = []
    for market in markets:
        market_dict = market.__dict__.copy()
        market_dict.pop(
            "raw_market_data",
            None,
        )  # Remove raw data to keep DataFrame clean
        market_dicts.append(market_dict)

    all_markets_df = pd.DataFrame(market_dicts)
    all_markets_df = all_markets_df.drop_duplicates(subset=["question"])
    # Handle published_at column if it exists
    if "published_at" in all_markets_df.columns:
        try:
            # First convert all to datetime, handling timezone-aware and naive
            all_markets_df["published_at"] = pd.to_datetime(
                all_markets_df["published_at"]
            )

            # Then convert all to timezone-naive
            all_markets_df["published_at"] = all_markets_df["published_at"].apply(
                lambda x: x.tz_localize(None) if x.tz is not None else x,
            )

            all_markets_df = all_markets_df.sort_values("published_at", ascending=False)
        except Exception:
            pass

    return all_markets_df


def fetch_markets_df() -> None:
    """Main function to run the market aggregation."""
    time.time()

    # Fetch markets from all platforms
    all_markets = asyncio.run(_fetch_all_markets(only_open=True))

    # Create DataFrame
    markets_df = _create_markets_dataframe(all_markets)

    time.time()

    # Print summary by platform

    # Save to CSV
    # output_path = Path("data/combined_markets.csv")
    # output_path.parent.mkdir(parents=True, exist_ok=True)
    # markets_df.to_csv(output_path, index=False)

    # Print sample of the data
    return markets_df


if __name__ == "__main__":
    markets_df = fetch_markets_df()
    print(markets_df)
