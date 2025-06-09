import hashlib
import os
from collections.abc import Sequence
from pathlib import Path

import dotenv
import numpy as np
import pandas as pd
from openai import OpenAI
from tqdm import tqdm

from mootlib.embeddings.remote_cache import get_remote_cache
from mootlib.utils.config import get_release_file_url

model = "BAAI/bge-m3"
EMBEDDING_DIM = 1024  # BGE-M3 embedding dimension
MAX_CHUNK_SIZE = 1024

# Create an OpenAI client with your deepinfra token and endpoint
openai = OpenAI(
    api_key=os.getenv("DEEPINFRA_TOKEN"),
    base_url="https://api.deepinfra.com/v1/openai",
)

dotenv.load_dotenv(Path(__file__).parent.parent / ".env")
os.getenv("DEEPINFRA_TOKEN")


def compute_string_hash(text: str) -> str:
    """Compute a hash for a single string."""
    return hashlib.sha256(text.strip().encode()).hexdigest()


class EmbeddingsCache:
    """Cache for embeddings."""

    def __init__(
        self,
        cache_path: Path | None = None,
        model: str = "BAAI/bge-m3",
        embedding_dim: int = 1024,
        chunk_size: int = 1024,
        use_remote: bool = True,
    ):
        """Initialize embeddings cache.

        Args:
            cache_path: Path to cache file. If None, uses default path.
            model: Model to use for embeddings.
            embedding_dim: Dimension of embeddings.
            chunk_size: Maximum chunk size for batch processing.
            use_remote: Whether to try fetching remote cache first.
        """
        if cache_path is None:
            cache_path = (
                Path(__file__).parent / "embeddings_cache" / "embeddings.parquet"
            )
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        self.model = model
        self.embedding_dim = embedding_dim
        self.chunk_size = chunk_size

        # Try to load cache in order: local file, remote cache, create new
        self.cache_df = None

        if self.cache_path.exists():
            self.cache_df = pd.read_parquet(self.cache_path)
        elif use_remote:
            release_url = get_release_file_url("embeddings.parquet.encrypted")
            print(f"Fetching remote cache from {release_url}")
            self.cache_df = get_remote_cache(release_url)
            if self.cache_df is not None:
                self.save_cache()

        if self.cache_df is None:
            self.cache_df = pd.DataFrame(
                columns=["text_hash", "text", "embedding"]
            ).set_index("text_hash")
            self.save_cache()

    def save_cache(self):
        """Save cache to disk."""
        self.cache_df.to_parquet(self.cache_path)

    def _embed_batch(self, texts: Sequence[str]) -> np.ndarray:
        """Embed a batch of texts using the model."""
        if not texts:
            return np.array([])

        embeddings = openai.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float",
        )
        return np.array([embedding.embedding for embedding in embeddings.data])

    def _embed_texts(self, texts: Sequence[str]) -> np.ndarray:
        """Embed texts, potentially in chunks."""
        if not texts:
            return np.array([])

        if len(texts) <= self.chunk_size:
            return self._embed_batch(texts)

        # Process in chunks
        embeddings_list = []
        for i in tqdm(range(0, len(texts), self.chunk_size)):
            chunk = texts[i : i + self.chunk_size]
            chunk_embeddings = self._embed_batch(chunk)
            embeddings_list.append(chunk_embeddings)

        return np.vstack(embeddings_list)

    def get_embeddings(
        self, texts: Sequence[str], update_cache: bool = True
    ) -> np.ndarray:
        """Get embeddings for texts, using cache and updating it if needed."""
        texts = [t.strip() for t in texts]
        text_hashes = [compute_string_hash(t) for t in texts]

        # Find which texts need to be embedded
        uncached_mask = [h not in self.cache_df.index for h in text_hashes]
        texts_to_embed = [
            t
            for t, needs_embed in zip(texts, uncached_mask, strict=False)
            if needs_embed
        ]

        # Embed new texts if any and update cache
        if texts_to_embed and update_cache:
            new_embeddings = self._embed_texts(texts_to_embed)
            new_hashes = [compute_string_hash(t) for t in texts_to_embed]

            new_entries = pd.DataFrame(
                {
                    "text_hash": new_hashes,
                    "text": texts_to_embed,
                    "embedding": list(new_embeddings),
                }
            ).set_index("text_hash")

            self.cache_df = pd.concat([self.cache_df, new_entries])
            self.save_cache()

        # Return embeddings in original order
        return np.array(
            [
                self.cache_df.loc[h, "embedding"]
                if h in self.cache_df.index
                else self._embed_texts([t])[0]
                for h, t in zip(text_hashes, texts, strict=False)
            ]
        )

    def embed_df(
        self,
        df: pd.DataFrame,
        text_column: str,
        update_cache: bool = True,
    ) -> pd.DataFrame:
        """Embed texts from a DataFrame column."""
        texts = df[text_column].tolist()
        embeddings = self.get_embeddings(texts, update_cache=update_cache)
        return pd.DataFrame(embeddings, index=df.index)


if __name__ == "__main__":
    from pathlib import Path
    from time import time

    from mootlib.utils.config import get_release_file_url
    from mootlib.utils.encryption import decrypt_to_df

    # Load encrypted data
    markets_file = Path(__file__).parent.parent.parent / "markets.csv.encrypted"
    markets_df = decrypt_to_df(markets_file)

    # Initialize cache
    cache = EmbeddingsCache()

    # First run - should compute all embeddings
    print("\nFirst run - computing and caching embeddings...")
    t0 = time()
    embeddings_df = cache.embed_df(markets_df, "question")
    print(f"First run took {time() - t0:.2f} seconds")
    print(f"Embedded {len(markets_df)} questions")
    print(f"Cache size: {len(cache.cache_df)} entries")

    # Second run - should use cache
    print("\nSecond run - should use cache...")
    t0 = time()
    embeddings_df_2 = cache.embed_df(markets_df, "question")
    print(f"Second run took {time() - t0:.2f} seconds")

    # Verify results are identical
    print("\nVerifying results...")
    assert (embeddings_df == embeddings_df_2).all().all(), "Cache differences!"
    print("Success! Both runs produced identical embeddings")
