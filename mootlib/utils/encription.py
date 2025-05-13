"""Utilities for encrypting and decrypting CSV files securely using Fernet
encryption.
"""

import os
from io import BytesIO
from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet

PathLike = str | Path


# Define exception
class EncryptionKeyNotSetError(Exception):
    """Exception raised when encryption key is not set."""

    def __str__(self) -> str:
        return "MOOTLIB_ENCRYPTION_KEY environment variable not set."


def get_encryption_key() -> bytes:
    """Get encryption key from environment variable.

    Returns:
        The encryption key as bytes.

    Raises:
        ValueError: If MOOTLIB_ENCRYPTION_KEY environment variable is not set.
    """
    if key := os.getenv("MOOTLIB_ENCRYPTION_KEY"):
        return key.encode()
    raise EncryptionKeyNotSetError


def encrypt_csv(input_file: PathLike, output_file: PathLike) -> None:
    """Encrypt a CSV file using Fernet symmetric encryption.

    Args:
        input_file: Path to the input CSV file.
        output_file: Path where to save the encrypted file.
    """
    df_to_encrypt = pd.read_csv(input_file)
    csv_bytes = df_to_encrypt.to_csv(index=False).encode()

    fernet = Fernet(get_encryption_key())
    encrypted_data = fernet.encrypt(csv_bytes)
    Path(output_file).write_bytes(encrypted_data)


def decrypt_csv(input_file: PathLike, output_file: PathLike) -> None:
    """Decrypt an encrypted CSV file back to CSV format.

    Args:
        input_file: Path to the encrypted file.
        output_file: Path where to save the decrypted CSV.
    """
    encrypted_data = Path(input_file).read_bytes()

    fernet = Fernet(get_encryption_key())
    decrypted_data = fernet.decrypt(encrypted_data)
    Path(output_file).write_bytes(decrypted_data)


def decrypt_to_df(input_file: PathLike) -> pd.DataFrame:
    """Decrypt an encrypted CSV file directly to a pandas DataFrame.

    Args:
        input_file: Path to the encrypted file.

    Returns:
        A pandas DataFrame containing the decrypted data.
    """
    encrypted_data = Path(input_file).read_bytes()

    fernet = Fernet(get_encryption_key())
    decrypted_data = fernet.decrypt(encrypted_data)
    return pd.read_csv(BytesIO(decrypted_data))


if __name__ == "__main__":
    # Generate and print a new encryption key
    key = Fernet.generate_key()
    print(
        "\nGenerated new encryption key. Set this in your GitHub"
        "  secrets as MOOTLIB_ENCRYPTION_KEY:"
    )
    print(f"\n{key.decode()}\n")
