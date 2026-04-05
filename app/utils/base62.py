"""
Base62 encode/decode utilities.
Alphabet: 0-9, a-z, A-Z  (length = 62)
"""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)  # 62


def encode(n: int) -> str:
    """
    Encode a non-negative integer into a Base62 string.

    Args:
        n: Non-negative integer (e.g., a Snowflake ID).

    Returns:
        Base62-encoded string (minimum length 1).

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError(f"Cannot encode negative integer: {n}")
    if n == 0:
        return ALPHABET[0]

    chars: list[str] = []
    while n:
        n, remainder = divmod(n, BASE)
        chars.append(ALPHABET[remainder])
    return "".join(reversed(chars))


def decode(s: str) -> int:
    """
    Decode a Base62 string back into an integer.

    Args:
        s: Base62-encoded string.

    Returns:
        Original non-negative integer.

    Raises:
        ValueError: If s contains characters outside the alphabet.
    """
    if not s:
        raise ValueError("Cannot decode an empty string")

    result = 0
    for char in s:
        idx = ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid Base62 character: '{char}'")
        result = result * BASE + idx
    return result
