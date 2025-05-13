"""Utilities for encrypting and decrypting CSV files securely using Fernet
encryption.
"""

import os
from io import BytesIO
from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

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


def encrypt_file(input_file: PathLike, output_file: PathLike) -> None:
    """Encrypt any file using Fernet symmetric encryption.

    Args:
        input_file: Path to the input file.
        output_file: Path where to save the encrypted file.
    """
    data = Path(input_file).read_bytes()
    fernet = Fernet(get_encryption_key())
    encrypted_data = fernet.encrypt(data)
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


def decrypt_to_df(
    input_file: PathLike | bytes, is_parquet: bool = False
) -> pd.DataFrame:
    """Decrypt an encrypted file directly to a pandas DataFrame.

    Args:
        input_file: Path to the encrypted file or encrypted bytes.
        is_parquet: Whether the encrypted file is a parquet file.

    Returns:
        A pandas DataFrame containing the decrypted data.
    """
    if isinstance(input_file, str | Path):
        encrypted_data = Path(input_file).read_bytes()
    else:
        encrypted_data = input_file

    fernet = Fernet(get_encryption_key())
    decrypted_data = fernet.decrypt(encrypted_data)

    if is_parquet:
        return pd.read_parquet(BytesIO(decrypted_data))
    return pd.read_csv(BytesIO(decrypted_data))


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

    # Test CSV encryption/decryption
    test_csv = test_dir / "test.csv"
    encrypted_csv = test_dir / "test.csv.encrypted"
    decrypted_csv = test_dir / "test_decrypted.csv"

    test_df.to_csv(test_csv, index=False)
    encrypt_csv(test_csv, encrypted_csv)
    decrypt_csv(encrypted_csv, decrypted_csv)

    decrypted_df = pd.read_csv(decrypted_csv)
    assert test_df.equals(decrypted_df), "CSV encryption/decryption failed"

    # Test direct DataFrame decryption
    df_from_decrypt = decrypt_to_df(encrypted_csv)
    assert test_df.equals(df_from_decrypt), "Direct DataFrame decryption failed"

    # Test parquet encryption/decryption
    test_parquet = test_dir / "test.parquet"
    encrypted_parquet = test_dir / "test.parquet.encrypted"

    test_df.to_parquet(test_parquet)
    encrypt_file(test_parquet, encrypted_parquet)
    df_from_parquet = decrypt_to_df(encrypted_parquet, is_parquet=True)
    assert test_df.equals(df_from_parquet), "Parquet encryption/decryption failed"

    # Clean up
    for f in test_dir.glob("*"):
        f.unlink()
    test_dir.rmdir()

    print("All encryption/decryption tests passed!")
