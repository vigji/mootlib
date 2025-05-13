r"""Mootlib - A library for finding similar prediction market questions.

This library provides tools to search and compare questions across multiple
prediction market platforms including Manifold, Metaculus, Polymarket, and more.

Example:
    >>> from mootlib import MootlibMatcher
    >>> matcher = MootlibMatcher()
    >>> similar = matcher.find_similar_questions(
    ...     "Will Russia invade Moldova in 2024?", n_results=3
    ... )
    >>> for q in similar:
    ...     print(f"\\n{q}")
"""

from importlib import metadata

from mootlib.embeddings.question_matcher import MootlibMatcher, SimilarQuestion

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
    "MootlibMatcher",
    "PolymarketGammaScraper",
    "PooledMarket",
    "PredictItScraper",
    "SimilarQuestion",
    "fetch_markets_df",
]
