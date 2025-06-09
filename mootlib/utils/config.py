"""Configuration utilities for Mootlib."""

import os
import subprocess
from pathlib import Path
from typing import Optional, Final

DEFAULT_GIT_REPO: Final[str] = "https://github.com/vigji/mootlib"

def get_github_repo_url() -> str:
    """Get the GitHub repository URL from environment or auto-detection.

    This function checks for the repository URL in the following order:
    1. MOOTLIB_GITHUB_REPO environment variable (full URL)
    2. Auto-detection from git remote origin
    3. Fallback to default repository

    Returns:
        The base GitHub repository URL (e.g., "https://github.com/user/repo")

    Examples:
        >>> # With environment variable set
        >>> os.environ["MOOTLIB_GITHUB_REPO"] = "https://github.com/myuser/mootlib"
        >>> get_github_repo_url()
        'https://github.com/myuser/mootlib'

        >>> # Auto-detection from git remote
        >>> get_github_repo_url()  # detects from current repo
        'https://github.com/vigji/mootlib'
    """
    # First, check if explicitly set in environment
    if repo_url := os.getenv("MOOTLIB_GITHUB_REPO"):
        return repo_url.rstrip("/")

    # Try to auto-detect from git remote
    try:
        repo_url = _get_git_remote_url()
        if repo_url:
            return repo_url
    except Exception:
        # If git detection fails, continue to fallback
        pass

    # Fallback to default repository
    return DEFAULT_GIT_REPO


def _get_git_remote_url() -> Optional[str]:
    """Get the GitHub repository URL from git remote origin.

    Returns:
        The GitHub repository URL if found, None otherwise.
    """
    try:
        # Try to get the remote origin URL
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent.parent.parent,  # mootlib root directory
        )

        remote_url = result.stdout.strip()

        # Convert various Git URL formats to HTTPS GitHub URLs
        if "github.com" in remote_url:
            # Handle SSH format: git@github.com:user/repo.git
            if remote_url.startswith("git@github.com:"):
                repo_path = remote_url.replace("git@github.com:", "").replace(".git", "")
                return f"https://github.com/{repo_path}"

            # Handle HTTPS format: https://github.com/user/repo.git
            elif remote_url.startswith("https://github.com/"):
                return remote_url.replace(".git", "").rstrip("/")

        return None

    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_release_file_url(filename: str) -> str:
    """Get the full URL for a release file.

    Args:
        filename: The name of the file to download (e.g., "markets.parquet.encrypted")

    Returns:
        The full URL to download the file from GitHub releases.

    Examples:
        >>> get_release_file_url("markets.parquet.encrypted")
        'https://github.com/vigji/mootlib/releases/download/latest/markets.parquet.encrypted'

        >>> get_release_file_url("embeddings.parquet.encrypted")
        'https://github.com/vigji/mootlib/releases/download/latest/embeddings.parquet.encrypted'
    """
    base_url = get_github_repo_url()
    return f"{base_url}/releases/download/latest/{filename}"


if __name__ == "__main__":
    # Test the configuration detection
    print("GitHub Repository URL:", get_github_repo_url())
    print("Markets file URL:", get_release_file_url("markets.parquet.encrypted"))
    print("Embeddings file URL:", get_release_file_url("embeddings.parquet.encrypted"))
