import asyncio
import logging
from zoneinfo import ZoneInfo

import pandas as pd

from mootlib.scrapers.common_markets import PooledMarket
from mootlib.scrapers.gjopen import GoodJudgmentOpenScraper
from mootlib.scrapers.manifold_markets import ManifoldScraper
from mootlib.scrapers.metaculus import MetaculusScraper
from mootlib.scrapers.polymarket_gamma import PolymarketGammaScraper
from mootlib.scrapers.predictit import PredictItScraper

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _fetch_platform_markets(
    scraper,
    only_open: bool,
) -> tuple[str, list[PooledMarket]]:
    """Fetch markets from a single platform."""
    platform_name = scraper.__class__.__name__.replace("Scraper", "")
    logger.info(f"Starting market fetch for {platform_name}")

    try:
        async with scraper:  #  async context manager for proper session handling
            markets = await scraper.get_pooled_markets(only_open=only_open)
            logger.info(f"Fetched {len(markets)} markets from {platform_name}")
            return platform_name, markets
    except Exception as e:
        logger.error(
            f"Failed to fetch markets from {platform_name}",
            exc_info=True,
            extra={"error": str(e)},
        )
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

    logger.info(f"Starting parallel fetch for {len(scrapers)} platforms")

    # Fetch from all platforms in parallel
    results = await asyncio.gather(
        *[_fetch_platform_markets(scraper, only_open) for scraper in scrapers],
        return_exceptions=True,  # Handle exceptions gracefully
    )

    # Combine results, handling any exceptions
    all_markets: list[PooledMarket] = []
    failed_platforms = []

    for result in results:
        if isinstance(result, Exception):
            logger.error("Unexpected error during market fetch", exc_info=result)
            continue

        platform_name, markets = result
        if not markets:  # Empty list indicates failure in _fetch_platform_markets
            failed_platforms.append(platform_name)
        else:
            all_markets.extend(markets)
            logger.info(f"Added {len(markets)} markets from {platform_name}")

    if failed_platforms:
        logger.warning(f"Failed to fetch markets from: {', '.join(failed_platforms)}")

    logger.info(f"Successfully fetched {len(all_markets)} markets in total")
    return all_markets


def _create_markets_dataframe(markets: list[PooledMarket]) -> pd.DataFrame:
    """Convert a list of PooledMarket objects to a pandas DataFrame.

    Args:
        markets: List of PooledMarket objects.

    Returns:
        DataFrame with all market data.
    """
    market_dicts = [
        {k: v for k, v in market.__dict__.items() if k != "raw_market_data"}
        for market in markets
    ]

    all_markets_df = pd.DataFrame(market_dicts)
    all_markets_df = all_markets_df.drop_duplicates(subset=["question"])

    # Handle published_at column if it exists
    if "published_at" in all_markets_df.columns:
        try:
            # Convert to datetime, force timezone to ET if naive
            all_markets_df["published_at"] = pd.to_datetime(
                all_markets_df["published_at"],
                utc=True,  # First convert everything to UTC
                errors="coerce",  # Handle invalid dates gracefully
            ).dt.tz_convert(ZoneInfo("America/New_York"))

            all_markets_df = all_markets_df.sort_values("published_at", ascending=False)

        except Exception as e:
            logger.warning(
                "Failed to process published_at dates",
                exc_info=True,
                extra={"error": str(e)},
            )

    return all_markets_df


def fetch_markets_df() -> pd.DataFrame:
    """Main function to run the market aggregation."""
    logger.info("Starting market aggregation")

    # Fetch markets from all platforms
    all_markets = asyncio.run(_fetch_all_markets(only_open=True))

    # Create DataFrame
    markets_df = _create_markets_dataframe(all_markets)
    logger.info(f"Created DataFrame with {len(markets_df)} unique markets")

    return markets_df


if __name__ == "__main__":
    markets_df = fetch_markets_df()
    print(markets_df)
