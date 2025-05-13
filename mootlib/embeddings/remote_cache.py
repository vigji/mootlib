"""Remote cache functionality for embeddings."""

import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

from mootlib.utils.encryption import decrypt_to_df, encrypt_dataframe


def download_file(url: str, target_path: Path) -> None:
    """Download a file from a URL to a target path."""
    print(f"Downloading file from {url} to {target_path}")
    urllib.request.urlretrieve(url, target_path)


def get_remote_cache(
    url: str,
    local_path: Path | None = None,
    is_encrypted: bool = True,
) -> pd.DataFrame | None:
    """Get remote cache from URL.

    Args:
        url: URL to download cache from
        local_path: Path to save cache to. If None, uses a temporary file
        is_encrypted: Whether the remote file is encrypted

    Returns:
        DataFrame with cache contents or None if download fails
    """
    if local_path is None:
        local_path = Path(tempfile.gettempdir()) / "mootlib_embeddings.parquet"

    try:
        download_file(url, local_path)
        if is_encrypted:
            return decrypt_to_df(local_path, format="parquet")
        return pd.read_parquet(local_path)
    except Exception:
        return None


def upload_cache(df: pd.DataFrame, path: Path, encrypt: bool = True) -> None:
    """Save cache to disk, optionally encrypted.

    Args:
        df: DataFrame to save
        path: Path to save to
        encrypt: Whether to encrypt the file
    """
    if encrypt:
        encrypt_dataframe(df, path, format="parquet")
    else:
        df.to_parquet(path)
