import os
from pathlib import Path

from dotenv import load_dotenv

from mootlib.embeddings.embedding_utils import EmbeddingsCache
from mootlib.scrapers.aggregate import fetch_markets_df
from mootlib.utils.encryption import decrypt_to_df, encrypt_dataframe

load_dotenv()


assert (
    os.getenv("MOOTLIB_ENCRYPTION_KEY") is not None
), "MOOTLIB_ENCRYPTION_KEY is not set"

assert os.getenv("DEEPINFRA_TOKEN") is not None, "DEEPINFRA_TOKEN is not set"


def download_latest_release_file(filename: str) -> bool:
    """Download a file from the latest release if it exists."""
    try:
        import requests

        url = f"https://github.com/vigji/mootlib/releases/download/latest/{filename}"
        response = requests.get(url, allow_redirects=True)
        response.raise_for_status()
        with Path(filename).open("wb") as f:
            f.write(response.content)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Create data directory if needed
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Try to download existing embeddings cache
    print("Downloading existing embeddings cache...")
    cache_exists = download_latest_release_file("embeddings.parquet.encrypted")

    # Initialize embeddings cache
    cache = EmbeddingsCache()
    if cache_exists:
        print("Loading existing embeddings cache...")
        # Load the encrypted cache directly
        temp_cache_path = data_dir / "temp_embeddings.parquet"
        with Path("embeddings.parquet.encrypted").open("rb") as f:
            encrypted_data = f.read()
        decrypted_df = decrypt_to_df(encrypted_data, format="parquet")
        decrypted_df.to_parquet(temp_cache_path)
        cache = EmbeddingsCache(cache_path=temp_cache_path)
        temp_cache_path.unlink()
        Path("embeddings.parquet.encrypted").unlink()
        print(f"Loaded {len(cache.cache_df)} existing embeddings")

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
