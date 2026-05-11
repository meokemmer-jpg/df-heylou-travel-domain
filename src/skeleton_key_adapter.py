"""Skeleton-Key-Adapter [CRUX-MK].

Adapter-Pattern fuer beliebige Travel-Software-Schnittstellen
(PMS / OTA / RMS / Booking-Engine).

4 konkrete Adapter (alle MOCK im Sandbox-Mode):
- MEWSAdapter (PMS-Industry-Leader)
- BookingComAdapter (OTA-Industry-Leader)
- IdeasRevenueAdapter (RMS-Industry-Leader)
- GenericAPIAdapter (Skeleton-Key: HTTP-API mit Endpoint-Discovery)

K12 Provenance: Jede Response enthaelt source-tracking-fields.
ENV-Var-gated: DF_HEYLOU_REAL_ADAPTER_ENABLED=false per Default (Mock-Fallback).

T5-Mensch-Gateway: Bei Adapter-Auth-Failures wird Inbox-Note geschrieben
(per skeleton-key-Pattern; im Sandbox-Mode nur logging).

Welle-35.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdapterResponse:
    """Kanonische Adapter-Response (LC4 idempotent + K12 provenance).

    source ∈ {"mock", "real-api", "stub"}
    """
    adapter_name: str
    operation: str
    success: bool
    payload: dict
    source: str
    timestamp_iso: str
    request_hash: str
    error: Optional[str] = None


class TravelSoftwareAdapter(ABC):
    """Abstract Skeleton-Key-Pattern Interface.

    Jeder konkrete Adapter implementiert mindestens diese 4 Methoden:
    - connect()                 -> bool
    - query_inventory(criteria) -> AdapterResponse
    - book_room(booking_request) -> AdapterResponse
    - cancel_booking(booking_id) -> AdapterResponse
    """

    def __init__(self, adapter_name: str, sandbox_mode: Optional[bool] = None):
        self.adapter_name = adapter_name
        # Default: Mock unless explicitly enabled
        if sandbox_mode is None:
            self.sandbox_mode = os.environ.get("DF_HEYLOU_REAL_ADAPTER_ENABLED", "false") != "true"
        else:
            self.sandbox_mode = sandbox_mode
        self._connected = False
        # W35-C Patch-1 K11: in-memory idempotency cache for mutations (book/cancel)
        # Real implementation persists via SQLite-WAL (per persistent-state-sqlite-pattern)
        self._idempotency_cache: dict[str, AdapterResponse] = {}

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection. Returns True if successful."""
        raise NotImplementedError

    @abstractmethod
    def query_inventory(self, criteria: dict) -> AdapterResponse:
        """Query available rooms/inventory."""
        raise NotImplementedError

    @abstractmethod
    def book_room(self, booking_request: dict) -> AdapterResponse:
        """Book a room. K17-PAV: must verify env_tag != prod in sandbox-mode."""
        raise NotImplementedError

    @abstractmethod
    def cancel_booking(self, booking_id: str) -> AdapterResponse:
        """Cancel an existing booking."""
        raise NotImplementedError

    # ---- Helpers ----
    def _request_hash(self, operation: str, payload: dict) -> str:
        canonical = json.dumps({"op": operation, "payload": payload}, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def book_room_idempotent(
        self,
        booking_request: dict,
        idempotency_key: str,
    ) -> AdapterResponse:
        """W35-C K11 Idempotency-Wrapper around book_room().

        Per SAGA-Pattern: same idempotency_key returns cached response.
        Different keys execute new bookings.
        """
        if idempotency_key in self._idempotency_cache:
            cached = self._idempotency_cache[idempotency_key]
            logger.info(
                f"[K11-IDEMPOTENCY] adapter={self.adapter_name} "
                f"replay key={idempotency_key[:16]}..."
            )
            return cached
        result = self.book_room(booking_request)
        self._idempotency_cache[idempotency_key] = result
        return result

    def cancel_booking_idempotent(
        self,
        booking_id: str,
        idempotency_key: str,
    ) -> AdapterResponse:
        """W35-C K11 Idempotency-Wrapper around cancel_booking()."""
        if idempotency_key in self._idempotency_cache:
            cached = self._idempotency_cache[idempotency_key]
            logger.info(
                f"[K11-IDEMPOTENCY] adapter={self.adapter_name} "
                f"replay-cancel key={idempotency_key[:16]}..."
            )
            return cached
        result = self.cancel_booking(booking_id)
        self._idempotency_cache[idempotency_key] = result
        return result

    def _t5_inbox_note(self, reason: str, context: dict) -> None:
        """T5-Mensch-Gateway-Skeleton-Key-Inbox-Note bei Auth-Failures.

        Im Sandbox-Mode nur Logging. Im Real-Mode wuerde hier eine Inbox-File
        an Martin geschrieben (out-of-scope fuer SKELETON; Welle-36-Pflicht).
        """
        logger.warning(
            f"[T5-INBOX-NOTE] adapter={self.adapter_name} reason={reason} "
            f"context={json.dumps(context, default=str)}"
        )


class MEWSAdapter(TravelSoftwareAdapter):
    """PMS-Industry-Leader Mews Connector (Mock-Default).

    Real-API: https://api.mews.com (clientToken + accessToken in Header).
    Sandbox: deterministische Mock-Responses basierend auf request_hash.
    """

    def __init__(self, sandbox_mode: Optional[bool] = None):
        super().__init__("mews", sandbox_mode)

    def connect(self) -> bool:
        if self.sandbox_mode:
            self._connected = True
            return True
        # Real-API connection wuerde hier mit ENV-Vars MEWS_CLIENT_TOKEN + MEWS_ACCESS_TOKEN passieren
        client_token = os.environ.get("MEWS_CLIENT_TOKEN", "")
        access_token = os.environ.get("MEWS_ACCESS_TOKEN", "")
        if not client_token or not access_token:
            self._t5_inbox_note("missing_credentials", {"missing": ["MEWS_CLIENT_TOKEN", "MEWS_ACCESS_TOKEN"]})
            return False
        self._connected = True
        return True

    def query_inventory(self, criteria: dict) -> AdapterResponse:
        op = "query_inventory"
        h = self._request_hash(op, criteria)
        if self.sandbox_mode:
            mock_payload = {
                "available_rooms": 12,
                "room_types": ["standard", "deluxe", "suite"],
                "criteria_echoed": criteria,
            }
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload=mock_payload,
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        # Real-API call placeholder
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )

    def book_room(self, booking_request: dict) -> AdapterResponse:
        op = "book_room"
        h = self._request_hash(op, booking_request)
        if self.sandbox_mode:
            mock_booking_id = f"mews-mock-{h[:8]}"
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload={"booking_id": mock_booking_id, "request_echoed": booking_request},
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        # K17-PAV: Real-bookings require explicit DF_HEYLOU_PHRONESIS_TICKET
        ticket = os.environ.get("DF_HEYLOU_PHRONESIS_TICKET", "")
        if not ticket:
            self._t5_inbox_note("missing_phronesis_ticket", {"operation": op})
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=False,
                payload={},
                source="stub",
                timestamp_iso=self._now_iso(),
                request_hash=h,
                error="K17-PAV: real-booking requires DF_HEYLOU_PHRONESIS_TICKET",
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )

    def cancel_booking(self, booking_id: str) -> AdapterResponse:
        op = "cancel_booking"
        h = self._request_hash(op, {"booking_id": booking_id})
        if self.sandbox_mode:
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload={"booking_id": booking_id, "cancellation_status": "confirmed"},
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )


