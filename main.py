from mootlib.scrapers import fetch_markets_df
from mootlib.utils.encription import encrypt_csv
import dotenv
from pathlib import Path
import os
import pandas as pd

dotenv.load_dotenv()
assert os.getenv("MOOTLIB_ENCRYPTION_KEY") is not None, "MOOTLIB_ENCRYPTION_KEY is not set"

if __name__ == "__main__":
    # Create data directories
    data_dir = Path("data")
    raw_dir = data_dir / "raw"
    encrypted_dir = data_dir / "encrypted"
    for dir_path in [data_dir, raw_dir, encrypted_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Fetch and save markets data
    markets_df = pd.DataFrame([dict(
        question="What is the capital of France?",
        published_at=pd.Timestamp("2021-01-01"),
        platform="Example Platform",
        url="https://example.com/markets/123",
    )])# fetch_markets_df()
    
    # Save raw CSV temporarily
    timestamp = Path("markets").with_suffix(".csv")
    raw_path = raw_dir / timestamp
    encrypted_path = encrypted_dir / timestamp.with_suffix(".encrypted")
    
    # Save and encrypt
    markets_df.to_csv(raw_path, index=False)
    encrypt_csv(raw_path, encrypted_path)
    
    # Clean up raw file
    raw_path.unlink()
    
    print(f"Encrypted markets data saved to: {encrypted_path}")

    
