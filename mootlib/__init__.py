"""A library for scraping and analyzing forecasting markets."""

from importlib import metadata

try:
    __version__ = metadata.version("mootlib")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"

from mootlib.scrapers.aggregate import fetch_markets_df
from mootlib.scrapers.common_markets import BaseScraper, MarketFilter, PooledMarket
from mootlib.scrapers.gjopen import GoodJudgmentOpenScraper
from mootlib.scrapers.manifold_markets import ManifoldScraper
from mootlib.scrapers.polymarket_gamma import PolymarketGammaScraper
from mootlib.scrapers.predictit import PredictItScraper

__all__ = [
    "BaseScraper",
    "GoodJudgmentOpenScraper",
    "ManifoldScraper",
    "MarketFilter",
    "PolymarketGammaScraper",
    "PooledMarket",
    "PredictItScraper",
    "fetch_markets_df",
]