class BookingComAdapter(TravelSoftwareAdapter):
    """OTA-Industry-Leader Booking.com Connector (Mock-Default).

    Real-API: Booking.com Hotel API (channelManager XML/REST).
    Sandbox: deterministische Mock-Responses.
    """

    def __init__(self, sandbox_mode: Optional[bool] = None):
        super().__init__("booking_com", sandbox_mode)

    def connect(self) -> bool:
        if self.sandbox_mode:
            self._connected = True
            return True
        api_key = os.environ.get("BOOKING_COM_API_KEY", "")
        if not api_key:
            self._t5_inbox_note("missing_credentials", {"missing": ["BOOKING_COM_API_KEY"]})
            return False
        self._connected = True
        return True

    def query_inventory(self, criteria: dict) -> AdapterResponse:
        op = "query_inventory"
        h = self._request_hash(op, criteria)
        if self.sandbox_mode:
            mock_payload = {
                "ota_listings": [
                    {"hotel_id": "hildesheim", "ota_rate_eur": 135.0, "stars": 4},
                    {"hotel_id": "munich", "ota_rate_eur": 165.0, "stars": 4},
                ],
                "criteria_echoed": criteria,
            }
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload=mock_payload,
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )

    def book_room(self, booking_request: dict) -> AdapterResponse:
        op = "book_room"
        h = self._request_hash(op, booking_request)
        if self.sandbox_mode:
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload={"ota_booking_id": f"bdc-mock-{h[:8]}", "commission_pct": 18.0},
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        ticket = os.environ.get("DF_HEYLOU_PHRONESIS_TICKET", "")
        if not ticket:
            self._t5_inbox_note("missing_phronesis_ticket", {"operation": op})
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=False,
                payload={},
                source="stub",
                timestamp_iso=self._now_iso(),
                request_hash=h,
                error="K17-PAV: real-booking requires DF_HEYLOU_PHRONESIS_TICKET",
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )

    def cancel_booking(self, booking_id: str) -> AdapterResponse:
        op = "cancel_booking"
        h = self._request_hash(op, {"booking_id": booking_id})
        if self.sandbox_mode:
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload={"ota_booking_id": booking_id, "cancellation_fee_eur": 0.0},
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )


