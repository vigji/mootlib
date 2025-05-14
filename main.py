import os
from pathlib import Path

from dotenv import load_dotenv

from mootlib.embeddings.embedding_utils import EmbeddingsCache
from mootlib.scrapers.aggregate import fetch_markets_df
from mootlib.utils.encryption import encrypt_dataframe

load_dotenv()

assert (
    os.getenv("MOOTLIB_ENCRYPTION_KEY") is not None
), "MOOTLIB_ENCRYPTION_KEY is not set"
assert os.getenv("DEEPINFRA_TOKEN") is not None, "DEEPINFRA_TOKEN is not set"

if __name__ == "__main__":
    # Create data directory if needed
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Initialize embeddings cache with remote support
    print("Initializing embeddings cache...")
    cache = EmbeddingsCache(use_remote=True)
    print(f"Loaded {len(cache.cache_df)} existing embeddings from cache")

    # Fetch and save markets data
    markets_df = fetch_markets_df()
    print(f"Fetched {len(markets_df)} markets")

    # Compute embeddings (will use cache for existing questions)
    print("Computing embeddings...")
    _ = cache.embed_df(markets_df, "question")
    print("Done computing embeddings")

    # Save and encrypt markets data
    raw_path = data_dir / "markets.parquet"
    encrypted_path = Path("markets.parquet.encrypted")

    # Save and encrypt markets
    markets_df.to_parquet(raw_path)
    encrypt_dataframe(markets_df, encrypted_path)

    # Save and encrypt embeddings cache
    raw_cache_path = data_dir / "embeddings.parquet"
    encrypted_cache_path = Path("embeddings.parquet.encrypted")

    cache.cache_df.to_parquet(raw_cache_path)
    encrypt_dataframe(cache.cache_df, encrypted_cache_path)

    # Clean up raw files
    raw_path.unlink()
    raw_cache_path.unlink()

    print(f"Encrypted files ready at: {encrypted_path} and {encrypted_cache_path}")
    print("\nTo release, run:")
    print("gh release delete latest -y || true")
    print(
        f"gh release create latest {encrypted_path} {encrypted_cache_path} --title"
        "'Latest Encrypted Markets' --notes 'Auto-uploaded'"
    )
