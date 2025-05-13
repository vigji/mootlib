"""Utilities for encrypting and decrypting files securely using Fernet encryption."""

import os
from io import BytesIO
from pathlib import Path
from typing import Literal

import pandas as pd
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

PathLike = str | Path
DataFrameFormat = Literal["parquet", "csv"]


# Define exception
class EncryptionKeyNotSetError(Exception):
    """Exception raised when encryption key is not set."""

    def __str__(self) -> str:
        return "MOOTLIB_ENCRYPTION_KEY environment variable not set."


def get_encryption_key() -> bytes:
    """Get the encryption key from environment variables.

    Returns:
        The encryption key as bytes.

    Raises:
        EncryptionKeyNotSetError: If the encryption key is not set.
    """
    if key := os.getenv("MOOTLIB_ENCRYPTION_KEY"):
        return key.encode()
    raise EncryptionKeyNotSetError()


def encrypt_file(input_file: PathLike, output_file: PathLike) -> None:
    """Encrypt a file using Fernet symmetric encryption.

    Args:
        input_file: Path to the input file.
        output_file: Path where to save the encrypted file.
    """
    data_to_encrypt = Path(input_file).read_bytes()
    fernet = Fernet(get_encryption_key())
    encrypted_data = fernet.encrypt(data_to_encrypt)
    Path(output_file).write_bytes(encrypted_data)


def decrypt_file(input_file: PathLike, output_file: PathLike) -> None:
    """Decrypt an encrypted file.

    Args:
        input_file: Path to the encrypted file.
        output_file: Path where to save the decrypted file.
    """
    encrypted_data = Path(input_file).read_bytes()
    fernet = Fernet(get_encryption_key())
    decrypted_data = fernet.decrypt(encrypted_data)
    Path(output_file).write_bytes(decrypted_data)


def encrypt_dataframe(
    df: pd.DataFrame, output_file: PathLike, format: DataFrameFormat = "parquet"
) -> None:
    """Encrypt a DataFrame using Fernet symmetric encryption.

    Args:
        df: DataFrame to encrypt.
        output_file: Path where to save the encrypted file.
        format: Format to save the DataFrame in ("parquet" or "csv").
    """
    buffer = BytesIO()
    if format == "parquet":
        df.to_parquet(buffer)
    else:
        df.to_csv(buffer, index=False)

    data_bytes = buffer.getvalue()
    fernet = Fernet(get_encryption_key())
    encrypted_data = fernet.encrypt(data_bytes)
    Path(output_file).write_bytes(encrypted_data)


def decrypt_to_df(
    input_file: PathLike | bytes, format: DataFrameFormat = "parquet"
) -> pd.DataFrame:
    """Decrypt an encrypted file directly to a pandas DataFrame.

    Args:
        input_file: Path to the encrypted file or encrypted bytes.
        format: Format of the encrypted file ("parquet" or "csv").

    Returns:
        A pandas DataFrame containing the decrypted data.
    """
    if isinstance(input_file, str | Path):
        encrypted_data = Path(input_file).read_bytes()
    elif isinstance(input_file, bytes):
        encrypted_data = input_file
    else:
        raise TypeError(f"Unsupported input type: {type(input_file)}")

    fernet = Fernet(get_encryption_key())
    decrypted_data = fernet.decrypt(encrypted_data)

    buffer = BytesIO(decrypted_data)
    if format == "parquet":
        return pd.read_parquet(buffer)
    elif format == "csv":
        return pd.read_csv(buffer)
    else:
        raise ValueError(f"Unsupported format: {format}")


# Deprecated functions for backward compatibility
def encrypt_csv(input_file: PathLike, output_file: PathLike) -> None:
    """Deprecated: Use encrypt_dataframe instead."""
    df = pd.read_csv(input_file)
    encrypt_dataframe(df, output_file, format="csv")


def decrypt_csv(input_file: PathLike, output_file: PathLike) -> None:
    """Deprecated: Use decrypt_file instead."""
    decrypt_file(input_file, output_file)


if __name__ == "__main__":
    # Generate and print a new encryption key
    key = Fernet.generate_key()
    print(
        "\nGenerated new encryption key. Set this in your GitHub"
        "  secrets as MOOTLIB_ENCRYPTION_KEY:"
    )
    print(f"\n{key.decode()}\n")

    # Test encryption/decryption
    test_dir = Path("test_encryption")
    test_dir.mkdir(exist_ok=True)

    # Create test data
    test_df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})

    # Test parquet encryption/decryption
    encrypted_parquet = test_dir / "test.parquet.encrypted"
    encrypt_dataframe(test_df, encrypted_parquet)  # default format is parquet
    df_from_parquet = decrypt_to_df(encrypted_parquet)  # default format is parquet
    assert test_df.equals(df_from_parquet), "Parquet encryption/decryption failed"

    # Test CSV encryption/decryption for backward compatibility
    encrypted_csv = test_dir / "test.csv.encrypted"
    encrypt_dataframe(test_df, encrypted_csv, format="csv")
    df_from_csv = decrypt_to_df(encrypted_csv, format="csv")
    assert test_df.equals(df_from_csv), "CSV encryption/decryption failed"

    # Clean up
    for f in test_dir.glob("*"):
        f.unlink()
    test_dir.rmdir()

    print("All encryption/decryption tests passed!")