class IdeasRevenueAdapter(TravelSoftwareAdapter):
    """RMS-Industry-Leader IDeaS Revenue Connector (Mock-Default).

    Sandbox: deterministische Pricing-Mock-Responses.
    """

    def __init__(self, sandbox_mode: Optional[bool] = None):
        super().__init__("ideas_revenue", sandbox_mode)

    def connect(self) -> bool:
        if self.sandbox_mode:
            self._connected = True
            return True
        api_key = os.environ.get("IDEAS_REVENUE_API_KEY", "")
        if not api_key:
            self._t5_inbox_note("missing_credentials", {"missing": ["IDEAS_REVENUE_API_KEY"]})
            return False
        self._connected = True
        return True

    def query_inventory(self, criteria: dict) -> AdapterResponse:
        op = "query_inventory"
        h = self._request_hash(op, criteria)
        if self.sandbox_mode:
            mock_payload = {
                "recommended_pricing": {
                    "hildesheim": {"bar_eur": 125.0, "demand_index": 0.72},
                    "munich": {"bar_eur": 155.0, "demand_index": 0.85},
                },
                "criteria_echoed": criteria,
            }
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload=mock_payload,
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )

    def book_room(self, booking_request: dict) -> AdapterResponse:
        # IDeaS is RMS, not booking. Returns NoOp + helpful error.
        op = "book_room"
        h = self._request_hash(op, booking_request)
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="mock" if self.sandbox_mode else "stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="IDeaS is RMS not booking-engine. Use MEWSAdapter or BookingComAdapter.",
        )

    def cancel_booking(self, booking_id: str) -> AdapterResponse:
        op = "cancel_booking"
        h = self._request_hash(op, {"booking_id": booking_id})
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="mock" if self.sandbox_mode else "stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="IDeaS is RMS not booking-engine. Use MEWSAdapter or BookingComAdapter.",
        )


class GenericAPIAdapter(TravelSoftwareAdapter):
    """Skeleton-Key Generic HTTP-API Connector mit Endpoint-Discovery.

    Pattern: generic discovery-based adapter fuer beliebige Travel-Software,
    die noch keinen dedizierten Adapter hat.

    Endpoint-Discovery:
    - Client gibt base_url
    - Adapter probiert Standard-Endpoints (/v1/inventory, /api/inventory, /rooms)
    - Erfolg cached, Failure logged
    """

    def __init__(self, base_url: str = "https://example.com", sandbox_mode: Optional[bool] = None):
        super().__init__("generic_api", sandbox_mode)
        self.base_url = base_url
        self._discovered_endpoints: dict = {}

    def connect(self) -> bool:
        if self.sandbox_mode:
            self._connected = True
            self._discovered_endpoints = {
                "inventory": f"{self.base_url}/v1/inventory",
                "booking": f"{self.base_url}/v1/bookings",
                "cancel": f"{self.base_url}/v1/bookings/{{id}}/cancel",
            }
            return True
        # Real-discovery: probe endpoints
        return False

    def query_inventory(self, criteria: dict) -> AdapterResponse:
        op = "query_inventory"
        h = self._request_hash(op, criteria)
        if self.sandbox_mode:
            mock_payload = {
                "endpoint": self._discovered_endpoints.get("inventory", ""),
                "rooms": [{"id": "generic-1", "available": True}],
                "criteria_echoed": criteria,
            }
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload=mock_payload,
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )

    def book_room(self, booking_request: dict) -> AdapterResponse:
        op = "book_room"
        h = self._request_hash(op, booking_request)
        if self.sandbox_mode:
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload={"generic_booking_id": f"gen-mock-{h[:8]}"},
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )

    def cancel_booking(self, booking_id: str) -> AdapterResponse:
        op = "cancel_booking"
        h = self._request_hash(op, {"booking_id": booking_id})
        if self.sandbox_mode:
            return AdapterResponse(
                adapter_name=self.adapter_name,
                operation=op,
                success=True,
                payload={"generic_booking_id": booking_id, "cancellation_status": "confirmed"},
                source="mock",
                timestamp_iso=self._now_iso(),
                request_hash=h,
            )
        return AdapterResponse(
            adapter_name=self.adapter_name,
            operation=op,
            success=False,
            payload={},
            source="stub",
            timestamp_iso=self._now_iso(),
            request_hash=h,
            error="real-api not implemented in SKELETON",
        )
