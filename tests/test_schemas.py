"""DF-HeyLou-Travel-Domain Schema Tests [CRUX-MK].

K12 Schema-Validation + Provenance-Envelope (Patch-1 W35-C).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.schemas import (
    TravelQuerySchema,
    AdapterResponseSchema,
    wrap_with_provenance,
    validate_envelope,
    wrap_travel_response,
    iso_now,
)


def test_schema_valid_travel_query():
    """Test 1: Valid TravelQuerySchema accepted."""
    q = TravelQuerySchema(
        query_id="q-2026-05-11-001",
        operation="query_inventory",
        adapter_name="MEWSAdapter",
        criteria={"hotel_id": "hildesheim-001", "checkin": "2026-06-01"},
        tenant_id="hildesheim",
        idempotency_key="idem-001",
    )
    assert q.operation == "query_inventory"
    assert q.idempotency_key == "idem-001"


def test_schema_invalid_blank_query_id():
    """Test 2: Blank query_id rejected."""
    with pytest.raises((ValueError, Exception)):
        TravelQuerySchema(
            query_id="   ",
            operation="query_inventory",
            adapter_name="MEWSAdapter",
        )


def test_adapter_response_invalid_source():
    """Test 3: AdapterResponseSchema rejects bad source."""
    with pytest.raises((ValueError, Exception)):
        AdapterResponseSchema(
            adapter_name="MEWS",
            operation="query_inventory",
            success=True,
            source="invalid-source",  # not in {mock, real-api, stub}
            timestamp_iso="2026-05-11T00:00:00Z",
            request_hash="abc123def456",
        )


def test_provenance_complete():
    """Test 4: wrap_travel_response produces complete envelope."""
    resp = AdapterResponseSchema(
        adapter_name="MEWS",
        operation="query_inventory",
        success=True,
        source="mock",
        timestamp_iso=iso_now(),
        request_hash="abc123def456",
        payload={"rooms": 12},
    )
    wrapped = wrap_travel_response(resp, run_id="run-001")
    env = wrapped["envelope"]
    assert env["df_name"] == "df-heylou-travel-domain"
    assert env["provider"] == "skeleton-key"
    assert env["run_id"] == "run-001"
    assert validate_envelope(wrapped) is True


def test_tamper_detected_in_adapter_response():
    """Test 5: Tamper-detection on AdapterResponse."""
    resp = AdapterResponseSchema(
        adapter_name="BookingCom",
        operation="book_room",
        success=True,
        source="mock",
        timestamp_iso=iso_now(),
        request_hash="hash12345",
        payload={"booking_id": "BC-001"},
    )
    wrapped = wrap_travel_response(resp)
    assert validate_envelope(wrapped) is True

    # Tamper payload
    wrapped["output"]["payload"]["booking_id"] = "BC-HACKED"
    assert validate_envelope(wrapped) is False
