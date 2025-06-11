r"""Main API for Mootlib - a library for finding similar prediction market questions.

This module provides the main interface for interacting with Mootlib. It allows users
to:
- Find similar questions across multiple prediction market platforms
- Access historical market data and embeddings
- Compare questions using semantic similarity

Example:
    >>> from mootlib import MootlibMatcher
    >>> matcher = MootlibMatcher()
    >>> similar = matcher.find_similar_questions(
    ...     "Will Russia invade Moldova in 2024?", n_results=3, min_similarity=0.7
    ... )
    >>> for q in similar:
    ...     print(f"\\n{q}")
    >>> # Access raw dataframes
    >>> markets_df = matcher.markets_df
    >>> embeddings_df = matcher.embeddings_df

The matcher automatically handles:
- Downloading and caching market data from GitHub releases
- Managing temporary storage with configurable duration
- Semantic similarity computation using embeddings
"""

import os
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from mootlib.embeddings.embedding_utils import EmbeddingsCache
from mootlib.utils.config import get_release_file_url
from mootlib.utils.encryption import decrypt_to_df


@dataclass
class SimilarQuestion:
    """A dataclass representing a similar question with its metadata.

    This class provides a structured way to access information about similar
    questions
    found in prediction markets.

    Attributes:
        question: The text of the prediction market question.
        similarity_score: How similar this question is to the query (0-1).
        source_platform: The platform where this question was found (e.g., "Manifold",
        "Metaculus").
        formatted_outcomes: String representation of possible outcomes and
        their probabilities.
        url: Optional URL to the original market.
        n_forecasters: Optional number of people who made predictions.
        volume: Optional trading volume or liquidity.
        published_at: Optional datetime when the market was published.
    """

    question: str
    similarity_score: float
    source_platform: str
    formatted_outcomes: str
    url: str | None = None
    n_forecasters: int | None = None
    volume: float | None = None
    published_at: datetime | None = None

    def __str__(self) -> str:
        """Format the similar question for display."""
        parts = [
            f"Question: {self.question}",
            f"Platform: {self.source_platform}",
            f"Outcomes: {self.formatted_outcomes}",
            f"Similarity: {self.similarity_score:.3f}",
        ]
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.n_forecasters:
            parts.append(f"Forecasters: {self.n_forecasters}")
        if self.volume:
            parts.append(f"Volume: {self.volume:.2f}")
        if self.published_at:
            parts.append(f"Published: {self.published_at.strftime('%Y-%m-%d')}")
        return "\n".join(parts)


