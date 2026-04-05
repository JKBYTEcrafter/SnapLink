"""
Unit tests for Base62 encode/decode logic.
"""
import pytest
from app.utils.base62 import decode, encode

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class TestEncode:
    def test_encode_zero(self):
        assert encode(0) == "0"

    def test_encode_one(self):
        assert encode(1) == "1"

    def test_encode_large_number(self):
        # Known: 62**6 = 56800235584
        result = encode(56800235584)
        assert len(result) == 7  # 7 digits in base62

    def test_encode_only_uses_alphabet(self):
        for n in [0, 1, 61, 62, 3844, 100000, 2**32]:
            result = encode(n)
            assert all(c in ALPHABET for c in result), f"Invalid char in '{result}'"

    def test_encode_negative_raises(self):
        with pytest.raises(ValueError, match="negative"):
            encode(-1)

    def test_encode_deterministic(self):
        """Same input → same output every time."""
        assert encode(12345) == encode(12345)


class TestDecode:
    def test_decode_zero(self):
        assert decode("0") == 0

    def test_decode_one(self):
        assert decode("1") == 1

    def test_decode_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            decode("")

    def test_decode_invalid_char_raises(self):
        with pytest.raises(ValueError, match="Invalid Base62"):
            decode("hello!")

    def test_decode_invalid_space_raises(self):
        with pytest.raises(ValueError, match="Invalid Base62"):
            decode("ab cd")


class TestRoundTrip:
    @pytest.mark.parametrize("n", [0, 1, 61, 62, 3843, 100_000, 999_999_999, 2**31])
    def test_round_trip(self, n: int):
        assert decode(encode(n)) == n

    def test_large_snowflake_id(self):
        """Simulate a real Snowflake ID round-trip."""
        snowflake_id = 1711234567890123456
        code = encode(snowflake_id)
        assert len(code) <= 12  # Snowflake IDs fit in at most 12 Base62 chars
        assert decode(code) == snowflake_id
