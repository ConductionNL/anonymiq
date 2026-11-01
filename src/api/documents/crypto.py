# GCM STUFF: https://www.pycryptodome.org/src/cipher/modern#gcm-mode

import hashlib
import hmac
import json
from base64 import b64decode, b64encode
from typing import Union

from Crypto.Cipher import AES


def fingerprint_sha256(data: Union[bytes, str]) -> str:
    """Generate a SHA-256 fingerprint.

    Args:
        data: Raw key material to hash. Accepts ``bytes`` or ``str`` (UTF-8
            encoded before hashing).

    Returns:
        Hex-encoded SHA-256 digest (64 characters).
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def constant_time_equals(a: Union[bytes, str], b: Union[bytes, str]) -> bool:
    """Compare two values in constant time.

    Args:
        a: First value (digest or plain data), ``bytes`` or ``str``.
        b: Second value, same rules as ``a``.

    Returns:
        ``True`` if the values are identical, otherwise ``False``.
    """
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hmac.compare_digest(a, b)


def aes_gcm_encrypt(
    data: bytes,
    key: bytes,
    header: bytes = b"header",
) -> str:
    """Encrypts data using AES-GCM mode with optional header and key.

    Args:
        data: The data to encrypt
        key: Encryption key
        header: Additional authenticated data (default: b"header")

    Returns:
        JSON string containing nonce, header, ciphertext, and authentication tag
    """
    # if key is None:
    #     key = get_random_bytes(16)

    cipher = AES.new(key, AES.MODE_GCM)
    cipher.update(header)

    ciphertext, tag = cipher.encrypt_and_digest(data)

    fields = {
        "nonce": b64encode(cipher.nonce).decode(),
        "header": b64encode(header).decode(),
        "ciphertext": b64encode(ciphertext).decode(),
        "tag": b64encode(tag).decode(),
    }
    return json.dumps(fields, separators=(",", ":"))


def aes_gcm_decrypt(blob: str, key: bytes, header: bytes = b"header") -> bytes:
    """Reverse *aes_gcm_encrypt*.

    Args:
        blob: JSON string containing nonce, header, ciphertext, and tag
        key: Encryption key
        header: Additional authenticated data (default: b"header")

    Returns:
        Decrypted data as bytes

    Raises:
        ValueError: If the AAD does not match the header or if decryption fails
    """
    data = json.loads(blob)
    nonce = b64decode(data["nonce"])
    aad = b64decode(data["header"])
    ciphertext = b64decode(data["ciphertext"])
    tag = b64decode(data["tag"])

    if aad != header:
        raise ValueError("AAD mismatch – wrong header supplied")

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    cipher.update(header)
    return cipher.decrypt_and_verify(ciphertext, tag)