class MootlibMatcher:
    r"""Main interface for finding similar questions across prediction markets.

    This class provides the primary API for Mootlib. It handles:
    - Downloading and caching market data from GitHub releases
    - Computing semantic similarity between questions
    - Managing temporary storage with configurable duration
    - Providing access to raw market data and embeddings

    The matcher uses a local temporary directory to store downloaded market data.
    This data is automatically refreshed when it becomes stale (default: 30 minutes).

    Example:
        >>> matcher = MootlibMatcher()
        >>> # Find similar questions
        >>> similar = matcher.find_similar_questions(" SpaceX reach Mars by 2025?",
        >>>                                          n_results=3)
        >>> for q in similar:
        ...     print(f"\\n{q}")
        >>> # Access raw dataframes
        >>> markets_df = matcher.markets_df  # Get all market data
        >>> embeddings_df = matcher.embeddings_df  # Get question embeddings

    Note:
        Requires the MOOTLIB_ENCRYPTION_KEY environment variable to be set
        for decrypting market data.
    """

    TEMP_DIR = Path(tempfile.gettempdir()) / "mootlib"

    def __init__(
        self,
        cache_duration_minutes: int = 30,
    ):
        """Initialize the MootlibMatcher.

        Args:
            cache_duration_minutes: How long to keep the data in memory and cache.
                After this duration, fresh data will be downloaded from GitHub.
                Defaults to 30 minutes.

        Raises:
            ValueError: If MOOTLIB_ENCRYPTION_KEY environment variable is not set.
        """
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.last_refresh: datetime | None = None
        self._markets_df: pd.DataFrame | None = None
        self.embeddings_cache = EmbeddingsCache()

        # Ensure we have the encryption key
        if not os.getenv("MOOTLIB_ENCRYPTION_KEY"):
            raise ValueError(
                "MOOTLIB_ENCRYPTION_KEY environment variable must be set for decryption"
            )

        # Create temp directory if it doesn't exist
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.markets_file = self.TEMP_DIR / "markets.parquet.encrypted"

    @property
    def markets_df(self) -> pd.DataFrame:
        """Get the current markets DataFrame.

        Returns:
            A pandas DataFrame containing all market data, with columns including:
            - question: The market question text
            - source_platform: Platform where the market is from
            - formatted_outcomes: Current probabilities/outcomes
            - url: Link to the original market
            - n_forecasters: Number of forecasters
            - volume: Trading volume/liquidity
            - published_at: Publication datetime

        Note:
            Automatically downloads fresh data if the cache is stale.
        """
        self._ensure_fresh_data()
        if self._markets_df is None:
            raise RuntimeError("Failed to load markets data")
        return self._markets_df

    @property
    def embeddings_df(self) -> pd.DataFrame:
        """Get the embeddings DataFrame.

        Returns:
            A pandas DataFrame containing question embeddings, with columns:
            - text: The question text
            - embedding: The numerical embedding vector

        Note:
            Embeddings are computed on-demand and cached for future use.
        """
        return self.embeddings_cache.cache_df

    def _download_markets_file(self) -> None:
        """Download the markets file from GitHub releases."""
        release_url = get_release_file_url("markets.parquet.encrypted")
        print(
            f"Downloading markets file from {release_url} to"
            f" {self.markets_file}"
        )
        urllib.request.urlretrieve(release_url, self.markets_file)

    def _is_cache_valid(self) -> bool:
        """Check if the cached file is still valid."""
        if not self.markets_file.exists():
            return False

        file_mtime = datetime.fromtimestamp(self.markets_file.stat().st_mtime)
        return datetime.now() - file_mtime <= self.cache_duration

    def _ensure_fresh_data(self) -> None:
        """Ensure we have fresh market data loaded."""
        now = datetime.now()

        # Check if we need to refresh the DataFrame
        if (
            self._markets_df is None
            or self.last_refresh is None
            or now - self.last_refresh > self.cache_duration
        ):
            # Check if we need to download new data
            if not self._is_cache_valid():
                self._download_markets_file()

            self._markets_df = decrypt_to_df(self.markets_file, format="parquet")
            self.last_refresh = now

    def find_similar_questions(
        self,
        query: str,
        n_results: int = 5,
        min_similarity: float = 0.5,
        exclude_platforms: list[str] | None = None,
    ) -> list[SimilarQuestion]:
        r"""Find questions similar to the query across all prediction markets.

        This method searches through all available prediction market questions
        to find those most semantically similar to your query. It uses
        embeddings to compute similarity scores.

        Args:
            query: The question to find similar matches for.
                Example: "Will Russia invade another country in 2024?"
            n_results: Number of similar questions to return.
                Defaults to 5.
            min_similarity: Minimum similarity score (0-1) for returned questions.
                Higher values mean more similar results.
                Defaults to 0.5.
            exclude_platforms: List of platforms to exclude from the search.
                Defaults to None.

        Returns:
            A list of SimilarQuestion objects, sorted by similarity
            (most similar first).

        Example:
            >>> matcher = MootlibMatcher()
            >>> similar = matcher.find_similar_questions(
            ...     "Will Tesla stock reach $300 in 2024?",
            ...     n_results=3,
            ...     min_similarity=0.7,
            ...     exclude_platforms=["Manifold"],
            ... )
            >>> for q in similar:
            ...     print(f"\\n{q}")
        """
        if exclude_platforms is None:
            exclude_platforms = []
        self._ensure_fresh_data()
        if not self._markets_df is not None:
            raise RuntimeError("Failed to load markets data")

        # Get embeddings for the query and all questions
        query_embedding = self.embeddings_cache.get_embeddings([query])[0]
        all_embeddings = self.embeddings_cache.get_embeddings(
            self._markets_df["question"].tolist()
        )

        # Calculate similarities
        similarities = cosine_similarity([query_embedding], all_embeddings)[0]

        # Get indices of top matches above minimum similarity
        valid_indices = np.where(similarities >= min_similarity)[0]
        top_indices = valid_indices[
            np.argsort(-similarities[valid_indices])  # [:n_results]
        ]

        # Create SimilarQuestion objects for each match
        similar_questions = []
        for idx in top_indices:
            row = self._markets_df.iloc[idx]
            published_at = row.get("published_at")

            if row["source_platform"] in exclude_platforms:
                continue

            similar_questions.append(
                SimilarQuestion(
                    question=row["question"],
                    similarity_score=float(similarities[idx]),
                    source_platform=row["source_platform"],
                    formatted_outcomes=row["formatted_outcomes"],
                    url=row.get("url"),
                    n_forecasters=row.get("n_forecasters"),
                    volume=row.get("volume"),
                    published_at=published_at,
                )
            )

            if len(similar_questions) >= n_results:
                break

        return similar_questions


if __name__ == "__main__":
    # Example usage
    matcher = MootlibMatcher()
    query = "Will Russia invade another country in 2024?"
    similar = matcher.find_similar_questions(
        query,
        n_results=3,  # exclude_platforms=["Manifold"]
    )
    for q in similar:
        print(f"\n{q}\n{'-' * 80}")
