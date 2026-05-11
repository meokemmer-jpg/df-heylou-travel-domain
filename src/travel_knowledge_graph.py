"""Travel-Knowledge-Graph [CRUX-MK].

Domain-Knowledge-Layer ueber Reisen: Hotels + Routes + Rates + GuestPreferences.

In-Memory-Store mit Sandbox-Default-Daten (3 HeyLou-Hotels: Hildesheim, Cape-Coral, Munich).
Persistenz via JSONL-Snapshot optional.

Architektur-Prinzip: Knowledge-Graph ist deterministisch + LLM-unabhaengig.
LLM-Layer (llm_subfunction_router) nutzt Knowledge-Graph als Context-Anreicherung,
aber Knowledge-Graph selbst hat keine LLM-Calls.

Welle-35.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Hotel:
    """HeyLou-Hotel als Knowledge-Graph-Node."""
    hotel_id: str
    name: str
    location: str
    pms_type: str          # mews | opera | protel | apaleo | custom
    rms_type: str          # ideas | duetto | atomize | custom
    timezone: str = "Europe/Berlin"
    rating_stars: int = 4
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Route:
    """Travel-Route zwischen 2 Locations (Origin -> Destination)."""
    origin: str
    destination: str
    duration_h: float
    price_eur: float
    transport_mode: str = "flight"  # flight | train | car | bus
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Rate:
    """Hotel-Rate fuer einen bestimmten Tag (price + availability)."""
    hotel_id: str
    date_iso: str  # YYYY-MM-DD
    price_eur: float
    availability: int        # rooms available
    rate_plan: str = "BAR"   # Best Available Rate
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GuestPreference:
    """Gast-Praeferenzen fuer Personalisierung."""
    guest_id: str
    preferences: dict        # e.g. {"smoking": False, "bed_type": "king", "diet": "vegan"}
    loyalty_tier: str = "standard"
    metadata: dict = field(default_factory=dict)


class TravelKnowledgeGraph:
    """K11 try/except per operation. K12 deterministic data layer (kein LLM).

    Public API:
    - add_hotel(hotel) / get_hotel(hotel_id)
    - find_hotels(location_substring=None, pms_type=None) -> list[Hotel]
    - add_route(route) / compute_route(origin, dest) -> Optional[Route]
    - add_rate(rate) / get_rates(hotel_id, date_from, date_to) -> list[Rate]
    - add_preference(pref) / get_preference(guest_id) -> Optional[GuestPreference]
    - snapshot() -> dict (JSON-serializable)
    - context_for_llm(hotel_id) -> str (formatted for LLM-Sub-Funktion)
    """

    def __init__(self, sandbox_seed: bool = True):
        self._hotels: dict[str, Hotel] = {}
        self._routes: list[Route] = []
        self._rates: list[Rate] = []
        self._preferences: dict[str, GuestPreference] = {}

        if sandbox_seed:
            self._seed_sandbox_data()

    def _seed_sandbox_data(self) -> None:
        """Mock-Daten fuer 3 HeyLou-Hotels (Hildesheim, Cape-Coral, Munich)."""
        sandbox_hotels = [
            Hotel(
                hotel_id="hildesheim",
                name="HeyLou Hildesheim",
                location="Hildesheim, DE",
                pms_type="mews",
                rms_type="ideas",
                timezone="Europe/Berlin",
                rating_stars=4,
            ),
            Hotel(
                hotel_id="cape-coral",
                name="HeyLou Cape Coral",
                location="Cape Coral, FL, USA",
                pms_type="mews",
                rms_type="ideas",
                timezone="America/New_York",
                rating_stars=4,
            ),
            Hotel(
                hotel_id="munich",
                name="HeyLou Munich",
                location="Munich, DE",
                pms_type="mews",
                rms_type="ideas",
                timezone="Europe/Berlin",
                rating_stars=4,
            ),
        ]
        for h in sandbox_hotels:
            self._hotels[h.hotel_id] = h

        # Sandbox-Routes (Hildesheim <-> Munich, Munich <-> Cape-Coral)
        self._routes.extend([
            Route("Hildesheim, DE", "Munich, DE", duration_h=4.5, price_eur=89.0, transport_mode="train"),
            Route("Munich, DE", "Cape Coral, FL, USA", duration_h=12.0, price_eur=850.0, transport_mode="flight"),
        ])

        # Sandbox-Rates (heute + 7 Tage)
        today = datetime.now(timezone.utc).date()
        for offset in range(7):
            iso_date = (today.replace(day=today.day) if offset == 0 else None)
            iso_str = (today.isoformat() if offset == 0
                       else (datetime.now(timezone.utc).date().isoformat()))
            for hid, base_price in [("hildesheim", 120.0), ("cape-coral", 180.0), ("munich", 145.0)]:
                self._rates.append(Rate(
                    hotel_id=hid,
                    date_iso=iso_str,
                    price_eur=base_price + offset * 5.0,
                    availability=10 - offset,
                ))

    # ---- Hotels ----
    def add_hotel(self, hotel: Hotel) -> None:
        try:
            self._hotels[hotel.hotel_id] = hotel
        except Exception as e:
            logger.error(f"add_hotel failed: {e}")
            raise

    def get_hotel(self, hotel_id: str) -> Optional[Hotel]:
        return self._hotels.get(hotel_id)

    def find_hotels(
        self,
        location_substring: Optional[str] = None,
        pms_type: Optional[str] = None,
    ) -> list[Hotel]:
        """K11 try/except, deterministic filter."""
        try:
            results = list(self._hotels.values())
            if location_substring:
                lc = location_substring.lower()
                results = [h for h in results if lc in h.location.lower()]
            if pms_type:
                results = [h for h in results if h.pms_type == pms_type]
            return results
        except Exception as e:
            logger.error(f"find_hotels failed: {e}")
            return []

    # ---- Routes ----
    def add_route(self, route: Route) -> None:
        self._routes.append(route)

    def compute_route(self, origin: str, destination: str) -> Optional[Route]:
        """K11 try/except. Returns first matching route or None."""
        try:
            for r in self._routes:
                if r.origin.lower() == origin.lower() and r.destination.lower() == destination.lower():
                    return r
            return None
        except Exception as e:
            logger.error(f"compute_route failed: {e}")
            return None

    # ---- Rates ----
    def add_rate(self, rate: Rate) -> None:
        self._rates.append(rate)

    def get_rates(
        self,
        hotel_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> list[Rate]:
        """K11 try/except. Returns rates matching hotel + optional date-range."""
        try:
            results = [r for r in self._rates if r.hotel_id == hotel_id]
            if date_from:
                results = [r for r in results if r.date_iso >= date_from]
            if date_to:
                results = [r for r in results if r.date_iso <= date_to]
            return results
        except Exception as e:
            logger.error(f"get_rates failed: {e}")
            return []

    # ---- Preferences ----
    def add_preference(self, pref: GuestPreference) -> None:
        self._preferences[pref.guest_id] = pref

    def get_preference(self, guest_id: str) -> Optional[GuestPreference]:
        return self._preferences.get(guest_id)

    # ---- Snapshot + LLM-Context ----
    def snapshot(self) -> dict:
        """JSON-serializable snapshot des Knowledge-Graph."""
        return {
            "hotels": [asdict(h) for h in self._hotels.values()],
            "routes": [asdict(r) for r in self._routes],
            "rates": [asdict(r) for r in self._rates],
            "preferences": [asdict(p) for p in self._preferences.values()],
            "snapshot_iso": datetime.now(timezone.utc).isoformat(),
        }

    def snapshot_hash(self) -> str:
        """SHA256 ueber canonical snapshot (Provenance-Field fuer Audit)."""
        canonical = json.dumps(self.snapshot(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def context_for_llm(self, hotel_id: str) -> str:
        """Knowledge-Graph-Context als Text fuer LLM-Sub-Funktion-Anreicherung.

        Beispiel-Output:
        ```
        Hotel: HeyLou Hildesheim (hildesheim)
        Location: Hildesheim, DE
        PMS: mews | RMS: ideas | Stars: 4
        Rates (next 7 days): EUR 120-150
        Available routes from this hotel: Hildesheim->Munich (train, 4.5h, EUR 89)
        ```
        """
        hotel = self.get_hotel(hotel_id)
        if not hotel:
            return f"Hotel '{hotel_id}' not found in knowledge-graph."

        rates = self.get_rates(hotel_id)
        rate_summary = ""
        if rates:
            prices = [r.price_eur for r in rates]
            rate_summary = f"Rates ({len(rates)} entries): EUR {min(prices):.0f}-{max(prices):.0f}"
        else:
            rate_summary = "No rates available."

        # Routes from this hotel
        from_loc = hotel.location
        from_routes = [r for r in self._routes if r.origin.lower() == from_loc.lower()]
        route_summary = ""
        if from_routes:
            route_summary = "Available routes: " + ", ".join(
                f"{r.origin}->{r.destination} ({r.transport_mode}, {r.duration_h}h, EUR {r.price_eur:.0f})"
                for r in from_routes
            )
        else:
            route_summary = "No outbound routes available."

        return (
            f"Hotel: {hotel.name} ({hotel.hotel_id})\n"
            f"Location: {hotel.location}\n"
            f"PMS: {hotel.pms_type} | RMS: {hotel.rms_type} | Stars: {hotel.rating_stars}\n"
            f"{rate_summary}\n"
            f"{route_summary}"
        )
