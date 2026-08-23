import hashlib
import hmac
import json
import os
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse


# === Konfiguration ===
DF_HEYLOU_REAL_LLM_ENABLED = os.environ.get("DF_HEYLOU_REAL_LLM_ENABLED", "false").lower() == "true"
PHRONESIS_TICKET = os.environ.get("PHRONESIS_TICKET", "")
HMAC_SECRET = os.environ.get("DF_HEYLOU_HMAC_SECRET", "df-heylou-travel-secret-2026").encode("utf-8")


# == Travel Knowledge Graph (In-Memory Mock) ==

@dataclass
class Hotel:
    id: str
    name: str
    city: str
    country: str
    stars: int
    amenities: List[str]
    base_rate: float

@dataclass
class Route:
    id: str
    from_city: str
    to_city: str
    transport_type: str  # flight, train, bus
    duration_minutes: int
    base_price: float

@dataclass
class TravelPreference:
    user_id: str
    preferred_airlines: List[str]
    min_stars: int
    max_budget: float
    amenities_required: List[str]


class TravelKnowledgeGraph:
    """In-Memory Travel Knowledge Graph mit Mock-Daten."""
    
    def __init__(self):
        self.hotels: Dict[str, Hotel] = {}
        self.routes: Dict[str, Route] = {}
        self.preferences: Dict[str, TravelPreference] = {}
        self._load_mock_data()
    
    def _load_mock_data(self):
        # Mock Hotels
        self.hotels["H-001"] = Hotel("H-001", "Grand Palace Hotel", "Berlin", "Deutschland", 5, ["Pool", "Spa", "Frühstück", "WLAN"], 250.00)
        self.hotels["H-002"] = Hotel("H-002", "City Comfort Inn", "Berlin", "Deutschland", 3, ["WLAN", "Frühstück"], 89.00)
        self.hotels["H-003"] = Hotel("H-003", "Alpine Lodge", "Zürich", "Schweiz", 4, ["Pool", "Sauna", "WLAN", "Restaurant"], 180.00)
        self.hotels["H-004"] = Hotel("H-004", "Sea View Resort", "Barcelona", "Spanien", 4, ["Pool", "Strandzugang", "WLAN", "All-Inclusive"], 300.00)
        self.hotels["H-005"] = Hotel("H-005", "Budget Sleep", "Paris", "Frankreich", 2, ["WLAN"], 45.00)
        
        # Mock Routes
        self.routes["R-001"] = Route("R-001", "Berlin", "Zürich", "flight", 90, 120.00)
        self.routes["R-002"] = Route("R-002", "Berlin", "Paris", "train", 480, 80.00)
        self.routes["R-003"] = Route("R-003", "Zürich", "Barcelona", "flight", 120, 150.00)
        self.routes["R-004"] = Route("R-004", "Paris", "Barcelona", "train", 360, 60.00)
        self.routes["R-005"] = Route("R-005", "Berlin", "Barcelona", "flight", 150, 180.00)
        
        # Mock Preferences
        self.preferences["U-001"] = TravelPreference("U-001", ["Lufthansa", "Swiss"], 3, 500.00, ["WLAN"])
        self.preferences["U-002"] = TravelPreference("U-002", ["Ryanair"], 2, 100.00, ["WLAN", "Frühstück"])
    
    def get_hotel(self, hotel_id: str) -> Optional[Hotel]:
        return self.hotels.get(hotel_id)
    
    def search_hotels(self, city: Optional[str] = None, min_stars: int = 1, max_budget: float = 10000.0) -> List[Hotel]:
        results = []
        for h in self.hotels.values():
            if city and h.city.lower() != city.lower():
                continue
            if h.stars < min_stars:
                continue
            if h.base_rate > max_budget:
                continue
            results.append(h)
        return results
    
    def get_route(self, route_id: str) -> Optional[Route]:
        return self.routes.get(route_id)
    
    def find_routes(self, from_city: str, to_city: str) -> List[Route]:
        results = []
        for r in self.routes.values():
            if r.from_city.lower() == from_city.lower() and r.to_city.lower() == to_city.lower():
                results.append(r)
        return results
    
    def get_preference(self, user_id: str) -> Optional[TravelPreference]:
        return self.preferences.get(user_id)


