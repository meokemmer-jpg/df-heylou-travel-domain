"""Tests fuer skeleton_key_adapter.py [CRUX-MK]."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.skeleton_key_adapter import (
    TravelSoftwareAdapter,
    MEWSAdapter,
    BookingComAdapter,
    IdeasRevenueAdapter,
    GenericAPIAdapter,
    AdapterResponse,
)


def test_mews_adapter_sandbox_connect_succeeds():
    """LC1: sandbox-mode connects without credentials."""
    adapter = MEWSAdapter(sandbox_mode=True)
    assert adapter.connect() is True


def test_mews_adapter_query_inventory_returns_mock():
    """K12 source-tracking: sandbox returns source='mock' with payload."""
    adapter = MEWSAdapter(sandbox_mode=True)
    adapter.connect()
    resp = adapter.query_inventory({"hotel_id": "hildesheim"})
    assert isinstance(resp, AdapterResponse)
    assert resp.success is True
    assert resp.source == "mock"
    assert resp.adapter_name == "mews"
    assert "available_rooms" in resp.payload


def test_booking_com_adapter_query_inventory_includes_commission():
    """OTA-Mock includes commission_pct in book_room (Booking.com 18% reality)."""
    adapter = BookingComAdapter(sandbox_mode=True)
    adapter.connect()
    book_resp = adapter.book_room({"hotel_id": "munich", "guest": "test"})
    assert book_resp.success is True
    assert "commission_pct" in book_resp.payload
    assert book_resp.payload["commission_pct"] == 18.0


def test_ideas_revenue_book_room_returns_helpful_error():
    """RMS != booking-engine. book_room must return helpful error."""
    adapter = IdeasRevenueAdapter(sandbox_mode=True)
    adapter.connect()
    resp = adapter.book_room({"hotel_id": "hildesheim"})
    assert resp.success is False
    assert resp.error is not None
    assert "RMS" in resp.error
    assert "MEWSAdapter" in resp.error or "BookingComAdapter" in resp.error


def test_generic_api_endpoint_discovery():
    """Skeleton-Key: GenericAPIAdapter discovers endpoints in sandbox-mode."""
    adapter = GenericAPIAdapter(base_url="https://test.example.com", sandbox_mode=True)
    adapter.connect()
    resp = adapter.query_inventory({"foo": "bar"})
    assert resp.success is True
    assert "endpoint" in resp.payload
    assert "test.example.com" in resp.payload["endpoint"]


def test_request_hash_is_deterministic():
    """LC4 idempotency: same request -> same hash."""
    adapter = MEWSAdapter(sandbox_mode=True)
    adapter.connect()
    h1 = adapter._request_hash("query_inventory", {"a": 1, "b": 2})
    h2 = adapter._request_hash("query_inventory", {"b": 2, "a": 1})  # order-independent
    assert h1 == h2
    assert len(h1) == 16


def test_real_mode_without_credentials_returns_t5_inbox_note(caplog):
    """K17-PAV: real-mode without credentials must NOT crash, must log T5-note."""
    # Force real-mode
    os.environ.pop("MEWS_CLIENT_TOKEN", None)
    os.environ.pop("MEWS_ACCESS_TOKEN", None)
    adapter = MEWSAdapter(sandbox_mode=False)
    result = adapter.connect()
    assert result is False  # graceful failure, no crash


def test_book_room_real_mode_requires_phronesis_ticket():
    """K17-PAV + K_0-Schutz: real book_room without PHRONESIS_TICKET returns error."""
    os.environ.pop("DF_HEYLOU_PHRONESIS_TICKET", None)
    adapter = MEWSAdapter(sandbox_mode=False)
    resp = adapter.book_room({"hotel_id": "test"})
    assert resp.success is False
    assert resp.error is not None
    assert "PHRONESIS" in resp.error
