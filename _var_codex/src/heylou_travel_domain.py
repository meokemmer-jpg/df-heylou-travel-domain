from __future__ import annotations

import abc
import datetime as _dt
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TravelQuery:
    origin: str
    destination: str
    check_in: str
    check_out: str
    guests: int
    budget_eur: int
    intent: str = "hotel_search"
    hotel_name: Optional[str] = None


class AuditLogger:
    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")
        self.events: List[Dict[str, Any]] = []

    @staticmethod
    def _canonical(payload: Dict[str, Any]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign(self, payload: Dict[str, Any]) -> str:
        return hmac.new(self._secret, self._canonical(payload), hashlib.sha256).hexdigest()

    def record(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        entry = {
            "event_type": event_type,
            "payload": payload,
            "timestamp": _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
        entry["signature"] = self.sign(entry["payload"])
        self.events.append(entry)
        return entry


class TravelKnowledgeGraph:
    def __init__(self) -> None:
        self.hotels = {
            "Berlin": [
                {"name": "Mock Hotel Alexanderplatz", "stars": 4, "nightly_rate_eur": 145},
                {"name": "Mock Hotel Tiergarten", "stars": 3, "nightly_rate_eur": 110},
            ],
            "Paris": [
                {"name": "Mock Hotel Louvre", "stars": 4, "nightly_rate_eur": 210},
                {"name": "Mock Hotel Bastille", "stars": 3, "nightly_rate_eur": 160},
            ],
        }
        self.routes = {
            ("Hamburg", "Berlin"): {"mode": "rail", "duration_hours": 1.9},
            ("Munich", "Paris"): {"mode": "air", "duration_hours": 1.6},
        }
        self.preferences = {
            "default": {
                "quiet_hours": "22:00-07:00",
                "refund_policy": "flexible-mock",
                "provider_policy": "sandbox-default",
            }
        }

    def enrich(self, query: TravelQuery) -> Dict[str, Any]:
        hotels = list(self.hotels.get(query.destination, []))
        if query.hotel_name:
            hotels = [h for h in hotels if h["name"] == query.hotel_name]
        route = self.routes.get((query.origin, query.destination), {"mode": "unknown", "duration_hours": None})
        return {
            "query": {
                "origin": query.origin,
                "destination": query.destination,
                "check_in": query.check_in,
                "check_out": query.check_out,
                "guests": query.guests,
                "budget_eur": query.budget_eur,
                "intent": query.intent,
                "hotel_name": query.hotel_name,
            },
            "hotels": hotels,
            "route": route,
            "preferences": self.preferences["default"],
        }


class TravelSoftwareAdapter(abc.ABC):
    def __init__(self, adapter_name: str, sandbox_mode: bool = True) -> None:
        self.adapter_name = adapter_name
        self.sandbox_mode = sandbox_mode

    def authenticate(self, credentials: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        credentials = credentials or {}
        if credentials.get("token") == "valid-mock-token":
            return {"ok": True, "adapter": self.adapter_name}
        return {
            "ok": False,
            "adapter": self.adapter_name,
            "gateway_note": "T5-Mensch-Gateway-Inbox-Note: adapter auth failure",
        }

    @abc.abstractmethod
    def fetch_quote(self, query: TravelQuery, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class MEWSAdapter(TravelSoftwareAdapter):
    def __init__(self, sandbox_mode: bool = True) -> None:
        super().__init__("MEWS", sandbox_mode=sandbox_mode)

    def fetch_quote(self, query: TravelQuery, context: Dict[str, Any]) -> Dict[str, Any]:
        hotel = (context["hotels"] or [{"name": "MEWS Mock Hotel", "nightly_rate_eur": 130}])[0]
        return {
            "adapter": self.adapter_name,
            "mode": "mock" if self.sandbox_mode else "live",
            "hotel": hotel["name"],
            "nightly_rate_eur": hotel["nightly_rate_eur"],
        }


class BookingComAdapter(TravelSoftwareAdapter):
    def __init__(self, sandbox_mode: bool = True) -> None:
        super().__init__("BookingCom", sandbox_mode=sandbox_mode)

    def fetch_quote(self, query: TravelQuery, context: Dict[str, Any]) -> Dict[str, Any]:
        hotel = (context["hotels"] or [{"name": "Booking Mock Hotel", "nightly_rate_eur": 135}])[0]
        return {
            "adapter": self.adapter_name,
            "mode": "mock" if self.sandbox_mode else "live",
            "hotel": hotel["name"],
            "nightly_rate_eur": hotel["nightly_rate_eur"] + 5,
        }


class IdeasRevenueAdapter(TravelSoftwareAdapter):
    def __init__(self, sandbox_mode: bool = True) -> None:
        super().__init__("IdeasRevenue", sandbox_mode=sandbox_mode)

    def fetch_quote(self, query: TravelQuery, context: Dict[str, Any]) -> Dict[str, Any]:
        base = (context["hotels"] or [{"nightly_rate_eur": 120}])[0]["nightly_rate_eur"]
        return {
            "adapter": self.adapter_name,
            "mode": "mock" if self.sandbox_mode else "live",
            "recommended_rate_eur": int(base * 1.08),
            "yield_signal": "hold-rate",
        }


class GenericAPIAdapter(TravelSoftwareAdapter):
    def __init__(self, base_url: str, sandbox_mode: bool = True) -> None:
        super().__init__("GenericAPI", sandbox_mode=sandbox_mode)
        self.base_url = base_url.rstrip("/")

    def discover_endpoints(self) -> Dict[str, str]:
        return {
            "availability": f"{self.base_url}/availability",
            "rates": f"{self.base_url}/rates",
            "bookings": f"{self.base_url}/bookings",
        }

    def fetch_quote(self, query: TravelQuery, context: Dict[str, Any]) -> Dict[str, Any]:
        endpoints = self.discover_endpoints()
        hotel = (context["hotels"] or [{"name": "Generic Mock Hotel", "nightly_rate_eur": 125}])[0]
        return {
            "adapter": self.adapter_name,
            "mode": "mock" if self.sandbox_mode else "live",
            "hotel": hotel["name"],
            "nightly_rate_eur": hotel["nightly_rate_eur"],
            "discovered_endpoints": endpoints,
        }


class LLMSubfunctionRouter:
    PROVIDERS = (
        "ollama-local",
        "gemini",
        "openai",
        "grok",
        "mistral",
        "deepseek",
    )

    def __init__(self, audit_logger: AuditLogger) -> None:
        self.audit_logger = audit_logger

    def _provider_response(self, provider: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        hotels = context.get("hotels") or []
        top_hotel = hotels[0]["name"] if hotels else "No Hotel Found"
        rationale = {
            "ollama-local": "local-primary",
            "gemini": "long-context-itinerary",
            "openai": "booking-logic",
            "grok": "disruption-scan",
            "mistral": "eu-compliance",
            "deepseek": "cost-routine",
        }[provider]
        return {
            "provider": provider,
            "task": task,
            "recommendation": top_hotel,
            "rationale": rationale,
        }

    def route(
        self,
        task: str,
        context: Dict[str, Any],
        *,
        k0_q0_proximity: float = 1.0,
        phronesis_ticket: Optional[str] = None,
    ) -> Dict[str, Any]:
        real_enabled = os.environ.get("DF_HEYLOU_REAL_LLM_ENABLED", "").lower() == "true"
        mode = "real" if real_enabled and phronesis_ticket else "sandbox"

        providers = ["ollama-local"]
        if k0_q0_proximity <= 0.20:
            providers.append("openai")

        outputs = [self._provider_response(provider, task, context) for provider in providers]
        payload = {
            "task": task,
            "mode": mode,
            "providers": providers,
            "context_hash": hashlib.sha256(
                json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        }
        signature = self.audit_logger.sign(payload)
        self.audit_logger.record("llm_route", payload)

        return {
            "mode": mode,
            "providers_used": providers,
            "cross_validated": len(providers) >= 2,
            "outputs": outputs,
            "signature": signature,
        }


class TravelDomainOrchestrator:
    def __init__(
        self,
        knowledge_graph: Optional[TravelKnowledgeGraph] = None,
        router: Optional[LLMSubfunctionRouter] = None,
        adapter: Optional[TravelSoftwareAdapter] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self.audit_logger = audit_logger or AuditLogger("heylou-default-secret")
        self.knowledge_graph = knowledge_graph or TravelKnowledgeGraph()
        self.router = router or LLMSubfunctionRouter(self.audit_logger)
        self.adapter = adapter or GenericAPIAdapter("https://mock.heylou.local", sandbox_mode=True)

    def execute(
        self,
        query: TravelQuery,
        *,
        k0_q0_proximity: float = 1.0,
        phronesis_ticket: Optional[str] = None,
    ) -> Dict[str, Any]:
        context = self.knowledge_graph.enrich(query)
        quote = self.adapter.fetch_quote(query, context)
        llm = self.router.route(
            task=query.intent,
            context=context,
            k0_q0_proximity=k0_q0_proximity,
            phronesis_ticket=phronesis_ticket,
        )
        result = {
            "query": context["query"],
            "quote": quote,
            "llm": llm,
            "route": context["route"],
            "hotel_candidates": [hotel["name"] for hotel in context["hotels"]],
        }
        self.audit_logger.record("travel_orchestration", result)
        return result


def run_heylou_travel_domain(
    query: TravelQuery,
    *,
    secret: str = "heylou-secret",
    adapter: Optional[TravelSoftwareAdapter] = None,
    k0_q0_proximity: float = 1.0,
    phronesis_ticket: Optional[str] = None,
) -> Dict[str, Any]:
    audit = AuditLogger(secret)
    orchestrator = TravelDomainOrchestrator(
        knowledge_graph=TravelKnowledgeGraph(),
        router=LLMSubfunctionRouter(audit),
        adapter=adapter or GenericAPIAdapter("https://mock.heylou.local", sandbox_mode=True),
        audit_logger=audit,
    )
    return orchestrator.execute(
        query,
        k0_q0_proximity=k0_q0_proximity,
        phronesis_ticket=phronesis_ticket,
    )


__all__ = [
    "AuditLogger",
    "BookingComAdapter",
    "GenericAPIAdapter",
    "IdeasRevenueAdapter",
    "LLMSubfunctionRouter",
    "MEWSAdapter",
    "TravelDomainOrchestrator",
    "TravelKnowledgeGraph",
    "TravelQuery",
    "TravelSoftwareAdapter",
    "run_heylou_travel_domain",
]
# [CRUX-MK]
