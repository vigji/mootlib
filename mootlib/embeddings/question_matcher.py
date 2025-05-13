"""Provides functionality for finding similar questions in the market database."""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from mootlib.embeddings.embedding_utils import EmbeddingsCache
from mootlib.utils.encryption import decrypt_to_df


@dataclass
class SimilarQuestion:
    """A dataclass representing a similar question with its metadata."""

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


class QuestionMatcher:
    """A class for finding similar questions in the market database."""

    def __init__(
        self,
        markets_file: str | Path | None = None,
        cache_duration_minutes: int = 30,
    ):
        """Initialize the QuestionMatcher.

        Args:
            markets_file: Path to the encrypted markets file.
            If None, looks in default location.
            cache_duration_minutes: How long to keep the markets data in memory.
        """
        if not markets_file:
            markets_file = (
                Path(__file__).parent.parent.parent / "markets.parquet.encrypted"
            )

        self.markets_file = Path(markets_file)
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.last_refresh: datetime | None = None
        self.markets_df: pd.DataFrame | None = None
        self.embeddings_cache = EmbeddingsCache()

        # Ensure we have the encryption key
        if not os.getenv("MOOTLIB_ENCRYPTION_KEY"):
            raise ValueError(
                "MOOTLIB_ENCRYPTION_KEY environment variable must be set for decryption"
            )

    def _ensure_fresh_data(self) -> None:
        """Ensure we have fresh market data loaded."""
        now = datetime.now()
        if (
            self.markets_df is None
            or self.last_refresh is None
            or now - self.last_refresh > self.cache_duration
        ):
            # Try parquet first, fall back to csv for backward compatibility
            try:
                self.markets_df = decrypt_to_df(self.markets_file, format="parquet")
            except Exception:
                # If parquet fails, try csv as fallback
                csv_path = self.markets_file.with_suffix(".csv.encrypted")
                if csv_path.exists():
                    self.markets_df = decrypt_to_df(csv_path, format="csv")
                else:
                    raise FileNotFoundError(
                        "No valid markets file found at "
                        "{self.markets_file} or {csv_path}"
                    )

            # Convert published_at to datetime if it exists
            if "published_at" in self.markets_df.columns:
                self.markets_df["published_at"] = pd.to_datetime(
                    self.markets_df["published_at"],
                    utc=True,  # First convert everything to UTC
                ).dt.tz_convert("America/New_York")  # Then convert to ET

            self.last_refresh = now

    def find_similar_questions(
        self,
        query: str,
        n_results: int = 5,
        min_similarity: float = 0.5,
    ) -> list[SimilarQuestion]:
        """Find questions similar to the query.

        Args:
            query: The question to find similar matches for.
            n_results: Number of similar questions to return.
            min_similarity: Minimum similarity score (0-1) for returned questions.

        Returns:
            A list of SimilarQuestion objects, sorted by similarity
            (most similar first).
        """
        self._ensure_fresh_data()
        if not self.markets_df is not None:
            raise RuntimeError("Failed to load markets data")

        # Get embeddings for the query and all questions
        query_embedding = self.embeddings_cache.get_embeddings([query])[0]
        all_embeddings = self.embeddings_cache.get_embeddings(
            self.markets_df["question"].tolist()
        )

        # Calculate similarities
        similarities = cosine_similarity([query_embedding], all_embeddings)[0]

        # Get indices of top matches above minimum similarity
        valid_indices = np.where(similarities >= min_similarity)[0]
        top_indices = valid_indices[
            np.argsort(-similarities[valid_indices])[:n_results]
        ]

        # Create SimilarQuestion objects for each match
        similar_questions = []
        for idx in top_indices:
            row = self.markets_df.iloc[idx]
            published_at = row.get("published_at")
            # published_at is already handled in _ensure_fresh_data

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

        return similar_questions


if __name__ == "__main__":
    # Example usage
    matcher = QuestionMatcher()
    query = "Russia Ukraine ceasefire in 2025?"
    similar = matcher.find_similar_questions(query, n_results=3)
    for q in similar:
        print(f"\n{q}\n{'-' * 80}")
