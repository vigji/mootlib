import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from mootlib.scrapers.aggregate import fetch_markets_df
from mootlib.utils.encription import encrypt_csv

load_dotenv()

# print all available environment variables
print(os.environ)

assert (
    os.getenv("MOOTLIB_ENCRYPTION_KEY") is not None
), "MOOTLIB_ENCRYPTION_KEY is not set"

if __name__ == "__main__":
    # Create data directory if needed
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Fetch and save markets data
    test_df = pd.DataFrame(
        [
            {
                "question": "What is the capital of France?",
                "published_at": pd.Timestamp("2021-01-01"),
                "platform": "Example Platform",
                "url": "https://example.com/markets/123",
            }
        ]
    )
    markets_df = fetch_markets_df()

    # Save and encrypt directly in the root directory for GitHub release
    raw_path = data_dir / "markets.csv"
    encrypted_path = Path("markets.csv.encrypted")

    # Save and encrypt
    markets_df.to_csv(raw_path, index=False)
    encrypt_csv(raw_path, encrypted_path)

    # Clean up raw file
    raw_path.unlink()

    print(f"Encrypted file ready at: {encrypted_path}")
    print("\nTo release, run:")
    print("gh release delete latest -y || true")
    print(
        f"gh release create latest {encrypted_path} --title"
        "'Latest Encrypted Markets' --notes 'Auto-uploaded'"
    )
