from __future__ import annotations

import hashlib
import hmac
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_PROVIDERS = (
    "ollama_local",
    "gemini",
    "openai",
    "grok",
    "mistral",
    "deepseek",
)


def _stable_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class AuditLogger:
    @staticmethod
    def sign_payload(payload: Dict[str, Any], secret: str) -> str:
        return hmac.new(
            secret.encode("utf-8"),
            _stable_json(payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def verify_signature(payload: Dict[str, Any], secret: str, signature: str) -> bool:
        expected = AuditLogger.sign_payload(payload, secret)
        return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class HumanGatewayNote:
    system: str
    reason: str
    action: str


class TravelKnowledgeGraph:
    def __init__(self) -> None:
        self.hotels = {
            "berlin": {"name": "HeyLou Berlin Mitte", "stars": 4, "segment": "city"},
            "paris": {"name": "HeyLou Paris Rive Gauche", "stars": 4, "segment": "city"},
            "rome": {"name": "HeyLou Roma Centro", "stars": 4, "segment": "city"},
        }
        self.routes = {
            ("berlin", "paris"): {"mode": "train", "duration_h": 8},
            ("berlin", "rome"): {"mode": "flight", "duration_h": 2},
            ("paris", "rome"): {"mode": "flight", "duration_h": 2},
        }
        self.rates = {
            "city": {"currency": "EUR", "nightly_from": 149},
        }
        self.preferences = {
            "business": {"wifi": True, "breakfast": True, "late_checkin": True},
            "family": {"wifi": True, "breakfast": True, "extra_bed": True},
            "leisure": {"wifi": True, "breakfast": False, "late_checkout": True},
        }

    def enrich(self, request: Dict[str, Any]) -> Dict[str, Any]:
        destination = str(request["destination"]).lower()
        origin = str(request.get("origin", destination)).lower()
        traveler_type = str(request.get("traveler_type", "leisure")).lower()

        hotel = self.hotels.get(destination, {"name": f"HeyLou {destination.title()}", "stars": 4, "segment": "city"})
        route = self.routes.get((origin, destination), {"mode": "unknown", "duration_h": None})
        rate = self.rates.get(hotel["segment"], {"currency": "EUR", "nightly_from": 199})
        prefs = self.preferences.get(traveler_type, self.preferences["leisure"])

        itinerary_key = f"{origin}:{destination}:{request.get('check_in')}:{request.get('nights', 1)}"
        itinerary_id = hashlib.sha256(itinerary_key.encode("utf-8")).hexdigest()[:12]

        return {
            "destination": destination,
            "origin": origin,
            "hotel": hotel,
            "route": route,
            "rate": rate,
            "preferences": prefs,
            "itinerary_id": itinerary_id,
        }


class TravelSoftwareAdapter(ABC):
    name: str = "base"

    def __init__(self, sandbox_mode: bool = True) -> None:
        self.sandbox_mode = sandbox_mode

    def authenticate(self, credentials: Optional[Dict[str, str]]) -> bool:
        return bool(credentials and credentials.get("token") == "valid-token")

    @abstractmethod
    def fetch_offer(self, query: Dict[str, Any], credentials: Optional[Dict[str, str]]) -> Dict[str, Any]:
        raise NotImplementedError


class MEWSAdapter(TravelSoftwareAdapter):
    name = "mews"

    def fetch_offer(self, query: Dict[str, Any], credentials: Optional[Dict[str, str]]) -> Dict[str, Any]:
        if not self.authenticate(credentials):
            return {
                "ok": False,
                "gateway_note": HumanGatewayNote(
                    system="MEWSAdapter",
                    reason="authentication_failed",
                    action="T5-Mensch-Gateway-Inbox informieren und Credentials pruefen",
                ),
            }
        return {
            "ok": True,
            "source": self.name,
            "sandbox_mode": self.sandbox_mode,
            "offer_code": f"MEWS-{query['itinerary_id']}",
            "nightly_rate": query["rate"]["nightly_from"],
        }


class BookingComAdapter(TravelSoftwareAdapter):
    name = "booking_com"

    def fetch_offer(self, query: Dict[str, Any], credentials: Optional[Dict[str, str]]) -> Dict[str, Any]:
        if not self.authenticate(credentials):
            return {
                "ok": False,
                "gateway_note": HumanGatewayNote(
                    system="BookingComAdapter",
                    reason="authentication_failed",
                    action="T5-Mensch-Gateway-Inbox informieren und OTA-Token erneuern",
                ),
            }
        return {
            "ok": True,
            "source": self.name,
            "sandbox_mode": self.sandbox_mode,
            "offer_code": f"BCOM-{query['itinerary_id']}",
            "nightly_rate": query["rate"]["nightly_from"] + 5,
        }


class IdeasRevenueAdapter(TravelSoftwareAdapter):
    name = "ideas_revenue"

    def fetch_offer(self, query: Dict[str, Any], credentials: Optional[Dict[str, str]]) -> Dict[str, Any]:
        if not self.authenticate(credentials):
            return {
                "ok": False,
                "gateway_note": HumanGatewayNote(
                    system="IdeasRevenueAdapter",
                    reason="authentication_failed",
                    action="T5-Mensch-Gateway-Inbox informieren und RMS-Zugang pruefen",
                ),
            }
        uplift = 12 if query["preferences"].get("breakfast") else 0
        return {
            "ok": True,
            "source": self.name,
            "sandbox_mode": self.sandbox_mode,
            "recommended_rate": query["rate"]["nightly_from"] + uplift,
        }


class GenericAPIAdapter(TravelSoftwareAdapter):
    name = "generic_api"

    def discover_endpoints(self, base_url: str) -> List[str]:
        base = base_url.rstrip("/")
        return [f"{base}/health", f"{base}/offers", f"{base}/bookings"]

    def fetch_offer(self, query: Dict[str, Any], credentials: Optional[Dict[str, str]]) -> Dict[str, Any]:
        if not self.authenticate(credentials):
            return {
                "ok": False,
                "gateway_note": HumanGatewayNote(
                    system="GenericAPIAdapter",
                    reason="authentication_failed",
                    action="T5-Mensch-Gateway-Inbox informieren und Skeleton-Key-Auth reparieren",
                ),
            }
        return {
            "ok": True,
            "source": self.name,
            "sandbox_mode": self.sandbox_mode,
            "endpoints": self.discover_endpoints("https://mock.heylou.local"),
            "offer_code": f"GEN-{query['itinerary_id']}",
            "nightly_rate": query["rate"]["nightly_from"],
        }


def build_adapter(name: str, sandbox_mode: bool = True) -> TravelSoftwareAdapter:
    adapters = {
        "mews": MEWSAdapter,
        "booking_com": BookingComAdapter,
        "ideas_revenue": IdeasRevenueAdapter,
        "generic_api": GenericAPIAdapter,
    }
    try:
        return adapters[name](sandbox_mode=sandbox_mode)
    except KeyError as exc:
        raise ValueError(f"unknown adapter: {name}") from exc


class LLMSubfunctionRouter:
    def __init__(self, secret: str, providers: Iterable[str] = DEFAULT_PROVIDERS) -> None:
        self.secret = secret
        self.providers = tuple(providers)

    @staticmethod
    def _is_real_calls_enabled() -> bool:
        return os.getenv("DF_HEYLOU_REAL_LLM_ENABLED", "").lower() == "true"

    @staticmethod
    def _has_ticket() -> bool:
        return bool(os.getenv("PHRONESIS_TICKET"))

    def _mock_response(self, provider: str, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        recommendation = {
            "itinerary_id": context["itinerary_id"],
            "hotel_name": context["hotel"]["name"],
            "destination": context["destination"],
            "nightly_rate": context["rate"]["nightly_from"],
        }
        reasoning = f"{provider} validated travel plan for {context['destination']}"
        return {
            "provider": provider,
            "mode": "mock" if not self._is_real_calls_enabled() else "real-gated",
            "reasoning": reasoning,
            "recommendation": recommendation,
            "task_type": task.get("task_type", "plan_trip"),
        }

    def _signed_call(self, provider: str, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        envelope = {
            "provider": provider,
            "task": task,
            "context": context,
            "sandbox_mode": not (self._is_real_calls_enabled() and self._has_ticket()),
        }
        signature = AuditLogger.sign_payload(envelope, self.secret)
        response = self._mock_response(provider, task, context)
        return {
            "request_envelope": envelope,
            "signature": signature,
            "response": response,
        }

    def route(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any],
        primary_provider: str = "ollama_local",
    ) -> Dict[str, Any]:
        if primary_provider not in self.providers:
            raise ValueError(f"unknown provider: {primary_provider}")

        criticality = str(task.get("criticality", "")).upper()
        require_cross_validation = criticality in {"K_0", "Q_0"}

        providers_used = [primary_provider]
        if require_cross_validation:
            for provider in self.providers:
                if provider != primary_provider:
                    providers_used.append(provider)
                if len(providers_used) >= 2:
                    break

        calls = [self._signed_call(provider, task, context) for provider in providers_used]
        recommendations = [call["response"]["recommendation"] for call in calls]
        consensus = len({ _stable_json(r) for r in recommendations }) == 1

        return {
            "sandbox_mode": not (self._is_real_calls_enabled() and self._has_ticket()),
            "primary_provider": primary_provider,
            "providers_used": providers_used,
            "cross_validated": require_cross_validation,
            "consensus": consensus,
            "calls": calls,
            "final_recommendation": recommendations[0],
        }


def plan_trip(
    request: Dict[str, Any],
    *,
    adapter_name: str = "generic_api",
    primary_provider: str = "ollama_local",
    credentials: Optional[Dict[str, str]] = None,
    secret: str = "heylou-dev-secret",
) -> Dict[str, Any]:
    graph = TravelKnowledgeGraph()
    context = graph.enrich(request)

    adapter = build_adapter(adapter_name, sandbox_mode=True)
    adapter_result = adapter.fetch_offer(context, credentials)

    router = LLMSubfunctionRouter(secret=secret)
    llm_result = router.route(
        task={
            "task_type": "plan_trip",
            "criticality": request.get("criticality", "K_1"),
        },
        context=context,
        primary_provider=primary_provider,
    )

    return {
        "request": request,
        "context": context,
        "adapter_result": adapter_result,
        "llm_result": llm_result,
    }
# [CRUX-MK]