# == Skeleton-Key-Adapter Pattern ==

class TravelSoftwareAdapter:
    """Basis-Adapter für Travel-Software-Schnittstellen."""
    
    def __init__(self, endpoint: str = "https://mock.api/"):
        self.endpoint = endpoint
        self._connected = False
    
    def connect(self) -> bool:
        """Mock-Verbindung herstellen."""
        self._connected = True
        return True
    
    def disconnect(self) -> bool:
        self._connected = False
        return True
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Subclass must implement search()")
    
    def book(self, item_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Subclass must implement book()")
    
    def cancel(self, booking_id: str) -> Dict[str, Any]:
        raise NotImplementedError("Subclass must implement cancel()")


class MEWSAdapter(TravelSoftwareAdapter):
    """PMS-Adapter (Mock) - MEWS Industry Standard."""
    
    def __init__(self):
        super().__init__("https://mews.mock.api/v1/")
        self._bookings = {}
        self._booking_counter = 0
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        # Mock: Verfügbarkeit prüfen
        hotel_id = query.get("hotel_id", "H-001")
        check_in = query.get("check_in", "2026-08-01")
        check_out = query.get("check_out", "2026-08-03")
        return {
            "status": "available",
            "hotel_id": hotel_id,
            "check_in": check_in,
            "check_out": check_out,
            "room_types": ["Single", "Double", "Suite"],
            "rates": {"Single": 120.00, "Double": 180.00, "Suite": 350.00}
        }
    
    def book(self, item_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._booking_counter += 1
        booking_id = f"MEWS-BK-{self._booking_counter:04d}"
        self._bookings[booking_id] = {
            "hotel_id": item_id,
            "room_type": params.get("room_type", "Double"),
            "check_in": params.get("check_in", "2026-08-01"),
            "check_out": params.get("check_out", "2026-08-03"),
            "guest_name": params.get("guest_name", "Unknown"),
            "total_amount": params.get("total_amount", 0.0),
            "status": "confirmed"
        }
        return {"booking_id": booking_id, "status": "confirmed", "details": self._bookings[booking_id]}
    
    def cancel(self, booking_id: str) -> Dict[str, Any]:
        if booking_id in self._bookings:
            self._bookings[booking_id]["status"] = "cancelled"
            return {"booking_id": booking_id, "status": "cancelled", "refund": 50.0}
        return {"error": "Booking not found"}


class BookingComAdapter(TravelSoftwareAdapter):
    """OTA-Adapter (Mock) - Booking.com Industry Standard."""
    
    def __init__(self):
        super().__init__("https://booking.mock.api/v2/")
        self._bookings = {}
        self._booking_counter = 0
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        city = query.get("city", "Berlin")
        check_in = query.get("check_in", "2026-08-01")
        check_out = query.get("check_out", "2026-08-03")
        guests = query.get("guests", 1)
        return {
            "status": "success",
            "city": city,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
            "properties": [
                {"id": "P001", "name": "Hotel Berlin Mitte", "stars": 4, "rate": 150.00},
                {"id": "P002", "name": "Budget Hostel", "stars": 2, "rate": 35.00}
            ]
        }
    
    def book(self, item_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._booking_counter += 1
        booking_id = f"BC-BK-{self._booking_counter:04d}"
        self._bookings[booking_id] = {
            "property_id": item_id,
            "room_type": params.get("room_type", "Standard"),
            "check_in": params.get("check_in", "2026-08-01"),
            "check_out": params.get("check_out", "2026-08-03"),
            "total_amount": params.get("total_amount", 0.0),
            "status": "booked"
        }
        return {"booking_id": booking_id, "status": "booked", "details": self._bookings[booking_id]}
    
    def cancel(self, booking_id: str) -> Dict[str, Any]:
        if booking_id in self._bookings:
            self._bookings[booking_id]["status"] = "cancelled"
            return {"booking_id": booking_id, "status": "cancelled", "refund_policy": "free_cancellation"}
        return {"error": "Booking not found"}


class IdeasRevenueAdapter(TravelSoftwareAdapter):
    """RMS-Adapter (Mock) - Ideas Revenue Standard."""
    
    def __init__(self):
        super().__init__("https://ideas.mock.api/rms/v1/")
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        hotel_id = query.get("hotel_id", "H-001")
        date_from = query.get("date_from", "2026-08-01")
        date_to = query.get("date_to", "2026-08-07")
        return {
            "status": "success",
            "hotel_id": hotel_id,
            "period": {"from": date_from, "to": date_to},
            "rate_recommendations": {
                "Single": {"current": 120.00, "recommended": 135.00, "confidence": 0.87},
                "Double": {"current": 180.00, "recommended": 195.00, "confidence": 0.92},
                "Suite": {"current": 350.00, "recommended": 380.00, "confidence": 0.78}
            },
            "occupancy_forecast": 0.72
        }
    
    def book(self, item_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # RMS does not book, only recommends
        return {"status": "rate_recommendation_only", "hotel_id": item_id}
    
    def cancel(self, booking_id: str) -> Dict[str, Any]:
        return {"status": "rate_recommendation_only", "note": "RMS does not handle bookings"}


class GenericAPIAdapter(TravelSoftwareAdapter):
    """Skeleton-Key-Pattern: Generic HTTP-API Connector mit Endpoint-Discovery."""
    
    def __init__(self, base_url: str = "https://generic.travel.api/v1/"):
        super().__init__(base_url)
        self._discovered_endpoints: Dict[str, str] = {}
    
    def discover_endpoints(self) -> Dict[str, str]:
        """Mock: Endpoint-Discovery per Skeleton-Key-Pattern."""
        self._discovered_endpoints = {
            "search": f"{self.endpoint}search",
            "book": f"{self.endpoint}book",
            "cancel": f"{self.endpoint}cancel",
            "status": f"{self.endpoint}status"
        }
        return self._discovered_endpoints
    
    def search(self, query: Dict[str, Any]) -> Dict[str, Any]:
        if not self._discovered_endpoints:
            self.discover_endpoints()
        # Mock Generic API-Call
        return {
            "status": "ok",
            "endpoint_used": self._discovered_endpoints.get("search", "unknown"),
            "results": [{"id": "GEN-001", "name": "Generic Travel Option", "price": 99.99}]
        }
    
    def book(self, item_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._discovered_endpoints:
            self.discover_endpoints()
        booking_id = f"GEN-BK-{random.randint(1000, 9999)}"
        return {
            "status": "confirmed",
            "booking_id": booking_id,
            "endpoint_used": self._discovered_endpoints.get("book", "unknown")
        }
    
    def cancel(self, booking_id: str) -> Dict[str, Any]:
        if not self._discovered_endpoints:
            self.discover_endpoints()
        return {
            "status": "cancelled",
            "booking_id": booking_id,
            "endpoint_used": self._discovered_endpoints.get("cancel", "unknown")
        }


# == LLM Sub-Function Router ==

@dataclass
class LLMResponse:
    provider: str
    content: str
    travel_context: Dict[str, Any]
    hmac_signature: str
    timestamp: float = field(default_factory=time.time)


class LLMProvider:
    """Basis-LLM-Provider mit HMAC-Signing."""
    
    def __init__(self, name: str, provider_type: str):
        self.name = name
        self.provider_type = provider_type  # local, cloud, eu-dsgvo, cost-effective
    
    def _sign(self, content: str, travel_context: Dict[str, Any]) -> str:
        """HMAC-SHA256 Signatur für Provenance."""
        message = json.dumps({"content": content, "context": travel_context}, sort_keys=True)
        return hmac.new(HMAC_SECRET, message.encode("utf-8"), hashlib.sha256).hexdigest()
    
    def _enrich_with_travel_context(self, query: str, graph: TravelKnowledgeGraph) -> str:
        """Reichere Query mit Travel-Knowledge-Graph-Kontext an."""
        context = f"[Travel-Knowledge-Graph: {len(graph.hotels)} Hotels, {len(graph.routes)} Routes, {len(graph.preferences)} Preferences]"
        return f"{context}\n\nUser Query: {query}"
    
    def query(self, query: str, travel_context: Dict[str, Any], graph: TravelKnowledgeGraph) -> LLMResponse:
        """Mock-LLM-Query (Sandbox-Mode)."""
        enriched = self._enrich_with_travel_context(query, graph)
        
        # Mock-Response basierend auf Provider
        if self.name == "Ollama-Local":
            content = f"[Ollama-Local Sandbox] Travel recommendation for: {query[:50]}... | Context: {len(travel_context)} items"
        elif self.name == "Gemini":
            content = f"[Gemini Sandbox] Long-context itinerary analysis: {query[:50]}... | Best option found"
        elif self.name == "OpenAI":
            content = f"[OpenAI Sandbox] Booking logic reasoning: {query[:50]}... | Optimal decision path identified"
        elif self.name == "Grok":
            content = f"[Grok Sandbox] Real-time travel disruption update: {query[:50]}... | No disruptions detected"
        elif self.name == "Mistral":
            content = f"[Mistral Sandbox - EU-DSGVO] Data privacy compliant processing: {query[:50]}... | Preferences applied"
        elif self.name == "DeepSeek":
            content = f"[DeepSeek Sandbox - Cost-Effective] Routine travel query: {query[:50]}... | Standard response"
        else:
            content = f"[Unknown Provider] Mock response for: {query[:50]}"
        
        signature = self._sign(content, travel_context)
        return LLMResponse(
            provider=self.name,
            content=content,
            travel_context=travel_context,
            hmac_signature=signature
        )


class LLMRouter:
    """Router für 6 LLM-Provider mit Sub-Funktion-Pattern."""
    
    def __init__(self, graph: TravelKnowledgeGraph):
        self.graph = graph
        self.providers: Dict[str, LLMProvider] = {
            "Ollama-Local": LLMProvider("Ollama-Local", "local"),
            "Gemini": LLMProvider("Gemini", "cloud"),
            "OpenAI": LLMProvider("OpenAI", "cloud"),
            "Grok": LLMProvider("Grok", "cloud"),
            "Mistral": LLMProvider("Mistral", "eu-dsgvo"),
            "DeepSeek": LLMProvider("DeepSeek", "cost-effective")
        }
        self._call_history: List[LLMResponse] = []
    
    def query_provider(self, provider_name: str, query: str, travel_context: Optional[Dict[str, Any]] = None) -> LLMResponse:
        """Single-Provider Query."""
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(self.providers.keys())}")
        
        if travel_context is None:
            travel_context = {
                "hotels_count": len(self.graph.hotels),
                "routes_count": len(self.graph.routes),
                "preferences_count": len(self.graph.preferences)
            }
        
        # Sandbox-Mode: Immer Mock
        provider = self.providers[provider_name]
        response = provider.query(query, travel_context, self.graph)
        self._call_history.append(response)
        return response
    
    def cross_validate(self, query: str, travel_context: Dict[str, Any], min_providers: int = 2) -> Tuple[List[LLMResponse], bool]:
        """Cross-LLM-Validation: Fragt mindestens 2 Provider."""
        responses = []
        providers_used = list(self.providers.keys())[:min_providers]
        for pname in providers_used:
            resp = self.query_provider(pname, query, travel_context)
            responses.append(resp)
        
        # Simple Validation: Check if all returned successfully
        all_ok = all(r.content.startswith(f"[{r.provider}") for r in responses)
        return responses, all_ok


# == Domain Orchestrator ==

class TravelDomainOrchestrator:
    """5-Phase-Loop für HeyLou Travel Domain."""
    
    def __init__(self):
        self.graph = TravelKnowledgeGraph()
        self.llm_router = LLMRouter(self.graph)
        self.adapters: Dict[str, TravelSoftwareAdapter] = {
            "MEWS": MEWSAdapter(),
            "BookingCom": BookingComAdapter(),
            "IdeasRevenue": IdeasRevenueAdapter(),
            "GenericAPI": GenericAPIAdapter()
        }
        self.audit_log: List[Dict[str, Any]] = []
    
    def phase1_knowledge_loading(self) -> Dict[str, Any]:
        """Phase 1: Travel Knowledge Graph laden."""
        return {
            "phase": "knowledge_loading",
            "hotels_loaded": len(self.graph.hotels),
            "routes_loaded": len(self.graph.routes),
            "preferences_loaded": len(self.graph.preferences)
        }
    
    def phase2_adapter_connect(self) -> Dict[str, Any]:
        """Phase 2: Adapter verbinden."""
        connections = {}
        for name, adapter in self.adapters.items():
            connections[name] = adapter.connect()
        return {
            "phase": "adapter_connect",
            "connections": connections,
            "all_connected": all(connections.values())
        }
    
    def phase3_llm_subfunction(self, query: str, provider: str = "Ollama-Local") -> LLMResponse:
        """Phase 3: LLM Sub-Function Query."""
        travel_context = {
            "hotels_count": len(self.graph.hotels),
            "routes_count": len(self.graph.routes),
            "preferences_count": len(self.graph.preferences),
            "query": query[:100]
        }
        return self.llm_router.query_provider(provider, query, travel_context)
    
    def phase4_cross_validation(self, query: str) -> Tuple[List[LLMResponse], bool]:
        """Phase 4: Cross-LLM-Validation."""
        travel_context = {
            "hotels_count": len(self.graph.hotels),
            "routes_count": len(self.graph.routes),
            "preferences_count": len(self.graph.preferences),
            "query": query[:100]
        }
        return self.llm_router.cross_validate(query, travel_context, min_providers=2)
    
    def phase5_booking_workflow(self, adapter_name: str, hotel_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Phase 5: Buchungs-Workflow mit Adapter."""
        if adapter_name not in self.adapters:
            return {"error": f"Unknown adapter: {adapter_name}. Available: {list(self.adapters.keys())}"}
        
        adapter = self.adapters[adapter_name]
        search_result = adapter.search({"hotel_id": hotel_id, **params})
        booking_result = adapter.book(hotel_id, params)
        
        workflow = {
            "phase": "booking_workflow",
            "adapter": adapter_name,
            "search": search_result,
            "booking": booking_result
        }
        
        # Audit-Log
        self.audit_log.append({
            "timestamp": time.time(),
            "action": "booking_workflow",
            "adapter": adapter_name,
            "hotel_id": hotel_id,
            "success": booking_result.get("status") in ("confirmed", "booked")
        })
        
        return workflow
    
    def run_full_cycle(self, query: str, user_id: str = "U-001") -> Dict[str, Any]:
        """Vollständiger 5-Phase-Cycle (LaunchAgent-Entry)."""
        # Phase 1-2: Setup
        p1 = self.phase1_knowledge_loading()
        p2 = self.phase2_adapter_connect()
        
        # Phase 3: LLM Query (Primary: Ollama-Local)
        p3 = self.phase3_llm_subfunction(query)
        
        # Phase 4: Cross-Validation (Gemini + OpenAI)
        p4_responses, p4_valid = self.phase4_cross_validation(query)
        
        # Phase 5: Buchungs-Workflow (Basierend auf Query)
        pref = self.graph.get_preference(user_id)
        if pref:
            hotels = self.graph.search_hotels(min_stars=pref.min_stars, max_budget=pref.max_budget)
            if hotels:
                p5 = self.phase5_booking_workflow("MEWS", hotels[0].id, {
                    "check_in": "2026-08-01",
                    "check_out": "2026-08-05",
                    "guest_name": f"User_{user_id}",
                    "total_amount": hotels[0].base_rate * 4
                })
            else:
                p5 = {"phase": "booking_workflow", "error": "No suitable hotels found"}
        else:
            p5 = {"phase": "booking_workflow", "error": f"User {user_id} not found"}
        
        return {
            "phases": {
                "knowledge_loading": p1,
                "adapter_connect": p2,
                "llm_subfunction": {"provider": p3.provider, "content": p3.content[:100], "signature": p3.hmac_signature[:16]},
                "cross_validation": {"providers": [r.provider for r in p4_responses], "valid": p4_valid},
                "booking_workflow": p5
            },
            "summary": f"Full cycle completed. Cross-Validation: {'PASSED' if p4_valid else 'FAILED'} | Booking: {p5.get('booking', {}).get('status', 'N/A')}"
        }


# == Öffentliche API ==

def create_heylou_orchestrator() -> TravelDomainOrchestrator:
    """Factory-Funktion: Erstellt einen vollständigen HeyLou Travel Domain Orchestrator."""
    return TravelDomainOrchestrator()


def quick_search(destination: str, min_stars: int = 1, max_budget: float = 1000.0) -> List[Dict[str, Any]]:
    """Schnellsuche: Hotels + Routen für ein Reiseziel."""
    orch = create_heylou_orchestrator()
    hotels = orch.graph.search_hotels(city=destination, min_stars=min_stars, max_budget=max_budget)
    routes = orch.graph.find_routes("Berlin", destination)
    
    results = []
    for h in hotels:
        result = asdict(h)
        result["matching_routes"] = [asdict(r) for r in routes if r.to_city.lower() == h.city.lower()]
        results.append(result)
    return results


def cross_validate_travel_recommendation(query: str) -> Dict[str, Any]:
    """Cross-LLM-Validierung einer Reiseempfehlung."""
    orch = create_heylou_orchestrator()
    responses, is_valid = orch.phase4_cross_validation(query)
    return {
        "query": query,
        "validated": is_valid,
        "responses": [{"provider": r.provider, "content": r.content[:150], "signature": r.hmac_signature[:16]} for r in responses]
    }


def health_check() -> Dict[str, Any]:
    """System-Health-Check."""
    status = {
        "system": "DF-HeyLou-Travel-Domain",
        "version": "1.0.0",
        "status": "operational",
        "real_llm_mode": DF_HEYLOU_REAL_LLM_ENABLED,
        "phronesis_ticket_present": bool(PHRONESIS_TICKET),
        "modules": {
            "knowledge_graph": True,
            "adapters": ["MEWS", "BookingCom", "IdeasRevenue", "GenericAPI"],
            "llm_providers": ["Ollama-Local", "Gemini", "OpenAI", "Grok", "Mistral", "DeepSeek"]
        }
    }
    
    # Test-Komponenten
    try:
        orch = create_heylou_orchestrator()
        p1 = orch.phase1_knowledge_loading()
        p2 = orch.phase2_adapter_connect()
        status["health_check"] = {
            "knowledge_graph_healthy": p1["hotels_loaded"] > 0,
            "all_adapters_connected": p2["all_connected"],
            "llm_router_healthy": True
        }
    except Exception as e:
        status["status"] = "degraded"
        status["error"] = str(e)
    
    return status
# [CRUX-MK]
