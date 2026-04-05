"""
Snowflake-style distributed ID generator.

Structure (64-bit integer):
  - 41 bits: millisecond timestamp (epoch: 2020-01-01)
  - 10 bits: machine ID (0-1023)
  - 12 bits: sequence number per millisecond (0-4095)

Guarantees monotonically increasing, globally unique IDs
across machines without a central coordinator.
"""
import threading
import time

EPOCH_MS = 1577836800000  # 2020-01-01 00:00:00 UTC in milliseconds

TIMESTAMP_BITS = 41
MACHINE_BITS = 10
SEQUENCE_BITS = 12

MAX_MACHINE_ID = (1 << MACHINE_BITS) - 1     # 1023
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1       # 4095

TIMESTAMP_SHIFT = MACHINE_BITS + SEQUENCE_BITS   # 22
MACHINE_SHIFT = SEQUENCE_BITS                    # 12


class SnowflakeIDGenerator:
    """Thread-safe Snowflake ID generator."""

    def __init__(self, machine_id: int = 1) -> None:
        if not 0 <= machine_id <= MAX_MACHINE_ID:
            raise ValueError(f"machine_id must be in [0, {MAX_MACHINE_ID}], got {machine_id}")
        self._machine_id = machine_id
        self._sequence = 0
        self._last_timestamp = -1
        self._lock = threading.Lock()

    def _current_ms(self) -> int:
        return int(time.time() * 1000)

    def _wait_next_ms(self, last_timestamp: int) -> int:
        timestamp = self._current_ms()
        while timestamp <= last_timestamp:
            timestamp = self._current_ms()
        return timestamp

    def next_id(self) -> int:
        """Generate the next unique 64-bit integer ID."""
        with self._lock:
            timestamp = self._current_ms()

            if timestamp < self._last_timestamp:
                # Clock moved backwards — wait until we catch up
                timestamp = self._wait_next_ms(self._last_timestamp)

            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & MAX_SEQUENCE
                if self._sequence == 0:
                    # Sequence exhausted within this millisecond — wait for next ms
                    timestamp = self._wait_next_ms(self._last_timestamp)
            else:
                self._sequence = 0

            self._last_timestamp = timestamp

            return (
                ((timestamp - EPOCH_MS) << TIMESTAMP_SHIFT)
                | (self._machine_id << MACHINE_SHIFT)
                | self._sequence
            )


# Module-level singleton; machine_id overridden during app startup
_generator: SnowflakeIDGenerator | None = None


def init_generator(machine_id: int = 1) -> None:
    """Initialise the module-level generator (call once at startup)."""
    global _generator
    _generator = SnowflakeIDGenerator(machine_id)


def generate_id() -> int:
    """Generate the next Snowflake ID using the module singleton."""
    if _generator is None:
        init_generator()
    return _generator.next_id()  # type: ignore[union-attr]
