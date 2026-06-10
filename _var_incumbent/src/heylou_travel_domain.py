from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


class AuditLogger:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")
        self.events: List[Dict[str, Any]] = []

    def log(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = {
            "event_type": event_type,
            "payload": payload,
            "ts": int(time.time()),
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._secret, raw, hashlib.sha256).hexdigest()
        event = dict(body)
        event["signature"] = signature
        self.events.append(event)
        return event


@dataclass
class TravelKnowledgeGraph:
    hotels: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    routes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    traveler_profiles: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def with_mock_data(cls) -> "TravelKnowledgeGraph":
        return cls(
            hotels={
                "BER_CITY": {
                    "city": "Berlin",
                    "name": "Mock Berlin Mitte Hotel",
                    "nightly_rate_eur": 145,
                    "amenities": ["wifi", "breakfast", "late-checkin"],
                },
                "MUC_CENTRAL": {
                    "city": "Munich",
                    "name": "Mock Munich Central Hotel",
                    "nightly_rate_eur": 189,
                    "amenities": ["wifi", "spa"],
                },
            },
            routes={
                "HAM->BER": {
                    "mode": "train",
                    "duration_min": 110,
                    "co2_score": "low",
                },
                "MUC->BER": {
                    "mode": "flight",
                    "duration_min": 65,
                    "co2_score": "medium",
                },
            },
            traveler_profiles={
                "default": {
                    "preferred_amenities": ["wifi", "breakfast"],
                    "budget_max_eur": 200,
                    "loyalty_tier": "gold",
                }
            },
        )

    def enrich_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        destination = request["destination"]
        origin = request.get("origin")
        traveler_id = request.get("traveler_id", "default")

        hotel_candidates = [
            {"hotel_id": hotel_id, **hotel}
            for hotel_id, hotel in self.hotels.items()
            if hotel["city"].lower() == destination.lower()
        ]

        route = None
        if origin:
            route = self.routes.get(f"{origin}->{destination[:3].upper()}") or self.routes.get(
                f"{origin}->{destination}"
            )

        return {
            "request": dict(request),
            "traveler_profile": self.traveler_profiles.get(traveler_id, self.traveler_profiles["default"]),
            "hotel_candidates": hotel_candidates,
            "route": route,
        }


class TravelSoftwareAdapter(Protocol):
    name: str

    def fetch_availability(self, destination: str, nights: int) -> Dict[str, Any]:
        ...

    def authenticate(self) -> bool:
        ...


@dataclass
class BaseMockAdapter:
    name: str
    auth_token: Optional[str] = None

    def authenticate(self) -> bool:
        return bool(self.auth_token or os.getenv("DF_HEYLOU_MOCK_AUTH", "1") == "1")

    def fetch_availability(self, destination: str, nights: int) -> Dict[str, Any]:
        if not self.authenticate():
            return {
                "adapter": self.name,
                "ok": False,
                "reason": "auth_failed",
                "human_gateway_note": f"T5 inbox: authentication failed for {self.name}",
            }
        return {
            "adapter": self.name,
            "ok": True,
            "destination": destination,
            "nights": nights,
            "availability": "mock-available",
        }


class MEWSAdapter(BaseMockAdapter):
    def __init__(self, auth_token: Optional[str] = None) -> None:
        super().__init__("MEWSAdapter", auth_token)


class BookingComAdapter(BaseMockAdapter):
    def __init__(self, auth_token: Optional[str] = None) -> None:
        super().__init__("BookingComAdapter", auth_token)


class IdeasRevenueAdapter(BaseMockAdapter):
    def __init__(self, auth_token: Optional[str] = None) -> None:
        super().__init__("IdeasRevenueAdapter", auth_token)


class GenericAPIAdapter(BaseMockAdapter):
    def __init__(self, endpoint: str = "https://mock.local/discovery", auth_token: Optional[str] = None) -> None:
        super().__init__("GenericAPIAdapter", auth_token)
        self.endpoint = endpoint

    def fetch_availability(self, destination: str, nights: int) -> Dict[str, Any]:
        base = super().fetch_availability(destination, nights)
        base["discovered_endpoint"] = self.endpoint
        return base


@dataclass
class LLMProviderResult:
    provider: str
    answer: Dict[str, Any]
    signature: str
    mode: str


class LLMSubfunctionRouter:
    PROVIDERS = ("ollama", "gemini", "openai", "grok", "mistral", "deepseek")

    def __init__(self, secret: str, real_calls_enabled: Optional[bool] = None) -> None:
        self._secret = secret.encode("utf-8")
        self.real_calls_enabled = (
            os.getenv("DF_HEYLOU_REAL_LLM_ENABLED", "false").lower() == "true"
            if real_calls_enabled is None
            else real_calls_enabled
        )

    def route(self, enriched_context: Dict[str, Any], providers: Optional[List[str]] = None) -> List[LLMProviderResult]:
        chosen = providers or ["ollama", "openai"]
        results = []
        for provider in chosen:
            if provider not in self.PROVIDERS:
                raise ValueError(f"Unsupported provider: {provider}")
            answer = self._mock_answer(provider, enriched_context)
            signature = self._sign(provider, answer, enriched_context)
            results.append(
                LLMProviderResult(
                    provider=provider,
                    answer=answer,
                    signature=signature,
                    mode="real" if self.real_calls_enabled else "sandbox",
                )
            )
        return results

    def cross_validate(self, results: List[LLMProviderResult]) -> bool:
        if len(results) < 2:
            return False
        destination_set = {item.answer["destination"] for item in results}
        budget_flags = {item.answer["within_budget"] for item in results}
        return len(destination_set) == 1 and len(budget_flags) == 1

    def _mock_answer(self, provider: str, enriched_context: Dict[str, Any]) -> Dict[str, Any]:
        request = enriched_context["request"]
        hotels = enriched_context["hotel_candidates"]
        traveler = enriched_context["traveler_profile"]

        best = min(
            hotels,
            key=lambda h: (h["nightly_rate_eur"], h["name"]),
        ) if hotels else None

        total = best["nightly_rate_eur"] * request["nights"] if best else None
        return {
            "provider": provider,
            "destination": request["destination"],
            "recommended_hotel": best["name"] if best else None,
            "estimated_total_eur": total,
            "within_budget": bool(total is not None and total <= traveler["budget_max_eur"] * request["nights"]),
            "reasoning_profile": {
                "ollama": "offline-primary",
                "gemini": "long-context-itinerary",
                "openai": "booking-logic",
                "grok": "disruption-monitoring",
                "mistral": "eu-compliance",
                "deepseek": "cost-routine",
            }[provider],
        }

    def _sign(self, provider: str, answer: Dict[str, Any], enriched_context: Dict[str, Any]) -> str:
        payload = {
            "provider": provider,
            "answer": answer,
            "context": enriched_context,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(self._secret, raw, hashlib.sha256).hexdigest()


@dataclass
class TravelDomainResult:
    request_id: str
    enriched_context: Dict[str, Any]
    adapter_results: List[Dict[str, Any]]
    llm_results: List[LLMProviderResult]
    cross_validated: bool
    audit_event: Dict[str, Any]


class DomainOrchestrator:
    def __init__(
        self,
        knowledge_graph: TravelKnowledgeGraph,
        router: LLMSubfunctionRouter,
        adapters: List[TravelSoftwareAdapter],
        audit_logger: AuditLogger,
    ) -> None:
        self.knowledge_graph = knowledge_graph
        self.router = router
        self.adapters = adapters
        self.audit_logger = audit_logger

    def plan_trip(self, origin: str, destination: str, nights: int, traveler_id: str = "default") -> TravelDomainResult:
        request = {
            "origin": origin,
            "destination": destination,
            "nights": nights,
            "traveler_id": traveler_id,
        }
        enriched = self.knowledge_graph.enrich_request(request)
        adapter_results = [adapter.fetch_availability(destination, nights) for adapter in self.adapters]
        llm_results = self.router.route(enriched, providers=["ollama", "openai"])
        cross_validated = self.router.cross_validate(llm_results)

        request_id = f"heylou-{uuid.uuid4().hex[:12]}"
        audit_event = self.audit_logger.log(
            "travel_plan_created",
            {
                "request_id": request_id,
                "destination": destination,
                "providers": [r.provider for r in llm_results],
                "cross_validated": cross_validated,
            },
        )

        return TravelDomainResult(
            request_id=request_id,
            enriched_context=enriched,
            adapter_results=adapter_results,
            llm_results=llm_results,
            cross_validated=cross_validated,
            audit_event=audit_event,
        )


def build_default_orchestrator(secret: str = "heylou-secret") -> DomainOrchestrator:
    graph = TravelKnowledgeGraph.with_mock_data()
    router = LLMSubfunctionRouter(secret=secret, real_calls_enabled=False)
    adapters: List[TravelSoftwareAdapter] = [
        MEWSAdapter(),
        BookingComAdapter(),
        IdeasRevenueAdapter(),
        GenericAPIAdapter(),
    ]
    audit_logger = AuditLogger(secret=secret)
    return DomainOrchestrator(graph, router, adapters, audit_logger)


def execute_heylou_travel_planning(origin: str, destination: str, nights: int) -> TravelDomainResult:
    orchestrator = build_default_orchestrator()
    return orchestrator.plan_trip(origin=origin, destination=destination, nights=nights)
# [CRUX-MK]
