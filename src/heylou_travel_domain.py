"""heylou_travel_domain.py - Travel Domain Kernel with Skeleton-Key-Adapter and 6-LLM-Sub-Function-Routing.

Implementation per DF-HeyLou-Travel-Domain CRUX-MK Spec.
Stdlib only, Python 3.10+ compatible.
"""

import hashlib
import hmac
import json
import random
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional, Dict, List, Tuple
from enum import Enum, auto

# ─── Constants ───────────────────────────────────────────────────────────────
HMAC_SECRET = b"heylou-travel-domain-skeleton-key-seed-2026"
HMAC_ALGORITHM = "sha256"
REAL_LLM_ENABLED = False  # Sandbox default
MIN_CROSS_VALIDATION = 2
VALID_PROVIDERS = ["ollama_local", "gemini", "openai", "grok", "mistral", "deepseek"]

# ─── Domain Data Structures ──────────────────────────────────────────────────

@dataclass
class Hotel:
    id: str
    name: str
    city: str
    country: str
    lat: float
    lng: float
    rating: float = 0.0
    amenities: List[str] = field(default_factory=list)

@dataclass
class Route:
    origin: str
    destination: str
    mode: str = "flight"  # flight, train, car, bus
    duration_min: int = 0
    price_eur: float = 0.0

@dataclass
class Rate:
    hotel_id: str
    room_type: str
    price_per_night: float
    currency: str = "EUR"
    available: bool = True

@dataclass
class TravelPreference:
    user_id: str
    preferred_cities: List[str] = field(default_factory=list)
    max_budget: float = 500.0
    amenities_wanted: List[str] = field(default_factory=list)
    transport_mode: str = "flight"

# ─── Travel Knowledge Graph ─────────────────────────────────────────────────

class TravelKnowledgeGraph:
    """In-Memory mock knowledge graph for travel domain."""
    
    def __init__(self):
        self.hotels: Dict[str, Hotel] = {}
        self.routes: List[Route] = []
        self.rates: Dict[str, List[Rate]] = {}
        self.preferences: Dict[str, TravelPreference] = {}
        self._seed_mock_data()
    
    def _seed_mock_data(self):
        # Mock hotels
        hotels_data = [
            Hotel("h1", "Grand Central", "Berlin", "Germany", 52.52, 13.405, 4.5, ["wifi", "breakfast", "gym"]),
            Hotel("h2", "Seaside Resort", "Barcelona", "Spain", 41.3874, 2.1686, 4.8, ["pool", "wifi", "spa", "breakfast"]),
            Hotel("h3", "Alpine Lodge", "Innsbruck", "Austria", 47.2692, 11.4041, 4.2, ["wifi", "ski_storage", "restaurant"]),
            Hotel("h4", "Business Inn", "Frankfurt", "Germany", 50.1109, 8.6821, 3.9, ["wifi", "meeting_rooms", "breakfast"]),
        ]
        for hotel in hotels_data:
            self.hotels[hotel.id] = hotel
        
        # Mock routes
        self.routes = [
            Route("Berlin", "Barcelona", "flight", 150, 89.99),
            Route("Berlin", "Innsbruck", "train", 360, 49.99),
            Route("Barcelona", "Berlin", "flight", 145, 79.99),
            Route("Frankfurt", "Innsbruck", "car", 300, 35.00),
        ]
        
        # Mock rates
        self.rates = {
            "h1": [
                Rate("h1", "single", 89.00),
                Rate("h1", "double", 129.00),
                Rate("h1", "suite", 199.00),
            ],
            "h2": [
                Rate("h2", "standard", 120.00),
                Rate("h2", "deluxe", 180.00, available=True),
                Rate("h2", "penthouse", 350.00, available=False),
            ],
            "h3": [
                Rate("h3", "single", 75.00),
                Rate("h3", "double", 110.00),
            ],
        }
        
        # Mock preferences
        self.preferences["user_001"] = TravelPreference(
            user_id="user_001",
            preferred_cities=["Barcelona", "Innsbruck"],
            max_budget=200.0,
            amenities_wanted=["wifi"],
        )
    
    def get_hotel(self, hotel_id: str) -> Optional[Hotel]:
        return self.hotels.get(hotel_id)
    
    def search_hotels_by_city(self, city: str) -> List[Hotel]:
        return [h for h in self.hotels.values() if h.city.lower() == city.lower()]
    
    def get_rates_for_hotel(self, hotel_id: str) -> List[Rate]:
        return self.rates.get(hotel_id, [])
    
    def find_routes(self, origin: str, destination: str) -> List[Route]:
        return [
            r for r in self.routes
            if r.origin.lower() == origin.lower() and r.destination.lower() == destination.lower()
        ]
    
    def get_context_for_llm(self, user_id: str = "") -> str:
        """Generate JSON context string for LLM enrichment."""
        context = {
            "available_hotels": [asdict(h) for h in self.hotels.values()],
            "available_routes": [asdict(r) for r in self.routes],
            "rate_summary": {
                hid: [asdict(r) for r in rates]
                for hid, rates in self.rates.items()
            },
        }
        if user_id and user_id in self.preferences:
            context["user_preferences"] = asdict(self.preferences[user_id])
        return json.dumps(context, indent=2, default=str)


