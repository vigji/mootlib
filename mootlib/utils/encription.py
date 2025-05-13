"""Utilities for encrypting and decrypting CSV files securely."""

import os
from io import BytesIO
from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet

PathLike = str | Path


def get_or_generate_key(config_path: PathLike | None = None) -> bytes:
    """Get encryption key from environment or config file, or generate a new one.

    Args:
        config_path: Optional path to a config file containing the key.
            If not provided, will look for key in MOOTLIB_ENCRYPTION_KEY env var.

    Returns:
        The encryption key as bytes.
    """
    # Try environment variable first
    if key := os.getenv("MOOTLIB_ENCRYPTION_KEY"):
        return key.encode()

    # Try config file if provided
    if config_path and Path(config_path).exists():
        return Path(config_path).read_bytes()

    # Generate new key if neither exists
    key = Fernet.generate_key()

    # Print instructions for saving the key
    print("\nGenerated new encryption key. To use this key later, either:")
    print(f"\n1. Set this environment variable:\nMOOTLIB_ENCRYPTION_KEY={key.decode()}")
    if config_path:
        print(f"\n2. Or save to config file:\necho {key.decode()} > {config_path}")

    return key


def generate_key(key_file: PathLike) -> None:
    """Generate and save a new encryption key.

    Args:
        key_file: Path where to save the generated key.
    """
    key = Fernet.generate_key()
    Path(key_file).write_bytes(key)


def load_key(key_file: PathLike) -> bytes:
    """Load an encryption key from file.

    Args:
        key_file: Path to the key file.

    Returns:
        The encryption key as bytes.
    """
    return Path(key_file).read_bytes()


def encrypt_csv(
    input_file: PathLike,
    output_file: PathLike,
    key_file: PathLike | None = None,
    config_path: PathLike | None = None,
) -> None:
    """Encrypt a CSV file using Fernet symmetric encryption.

    Args:
        input_file: Path to the input CSV file.
        output_file: Path where to save the encrypted file.
        key_file: Optional path to key file. If not provided, will use get_or_generate_key.
        config_path: Optional path to config file containing the key.
    """
    df = pd.read_csv(input_file)
    csv_bytes = df.to_csv(index=False).encode()

    key = load_key(key_file) if key_file else get_or_generate_key(config_path)
    fernet = Fernet(key)

    encrypted_data = fernet.encrypt(csv_bytes)
    Path(output_file).write_bytes(encrypted_data)


def decrypt_csv(
    input_file: PathLike,
    output_file: PathLike,
    key_file: PathLike | None = None,
    config_path: PathLike | None = None,
) -> None:
    """Decrypt an encrypted CSV file back to CSV format.

    Args:
        input_file: Path to the encrypted file.
        output_file: Path where to save the decrypted CSV.
        key_file: Optional path to key file. If not provided, will use 
        get_or_generate_key.
        config_path: Optional path to config file containing the key.
    """
    encrypted_data = Path(input_file).read_bytes()

    key = load_key(key_file) if key_file else get_or_generate_key(config_path)
    fernet = Fernet(key)

    decrypted_data = fernet.decrypt(encrypted_data)
    Path(output_file).write_bytes(decrypted_data)


def decrypt_to_df(
    input_file: PathLike,
    key_file: PathLike | None = None,
    config_path: PathLike | None = None,
) -> pd.DataFrame:
    """Decrypt an encrypted CSV file directly to a pandas DataFrame.

    Args:
        input_file: Path to the encrypted file.
        key_file: Optional path to key file. If not provided, will use 
        get_or_generate_key.
        config_path: Optional path to config file containing the key.

    Returns:
        A pandas DataFrame containing the decrypted data.
    """
    encrypted_data = Path(input_file).read_bytes()

    key = load_key(key_file) if key_file else get_or_generate_key(config_path)
    fernet = Fernet(key)

    decrypted_data = fernet.decrypt(encrypted_data)
    return pd.read_csv(BytesIO(decrypted_data))
