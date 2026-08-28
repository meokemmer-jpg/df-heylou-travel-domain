from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sign_payload(secret: str, payload: Dict[str, Any]) -> str:
    return hmac.new(secret.encode("utf-8"), _stable_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload: Dict[str, Any], signature: str) -> bool:
    expected = sign_payload(secret, payload)
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class Hotel:
    id: str
    name: str
    city: str
    nightly_rate: int
    tags: List[str]


@dataclass(frozen=True)
class Route:
    origin: str
    destination: str
    mode: str
    duration_minutes: int


@dataclass
class TravelKnowledgeGraph:
    hotels: List[Hotel] = field(default_factory=list)
    routes: List[Route] = field(default_factory=list)

    @classmethod
    def with_mock_data(cls) -> "TravelKnowledgeGraph":
        return cls(
            hotels=[
                Hotel("par-1", "Left Bank Loft", "Paris", 180, ["central", "wifi", "boutique"]),
                Hotel("par-2", "Canal Stay", "Paris", 140, ["wifi", "budget"]),
                Hotel("ber-1", "Mitte Base", "Berlin", 160, ["central", "wifi", "business"]),
                Hotel("rom-1", "Trastevere Court", "Rome", 210, ["romantic", "wifi"]),
            ],
            routes=[
                Route("BER", "Paris", "flight", 105),
                Route("BER", "Rome", "flight", 120),
                Route("MUC", "Paris", "train", 360),
            ],
        )

    def find_hotels(
        self,
        city: str,
        budget_max: Optional[int] = None,
        required_tags: Optional[Iterable[str]] = None,
    ) -> List[Hotel]:
        required = set(required_tags or [])
        matches = []
        for hotel in self.hotels:
            if hotel.city.lower() != city.lower():
                continue
            if budget_max is not None and hotel.nightly_rate > budget_max:
                continue
            if not required.issubset(set(hotel.tags)):
                continue
            matches.append(hotel)
        return sorted(matches, key=lambda item: (item.nightly_rate, item.name))

    def find_route(self, origin: str, destination: str) -> Optional[Route]:
        for route in self.routes:
            if route.origin.upper() == origin.upper() and route.destination.lower() == destination.lower():
                return route
        return None

    def build_context(self, request: Dict[str, Any], preferences: Dict[str, Any]) -> Dict[str, Any]:
        city = request.get("city", "")
        budget_max = request.get("budget_max")
        tags = preferences.get("tags", [])
        hotels = self.find_hotels(city=city, budget_max=budget_max, required_tags=tags)
        route = self.find_route(request.get("origin", ""), request.get("destination", ""))
        return {
            "request": dict(request),
            "preferences": dict(preferences),
            "hotels": [
                {
                    "id": hotel.id,
                    "name": hotel.name,
                    "city": hotel.city,
                    "nightly_rate": hotel.nightly_rate,
                    "tags": list(hotel.tags),
                }
                for hotel in hotels
            ],
            "route": None
            if route is None
            else {
                "origin": route.origin,
                "destination": route.destination,
                "mode": route.mode,
                "duration_minutes": route.duration_minutes,
            },
        }


class AdapterAuthError(RuntimeError):
    pass