# ─── Skeleton Key Adapter ────────────────────────────────────────────────────

class AdapterStatus(Enum):
    MOCK = auto()
    REAL = auto()
    AUTH_FAILURE = auto()

@dataclass
class AdapterResult:
    success: bool
    data: Any = None
    status: AdapterStatus = AdapterStatus.MOCK
    message: str = ""

class TravelSoftwareAdapter:
    """Base adapter for all travel software integrations.
    
    Implements skeleton-key-pattern for endpoint discovery and auth.
    """
    
    def __init__(self, name: str, mock_data: Optional[Dict] = None):
        self.name = name
        self._mock_data = mock_data or {}
        self._status = AdapterStatus.MOCK
        self._auth_token = self._generate_skeleton_key("adapter_auth")
    
    def _generate_skeleton_key(self, seed: str) -> str:
        """Generate skeleton key for adapter."""
        return hmac.new(HMAC_SECRET, seed.encode(), hashlib.sha256).hexdigest()[:32]
    
    def discover_endpoints(self) -> List[str]:
        """Endpoint discovery - skeleton key pattern."""
        return [
            f"{self.name}/v1/hotels",
            f"{self.name}/v1/rates",
            f"{self.name}/v1/bookings",
        ]
    
    def query(self, endpoint: str, params: Optional[Dict] = None) -> AdapterResult:
        """Mock query with skeleton key auth."""
        if self._status == AdapterStatus.AUTH_FAILURE:
            return AdapterResult(
                success=False,
                status=AdapterStatus.AUTH_FAILURE,
                message=f"Auth failed for {self.name}. Skeleton key invalid."
            )
        # Mock response based on endpoint
        return AdapterResult(
            success=True,
            data=self._mock_data.get(endpoint, {"mock": True, "adapter": self.name}),
            status=self._status,
        )
    
    def set_auth_failure(self):
        """Induce auth failure for testing."""
        self._status = AdapterStatus.AUTH_FAILURE


class MEWSAdapter(TravelSoftwareAdapter):
    def __init__(self):
        super().__init__("mews_pms", {
            "mews_pms/v1/hotels": {"hotels": [{"id": "m1", "name": "Mews Test Hotel"}]},
            "mews_pms/v1/rates": {"rates": [{"room": "standard", "price": 99.0}]},
        })


class BookingComAdapter(TravelSoftwareAdapter):
    def __init__(self):
        super().__init__("booking_com_ota", {
            "booking_com_ota/v1/hotels": {"hotels": [{"id": "b1", "name": "Booking Test Hotel"}]},
        })


class IdeasRevenueAdapter(TravelSoftwareAdapter):
    def __init__(self):
        super().__init__("ideas_revenue_rms", {
            "ideas_revenue_rms/v1/rates": {"recommended_rates": {"single": 85.0, "double": 130.0}},
        })


