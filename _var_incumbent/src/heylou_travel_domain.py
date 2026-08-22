"""heylou_travel_domain.py - file-backed travel domain recommendation kernel.

Stdlib-only implementation for df-heylou-travel-domain. The kernel uses a real
SQLite database file as its source of truth and produces auditable, deterministic
recommendations from persisted hotels, rates, routes, and user travel intents.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

HMAC_SECRET = b"df-heylou-travel-domain-audit-v1"


@dataclass(frozen=True)
class Hotel:
    id: str
    name: str
    city: str
    country: str
    lat: float
    lng: float
    rating: float
    amenities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Route:
    origin: str
    destination: str
    mode: str
    duration_min: int
    price_eur: float


@dataclass(frozen=True)
class Rate:
    hotel_id: str
    room_type: str
    price_per_night: float
    currency: str = "EUR"
    available: bool = True


@dataclass(frozen=True)
class TravelIntent:
    user_id: str
    origin: str
    desired_city: str | None = None
    avoid_cities: list[str] = field(default_factory=list)
    max_budget_eur: float = 500.0
    required_amenities: list[str] = field(default_factory=list)
    preferred_transport: str | None = None
    nights: int = 1


class SQLiteTravelRepository:
    """SQLite-backed travel repository.

    The repository is deliberately file-backed. Passing ':memory:' is rejected so
    tests and callers cannot prove behavior with an in-memory fixture.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if str(self.db_path) == ":memory:":
            raise ValueError("df-heylou-travel-domain requires a file-backed SQLite database")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS hotels (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    city TEXT NOT NULL,
                    country TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    rating REAL NOT NULL,
                    amenities_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rates (
                    hotel_id TEXT NOT NULL,
                    room_type TEXT NOT NULL,
                    price_per_night REAL NOT NULL,
                    currency TEXT NOT NULL,
                    available INTEGER NOT NULL,
                    PRIMARY KEY (hotel_id, room_type),
                    FOREIGN KEY (hotel_id) REFERENCES hotels(id)
                );
                CREATE TABLE IF NOT EXISTS routes (
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    duration_min INTEGER NOT NULL,
                    price_eur REAL NOT NULL,
                    PRIMARY KEY (origin, destination, mode)
                );
                """
            )

    def replace_catalog(
        self,
        hotels: Iterable[Hotel],
        rates: Iterable[Rate],
        routes: Iterable[Route],
    ) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM rates")
            conn.execute("DELETE FROM routes")
            conn.execute("DELETE FROM hotels")
            conn.executemany(
                """
                INSERT INTO hotels(id, name, city, country, lat, lng, rating, amenities_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        h.id,
                        h.name,
                        h.city,
                        h.country,
                        h.lat,
                        h.lng,
                        h.rating,
                        json.dumps(sorted(set(h.amenities))),
                    )
                    for h in hotels
                ],
            )
            conn.executemany(
                """
                INSERT INTO rates(hotel_id, room_type, price_per_night, currency, available)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(r.hotel_id, r.room_type, r.price_per_night, r.currency, int(r.available)) for r in rates],
            )
            conn.executemany(
                """
                INSERT INTO routes(origin, destination, mode, duration_min, price_eur)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(r.origin, r.destination, r.mode, r.duration_min, r.price_eur) for r in routes],
            )

    def catalog_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            return {
                "hotels": conn.execute("SELECT COUNT(*) FROM hotels").fetchone()[0],
                "rates": conn.execute("SELECT COUNT(*) FROM rates").fetchone()[0],
                "routes": conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0],
            }

    def recommendation_candidates(self, origin: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    h.id AS hotel_id,
                    h.name AS hotel_name,
                    h.city,
                    h.country,
                    h.rating,
                    h.amenities_json,
                    rt.room_type,
                    rt.price_per_night,
                    rt.currency,
                    r.mode,
                    r.duration_min,
                    r.price_eur AS route_price_eur
                FROM hotels h
                JOIN rates rt ON rt.hotel_id = h.id AND rt.available = 1
                JOIN routes r ON lower(r.destination) = lower(h.city)
                WHERE lower(r.origin) = lower(?)
                ORDER BY h.id, rt.price_per_night, r.price_eur
                """,
                (origin,),
            ).fetchall()
        return [dict(row) | {"amenities": json.loads(row["amenities_json"])} for row in rows]


class TravelDomainKernel:
    """Scores persisted travel inventory against a caller-provided intent."""

    def __init__(self, repository: SQLiteTravelRepository):
        self.repository = repository

    def recommend_trip(self, intent: TravelIntent | dict[str, Any]) -> dict[str, Any]:
        if isinstance(intent, dict):
            intent = TravelIntent(**intent)
        candidates = self.repository.recommendation_candidates(intent.origin)
        if not candidates:
            return self._signed_result(intent, None, [], "no_inventory")

        scored = [self._score_candidate(candidate, intent) for candidate in candidates]
        viable = [item for item in scored if item["score"] > -1_000]
        ranked = sorted(viable or scored, key=lambda item: (-item["score"], item["total_price_eur"], item["duration_min"]))
        best = ranked[0] if ranked else None
        return self._signed_result(intent, best, ranked[:5], "ok" if best else "no_match")

    def _score_candidate(self, candidate: dict[str, Any], intent: TravelIntent) -> dict[str, Any]:
        total = float(candidate["price_per_night"]) * max(intent.nights, 1) + float(candidate["route_price_eur"])
        amenities = {a.lower() for a in candidate["amenities"]}
        required = {a.lower() for a in intent.required_amenities}
        missing = sorted(required - amenities)

        score = float(candidate["rating"]) * 10.0
        reasons: list[str] = ["rating"]
        if intent.desired_city and candidate["city"].lower() == intent.desired_city.lower():
            score += 80.0
            reasons.append("desired_city")
        if candidate["city"].lower() in {c.lower() for c in intent.avoid_cities}:
            score -= 500.0
            reasons.append("avoided_city")
        if not missing:
            score += 30.0 + 8.0 * len(required)
            reasons.append("required_amenities")
        else:
            score -= 35.0 * len(missing)
            reasons.append("missing_amenities")
        if intent.preferred_transport and candidate["mode"].lower() == intent.preferred_transport.lower():
            score += 30.0
            reasons.append("preferred_transport")
        elif intent.preferred_transport:
            score -= 12.0
            reasons.append("transport_mismatch")
        if total <= intent.max_budget_eur:
            score += 40.0
            reasons.append("within_budget")
        else:
            score -= min(250.0, (total - intent.max_budget_eur) * 1.5)
            reasons.append("over_budget")

        return {
            "hotel_id": candidate["hotel_id"],
            "hotel_name": candidate["hotel_name"],
            "city": candidate["city"],
            "country": candidate["country"],
            "room_type": candidate["room_type"],
            "transport_mode": candidate["mode"],
            "duration_min": int(candidate["duration_min"]),
            "total_price_eur": round(total, 2),
            "score": round(score, 4),
            "reasons": reasons,
            "missing_amenities": missing,
        }

    def _signed_result(
        self,
        intent: TravelIntent,
        recommendation: dict[str, Any] | None,
        alternatives: list[dict[str, Any]],
        status: str,
    ) -> dict[str, Any]:
        evidence = {
            "mission": "df-heylou-travel-domain",
            "intent": asdict(intent),
            "status": status,
            "recommendation": recommendation,
            "alternatives": alternatives,
            "catalog_counts": self.repository.catalog_counts(),
        }
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
        evidence["payload_hash"] = hashlib.sha256(canonical).hexdigest()
        evidence["signature"] = hmac.new(HMAC_SECRET, canonical, hashlib.sha256).hexdigest()
        return evidence


def verify_result_signature(result: dict[str, Any]) -> bool:
    payload = {k: v for k, v in result.items() if k not in {"payload_hash", "signature"}}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_hash = hashlib.sha256(canonical).hexdigest()
    expected_signature = hmac.new(HMAC_SECRET, canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(result.get("payload_hash", ""), expected_hash) and hmac.compare_digest(
        result.get("signature", ""), expected_signature
    )