class TravelSoftwareAdapter(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    def authenticate(self, credentials: Dict[str, Any]) -> None:
        if credentials.get("token") != "valid-token":
            raise AdapterAuthError(f"{self.name} authentication failed")

    @abstractmethod
    def fetch_availability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class MEWSAdapter(TravelSoftwareAdapter):
    def __init__(self) -> None:
        super().__init__("MEWSAdapter")

    def fetch_availability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.authenticate(payload)
        return {"adapter": self.name, "status": "ok", "inventory": [{"room_type": "Deluxe", "available": 3}]}


class BookingComAdapter(TravelSoftwareAdapter):
    def __init__(self) -> None:
        super().__init__("BookingComAdapter")

    def fetch_availability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.authenticate(payload)
        return {"adapter": self.name, "status": "ok", "inventory": [{"listing_id": "booking-1", "available": True}]}


class IdeasRevenueAdapter(TravelSoftwareAdapter):
    def __init__(self) -> None:
        super().__init__("IdeasRevenueAdapter")

    def fetch_availability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.authenticate(payload)
        return {"adapter": self.name, "status": "ok", "inventory": [{"segment": "city-break", "recommended_rate": 175}]}


class GenericAPIAdapter(TravelSoftwareAdapter):
    def __init__(self) -> None:
        super().__init__("GenericAPIAdapter")

    def discover_endpoints(self, payload: Dict[str, Any]) -> Dict[str, str]:
        base_url = payload.get("base_url", "").rstrip("/")
        endpoints = payload.get("endpoints", {})
        discovered = {}
        for key, path in endpoints.items():
            discovered[key] = path if path.startswith("http") else f"{base_url}{path}"
        return discovered

    def fetch_availability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.authenticate(payload)
        discovered = self.discover_endpoints(payload)
        return {
            "adapter": self.name,
            "status": "ok",
            "discovered_endpoints": discovered,
            "inventory": [{"endpoint_count": len(discovered), "available": True}],
        }


def _default_provider(provider_name: str) -> Callable[[str, Dict[str, Any], bool], Dict[str, Any]]:
    def call(task: str, context: Dict[str, Any], sandbox: bool) -> Dict[str, Any]:
        hotel_names = [hotel["name"] for hotel in context.get("hotels", [])[:2]]
        route = context.get("route") or {}
        summary = {
            "provider": provider_name,
            "task": task,
            "sandbox": sandbox,
            "hotel_candidates": hotel_names,
            "route_mode": route.get("mode", "unknown"),
        }
        digest = hashlib.sha256(_stable_json(summary).encode("utf-8")).hexdigest()[:12]
        return {"text": f"{provider_name}:{digest}", "confidence": 0.84, "details": summary}

    return call


class LLMSubFunctionRouter:
    DEFAULT_PROVIDER_ORDER = ["ollama-local", "gemini", "openai", "grok", "mistral", "deepseek"]

    def __init__(
        self,
        secret: str,
        providers: Optional[Dict[str, Callable[[str, Dict[str, Any], bool], Dict[str, Any]]]] = None,
        cross_validate_threshold: float = 0.25,
    ) -> None:
        self.secret = secret
        self.cross_validate_threshold = cross_validate_threshold
        self.providers = providers or {name: _default_provider(name) for name in self.DEFAULT_PROVIDER_ORDER}

    def _real_llm_enabled(self, phronesis_ticket: Optional[str]) -> bool:
        return os.environ.get("DF_HEYLOU_REAL_LLM_ENABLED", "").lower() == "true" and bool(phronesis_ticket)

    def invoke(
        self,
        task: str,
        context: Dict[str, Any],
        preferred_provider: str = "ollama-local",
        uncertainty: float = 0.5,
        phronesis_ticket: Optional[str] = None,
    ) -> Dict[str, Any]:
        if preferred_provider not in self.providers:
            raise KeyError(f"Unknown provider: {preferred_provider}")

        sandbox = not self._real_llm_enabled(phronesis_ticket)
        providers_used = [preferred_provider]
        primary = self.providers[preferred_provider](task, context, sandbox)

        validations = []
        if uncertainty <= self.cross_validate_threshold:
            for candidate in self.DEFAULT_PROVIDER_ORDER:
                if candidate != preferred_provider and candidate in self.providers:
                    providers_used.append(candidate)
                    secondary = self.providers[candidate](task, context, sandbox)
                    validations.append(
                        {
                            "provider": candidate,
                            "agrees_on_task": secondary["details"]["task"] == primary["details"]["task"],
                            "text": secondary["text"],
                            "confidence": secondary["confidence"],
                        }
                    )
                    break

        signed_payload = {
            "task": task,
            "preferred_provider": preferred_provider,
            "providers_used": providers_used,
            "sandbox": sandbox,
            "uncertainty": uncertainty,
            "primary_text": primary["text"],
            "validations": validations,
            "context_fingerprint": hashlib.sha256(_stable_json(context).encode("utf-8")).hexdigest(),
        }
        signature = sign_payload(self.secret, signed_payload)
        return {
            "primary": primary,
            "validations": validations,
            "providers_used": providers_used,
            "signed_payload": signed_payload,
            "signature": signature,
        }


class AuditLogger:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    def record(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        envelope = {"event_type": event_type, "timestamp": int(time.time()), "payload": payload}
        return {"envelope": envelope, "signature": sign_payload(self.secret, envelope)}


class DomainOrchestrator:
    def __init__(
        self,
        secret: str,
        knowledge_graph: Optional[TravelKnowledgeGraph] = None,
        router: Optional[LLMSubFunctionRouter] = None,
        adapters: Optional[Dict[str, TravelSoftwareAdapter]] = None,
    ) -> None:
        self.secret = secret
        self.knowledge_graph = knowledge_graph or TravelKnowledgeGraph.with_mock_data()
        self.router = router or LLMSubFunctionRouter(secret=secret)
        self.audit_logger = AuditLogger(secret=secret)
        self.adapters = adapters or {
            "mews": MEWSAdapter(),
            "bookingcom": BookingComAdapter(),
            "ideasrevenue": IdeasRevenueAdapter(),
            "generic": GenericAPIAdapter(),
        }

    def handle_travel_request(
        self,
        request: Dict[str, Any],
        user_preferences: Dict[str, Any],
        adapter_name: str = "generic",
        preferred_provider: str = "ollama-local",
        uncertainty: float = 0.5,
        phronesis_ticket: Optional[str] = None,
    ) -> Dict[str, Any]:
        context = self.knowledge_graph.build_context(request, user_preferences)
        task = (
            f"Plan trip from {request.get('origin', 'N/A')} to {request.get('destination', 'N/A')} "
            f"for {request.get('city', 'N/A')}"
        )

        llm_result = self.router.invoke(
            task=task,
            context=context,
            preferred_provider=preferred_provider,
            uncertainty=uncertainty,
            phronesis_ticket=phronesis_ticket,
        )

        inbox_notes: List[str] = []
        adapter_payload = dict(request.get("adapter_payload", {}))
        adapter_result: Dict[str, Any]
        adapter = self.adapters[adapter_name]
        try:
            adapter_result = adapter.fetch_availability(adapter_payload)
        except AdapterAuthError as exc:
            inbox_notes.append(
                f"T5-Mensch-Gateway-Inbox-Note: auth failure on {adapter.name}; manual skeleton-key handoff required."
            )
            adapter_result = {"adapter": adapter.name, "status": "auth_failed", "error": str(exc)}

        result = {
            "context": context,
            "llm": llm_result,
            "adapter": adapter_result,
            "inbox_notes": inbox_notes,
        }
        result["audit"] = self.audit_logger.record("travel_request", result)
        return result
# [CRUX-MK]
