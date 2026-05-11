"""DF-HeyLou-Travel-Domain Idempotency-Wrapper Tests [CRUX-MK].

W35-C Cross-LLM-Konsens 2026-05-11: Idempotency-Wrapper auf book_room()
+ cancel_booking() (per K11/SAGA-Pattern).

4 Pflicht-Tests:
1. idempotency_key_first_call_executes
2. idempotency_key_replay_returns_cached
3. different_keys_execute_separately
4. expired_key_after_ttl_re_executes (TTL behavior)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class IdempotencyWrapper:
    """Minimal in-memory idempotency cache for travel-mutations.

    Real implementation would persist via SQLite-WAL (per persistent-state-sqlite-pattern).
    """

    def __init__(self, ttl_s: float = 3600.0):
        self._cache: dict[str, tuple[float, dict]] = {}
        self.ttl_s = ttl_s

    def execute_or_replay(
        self,
        idempotency_key: str,
        fn,
        *args,
        **kwargs,
    ) -> tuple[dict, bool]:
        """Returns (result, is_replay)."""
        now = time.time()
        if idempotency_key in self._cache:
            ts, cached = self._cache[idempotency_key]
            if now - ts < self.ttl_s:
                return cached, True
            # Expired -> re-execute
            del self._cache[idempotency_key]
        result = fn(*args, **kwargs)
        self._cache[idempotency_key] = (now, result)
        return result, False


def book_room_mock(booking: dict) -> dict:
    """Mock book_room that returns a fresh ID each call."""
    return {
        "booking_id": f"BK-{time.time_ns()}",
        "status": "confirmed",
        "booking_data": booking,
    }


def test_idempotency_key_first_call_executes():
    """Test 1: First call with key executes function."""
    wrapper = IdempotencyWrapper(ttl_s=60)
    result, is_replay = wrapper.execute_or_replay(
        "idem-first-001",
        book_room_mock,
        {"room": "single"},
    )
    assert is_replay is False
    assert result["status"] == "confirmed"
    assert "booking_id" in result


def test_idempotency_key_replay_returns_cached():
    """Test 2: Second call with same key returns cached result."""
    wrapper = IdempotencyWrapper(ttl_s=60)
    result1, _ = wrapper.execute_or_replay(
        "idem-replay-001",
        book_room_mock,
        {"room": "double"},
    )

    # Force time gap
    time.sleep(0.01)

    result2, is_replay = wrapper.execute_or_replay(
        "idem-replay-001",
        book_room_mock,
        {"room": "double"},
    )
    assert is_replay is True
    assert result2["booking_id"] == result1["booking_id"]  # Cached


def test_different_keys_execute_separately():
    """Test 3: Different keys produce different results."""
    wrapper = IdempotencyWrapper(ttl_s=60)
    r1, _ = wrapper.execute_or_replay(
        "key-A",
        book_room_mock,
        {"room": "A"},
    )
    r2, _ = wrapper.execute_or_replay(
        "key-B",
        book_room_mock,
        {"room": "B"},
    )
    assert r1["booking_id"] != r2["booking_id"]


def test_expired_key_after_ttl_re_executes():
    """Test 4: After TTL expiry, same key re-executes."""
    wrapper = IdempotencyWrapper(ttl_s=0.05)  # 50ms TTL
    r1, replay1 = wrapper.execute_or_replay(
        "key-expire",
        book_room_mock,
        {"room": "X"},
    )
    assert replay1 is False

    time.sleep(0.1)  # Wait for TTL to expire

    r2, replay2 = wrapper.execute_or_replay(
        "key-expire",
        book_room_mock,
        {"room": "X"},
    )
    assert replay2 is False  # TTL expired -> re-executed
    assert r2["booking_id"] != r1["booking_id"]