class GenericAPIAdapter(TravelSoftwareAdapter):
    """Skeleton-key pattern adapter for any third-party API."""
    
    def __init__(self, base_url: str = "https://api.generic-travel.com"):
        super().__init__(f"generic_api_{hash(base_url) % 10000}")
        self.base_url = base_url
        self._endpoint_map: Dict[str, str] = {}
    
    def register_endpoint(self, logical_name: str, full_path: str):
        self._endpoint_map[logical_name] = full_path
        self._mock_data[full_path] = {"discovered": True, "base_url": self.base_url}


# ─── LLM Sub-Function Router ────────────────────────────────────────────────

@dataclass
class LLMRequest:
    provider: str
    prompt: str
    context: str = ""
    temperature: float = 0.7
    user_id: str = ""

@dataclass
class LLMResponse:
    provider: str
    content: str
    hmac_signature: str
    validated_by: List[str] = field(default_factory=list)
    sandbox: bool = True

class LLMSubFunctionRouter:
    """Routes LLM requests across 6 providers with HMAC signing and cross-validation."""
    
    def __init__(self, knowledge_graph: TravelKnowledgeGraph):
        self.knowledge_graph = knowledge_graph
        # Mock response generators per provider
        self._mock_handlers: Dict[str, Callable[[LLMRequest], str]] = {
            "ollama_local": self._mock_ollama,
            "gemini": self._mock_gemini,
            "openai": self._mock_openai,
            "grok": self._mock_grok,
            "mistral": self._mock_mistral,
            "deepseek": self._mock_deepseek,
        }
    
    def _sign_request(self, request: LLMRequest) -> str:
        """HMAC-SHA256 signing for provenance."""
        payload = json.dumps(asdict(request), sort_keys=True).encode()
        return hmac.new(HMAC_SECRET, payload, hashlib.sha256).hexdigest()
    
    def _mock_ollama(self, request: LLMRequest) -> str:
        return f"[Ollama-Local] Travel recommendation based on context: {len(request.context)} chars analyzed."
    
    def _mock_gemini(self, request: LLMRequest) -> str:
        return f"[Gemini] Long-context itinerary for {request.user_id or 'guest'} with {len(request.context)} chars context."
    
    def _mock_openai(self, request: LLMRequest) -> str:
        return f"[OpenAI] Booking logic reasoning: optimal choice from {self.knowledge_graph.hotels} hotels."
    
    def _mock_grok(self, request: LLMRequest) -> str:
        return "[Grok] Real-time travel disruption: No disruptions detected on queried routes."
    
    def _mock_mistral(self, request: LLMRequest) -> str:
        return "[Mistral] EU-DSGVO-compliant travel suggestion: Data processed within EU."
    
    def _mock_deepseek(self, request: LLMRequest) -> str:
        return f"[DeepSeek] Cost-effective routine: Cheapest options for {request.prompt[:50]}..."
    
    def call_llm(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM call with travel domain context enrichment."""
        # Validate provider
        if request.provider not in VALID_PROVIDERS:
            raise ValueError(f"Invalid provider: {request.provider}. Must be one of {VALID_PROVIDERS}")
        
        # Enrich with travel knowledge graph context
        if not request.context:
            request.context = self.knowledge_graph.get_context_for_llm(request.user_id)
        
        # Sandbox mode - use mock handlers
        handler = self._mock_handlers.get(request.provider)
        if handler is None:
            raise ValueError(f"No handler for provider: {request.provider}")
        
        content = handler(request)
        signature = self._sign_request(request)
        
        # Cross-validation simulation (in sandbox, always successful)
        validated_by = [request.provider]
        if MIN_CROSS_VALIDATION > 1:
            # Simulate cross-validation with random other providers
            others = [p for p in VALID_PROVIDERS if p != request.provider]
            validated_by.extend(random.sample(others, min(MIN_CROSS_VALIDATION - 1, len(others))))
        
        return LLMResponse(
            provider=request.provider,
            content=content,
            hmac_signature=signature,
            validated_by=validated_by,
            sandbox=True,
        )
    
    def cross_validate(self, responses: List[LLMResponse]) -> Dict[str, bool]:
        """Cross-validate multiple LLM responses (K_0/Q_0 proximity check)."""
        result = {}
        for resp in responses:
            # In sandbox: check that signature is valid HMAC format
            valid = bool(resp.hmac_signature and len(resp.hmac_signature) == 64)
            result[resp.provider] = valid
        return result


# ─── Domain Orchestrator ─────────────────────────────────────────────────────

class DomainOrchestrator:
    """5-Phase Loop orchestrator for travel domain operations."""
    
    def __init__(self):
        self.knowledge_graph = TravelKnowledgeGraph()
        self.llm_router = LLMSubFunctionRouter(self.knowledge_graph)
        self.adapters: Dict[str, TravelSoftwareAdapter] = {
            "mews": MEWSAdapter(),
            "booking": BookingComAdapter(),
            "ideas": IdeasRevenueAdapter(),
            "generic": GenericAPIAdapter(),
        }
        self.audit_log: List[dict] = []
    
    def phase_discover(self) -> dict:
        """Phase 1: Discover available endpoints and data."""
        results = {}
        for name, adapter in self.adapters.items():
            results[name] = {
                "endpoints": adapter.discover_endpoints(),
                "status": adapter._status.name,
            }
        return {"phase": "discover", "results": results}
    
    def phase_enrich(self, user_id: str = "") -> dict:
        """Phase 2: Enrich with travel knowledge graph."""
        context = self.knowledge_graph.get_context_for_llm(user_id)
        return {"phase": "enrich", "context_length": len(context), "user_id": user_id}
    
    def phase_route_llm(self, prompt: str, user_id: str = "") -> List[LLMResponse]:
        """Phase 3: Route prompt to all LLM providers for parallel analysis."""
        responses = []
        for provider in VALID_PROVIDERS:
            request = LLMRequest(
                provider=provider,
                prompt=prompt,
                user_id=user_id,
            )
            response = self.llm_router.call_llm(request)
            responses.append(response)
            self._log_audit("llm_call", {"provider": provider, "signature": response.hmac_signature})
        return responses
    
    def phase_cross_validate(self, responses: List[LLMResponse]) -> dict:
        """Phase 4: Cross-validate responses."""
        validation = self.llm_router.cross_validate(responses)
        self._log_audit("cross_validation", validation)
        return {"phase": "cross_validate", "validation": validation, "all_passed": all(validation.values())}
    
    def phase_aggregate(self, responses: List[LLMResponse]) -> dict:
        """Phase 5: Aggregate responses into unified result."""
        aggregated = {
            "providers_used": [r.provider for r in responses],
            "consensus": responses[0].content if responses else "No responses",
            "signed_count": sum(1 for r in responses if r.hmac_signature),
            "sandbox_mode": all(r.sandbox for r in responses),
        }
        self._log_audit("aggregate", aggregated)
        return {"phase": "aggregate", "result": aggregated}
    
    def run_full_cycle(self, prompt: str, user_id: str = "") -> dict:
        """Run all 5 phases in sequence."""
        p1 = self.phase_discover()
        p2 = self.phase_enrich(user_id)
        p3 = self.phase_route_llm(prompt, user_id)
        p4 = self.phase_cross_validate(p3)
        p5 = self.phase_aggregate(p3)
        return {"phases": [p1, p2, p4, p5], "llm_responses": [asdict(r) for r in p3]}
    
    def _log_audit(self, action: str, data: dict):
        """Append to audit log (HMAC-signed entries)."""
        entry = {
            "action": action,
            "data": data,
            "hmac": hmac.new(HMAC_SECRET, json.dumps(data, sort_keys=True).encode(), hashlib.sha256).hexdigest(),
        }
        self.audit_log.append(entry)
    
    def get_audit_log(self) -> List[dict]:
        return self.audit_log.copy()
# [CRUX-MK]
