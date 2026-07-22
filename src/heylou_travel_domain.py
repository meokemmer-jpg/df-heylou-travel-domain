"""heylou_travel_domain.py - DF-HeyLou-Travel-Domain [CRUX-MK] Kernmodul.

Implementiert den Kern der HeyLou Travel Domain: Travel-Knowledge-Graph,
Skeleton-Key-Adapter, LLM-Sub-Funktion-Routing und Domain Orchestrator (5-Phase-Loop).
"""
import json
import hmac
import hashlib
import time
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from enum import Enum

# ---------------------------------------------------------------------------
# 1. TRAVEL KNOWLEDGE GRAPH
# ---------------------------------------------------------------------------

@dataclass
class Hotel:
    id: str
    name: str
    city: str
    country: str
    star_rating: int
    base_rate: float
    amenities: list[str] = field(default_factory=list)

@dataclass
class Route:
    id: str
    origin: str
    destination: str
    airline: str
    base_price: float
    duration_minutes: int

@dataclass
class Rate:
    hotel_id: str
    room_type: str
    price_per_night: float
    currency: str = "EUR"
    cancellation_policy: str = "free_24h"

@dataclass  
class UserPreference:
    user_id: str
    preferred_cities: list[str] = field(default_factory=list)
    max_budget: float = 1000.0
    min_star_rating: int = 3
    preferred_amenities: list[str] = field(default_factory=list)

class TravelKnowledgeGraph:
    """In-Memory Knowledge Graph fuer Travel-Domain-Daten."""
    
    def __init__(self):
        self.hotels: dict[str, Hotel] = {}
        self.routes: dict[str, Route] = {}
        self.rates: list[Rate] = []
        self.preferences: dict[str, UserPreference] = {}
        self._load_mock_data()
    
    def _load_mock_data(self):
        """Mock-Daten fuer Sandbox-Betrieb."""
        self.hotels["H001"] = Hotel("H001", "Grand Palace Hotel", "Berlin", "DE", 5, 250.0, ["pool", "spa", "wifi"])
        self.hotels["H002"] = Hotel("H002", "City Stay Inn", "Muenchen", "DE", 3, 89.0, ["wifi", "breakfast"])
        self.hotels["H003"] = Hotel("H003", "Alpine Lodge", "Innsbruck", "AT", 4, 180.0, ["pool", "wifi", "sauna"])
        
        self.routes["R001"] = Route("R001", "Berlin", "Muenchen", "Lufthansa", 129.0, 75)
        self.routes["R002"] = Route("R002", "Muenchen", "Innsbruck", "Austrian", 89.0, 45)
        self.routes["R003"] = Route("R003", "Berlin", "Innsbruck", "Ryanair", 49.0, 90)
        
        self.rates = [
            Rate("H001", "standard", 200.0),
            Rate("H001", "deluxe", 350.0),
            Rate("H002", "standard", 79.0),
            Rate("H002", "family", 129.0),
            Rate("H003", "standard", 150.0),
            Rate("H003", "suite", 280.0),
        ]
        
        self.preferences["USER001"] = UserPreference("USER001", ["Berlin", "Muenchen"], 500.0, 3, ["wifi"])
    
    def get_hotel(self, hotel_id: str) -> Optional[Hotel]:
        return self.hotels.get(hotel_id)
    
    def get_route(self, route_id: str) -> Optional[Route]:
        return self.routes.get(route_id)
    
    def get_rates_for_hotel(self, hotel_id: str) -> list[Rate]:
        return [r for r in self.rates if r.hotel_id == hotel_id]
    
    def get_user_preference(self, user_id: str) -> Optional[UserPreference]:
        return self.preferences.get(user_id)
    
    def search_hotels_by_city(self, city: str) -> list[Hotel]:
        return [h for h in self.hotels.values() if h.city.lower() == city.lower()]
    
    def to_context_string(self) -> str:
        """Serialisiert den Graph in einen Prompt-Context-String."""
        parts = []
        for h in self.hotels.values():
            parts.append(f"Hotel: {h.name} ({h.city}, {h.country}) - {h.star_rating}* - ab {h.base_rate}EUR")
        for r in self.routes.values():
            parts.append(f"Route: {r.origin} -> {r.destination} mit {r.airline} ab {r.base_price}EUR")
        return "\n".join(parts) if parts else "Keine Reisedaten verfuegbar."


# ---------------------------------------------------------------------------
# 2. SKELETON KEY ADAPTER
# ---------------------------------------------------------------------------

class AdapterType(Enum):
    PMS = "pms"
    OTA = "ota"
    RMS = "rms"
    GENERIC = "generic"

class TravelSoftwareAdapter:
    """Basis-Adapter - Skeleton Key Pattern."""
    
    def __init__(self, adapter_type: AdapterType, endpoint: str = ""):
        self.type = adapter_type
        self.endpoint = endpoint
        self.connected = False
    
    def connect(self) -> bool:
        """Simuliert Verbindungsaufbau (Mock)."""
        self.connected = True
        return True
    
    def fetch_hotel_data(self, hotel_id: str) -> dict:
        """Mock-Datenabruf."""
        return {
            "id": hotel_id,
            "name": f"Mock Hotel {hotel_id}",
            "available_rooms": [{"type": "standard", "count": 5}],
            "source": self.type.value,
            "connected": self.connected
        }
    
    def book_room(self, hotel_id: str, room_type: str) -> dict:
        """Mock-Buchung."""
        return {
            "status": "confirmed",
            "booking_id": f"BK-{hotel_id}-{int(time.time())}",
            "hotel_id": hotel_id,
            "room_type": room_type,
            "adapter": self.type.value
        }

class SkeletonKeyFactory:
    """Fabrik fuer Adapter - Skeleton Key Pattern."""
    
    @staticmethod
    def create_adapter(software_name: str) -> TravelSoftwareAdapter:
        mapping = {
            "mews": (AdapterType.PMS, "https://api.mews.com/v1"),
            "booking.com": (AdapterType.OTA, "https://api.booking.com/v2"),
            "ideas": (AdapterType.RMS, "https://api.ideas.com/v3"),
        }
        key = software_name.lower().replace(" ", "")
        if key in mapping:
            atype, endpoint = mapping[key]
            return TravelSoftwareAdapter(atype, endpoint)
        return TravelSoftwareAdapter(AdapterType.GENERIC, f"https://api.{software_name.lower()}.com")


# ---------------------------------------------------------------------------
# 3. LLM SUB-FUNKTION ROUTER
# ---------------------------------------------------------------------------

class LLMProvider(Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"
    OPENAI = "openai"
    GROK = "grok"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"

@dataclass
class LLMResponse:
    provider: LLMProvider
    content: str
    hmac_signature: str
    timestamp: float = field(default_factory=time.time)
    
    def verify_hmac(self, secret: bytes) -> bool:
        expected = hmac.new(secret, self.content.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, self.hmac_signature)

class LLMRouter:
    """Router fuer 6 LLM-Provider mit HMAC-Signing und Cross-Validation."""
    
    def __init__(self, hmac_secret: bytes = b"heylou-skeleton-key-2026"):
        self.secret = hmac_secret
        self._real_enabled = os.environ.get("DF_HEYLOU_REAL_LLM_ENABLED", "false").lower() == "true"
        self._phronesis_ticket = os.environ.get("PHRONESIS_TICKET", "")
    
    def _sign(self, content: str) -> str:
        return hmac.new(self.secret, content.encode(), hashlib.sha256).hexdigest()
    
    def _mock_call(self, provider: LLMProvider, prompt: str, context: str = "") -> str:
        """Simulierter LLM-Call."""
        responses = {
            LLMProvider.OLLAMA: f"[Ollama-Local] Reiseanalyse: {prompt[:50]}... Basierend auf Kontext: {context[:80]}...",
            LLMProvider.GEMINI: f"[Gemini-Itinerary] Ausfuehrliche Reiseroute erstellt fuer Anfrage: {prompt[:40]}",
            LLMProvider.OPENAI: f"[OpenAI-Reasoning] Buchungslogik geprueft. Empfehlung basierend auf {len(context)} Zeichen Kontext.",
            LLMProvider.GROK: f"[Grok-RealTime] Aktuelle Reiseinformationen fuer: {prompt[:30]}. Keine Stoerungen gemeldet.",
            LLMProvider.MISTRAL: f"[Mistral-EU-DSGVO] DSGVO-konforme Reiseberatung durchgefuehrt. Daten bleiben in EU.",
            LLMProvider.DEEPSEEK: f"[DeepSeek-Routine] Kosteneffiziente Routenberechnung: Anfrage bearbeitet.",
        }
        return responses.get(provider, f"[{provider.value}] Mock-Response: {prompt}")
    
    def call_llm(self, provider: LLMProvider, prompt: str, context: str = "") -> LLMResponse:
        """Fuehrt einen LLM-Call aus (Mock oder ggf. Real)."""
        if self._real_enabled and self._phronesis_ticket:
            # Real-Call (hier nur Platzhalter)
            content = f"[REAL-{provider.value}] {prompt} (ticket={self._phronesis_ticket})"
        else:
            content = self._mock_call(provider, prompt, context)
        
        signature = self._sign(content)
        return LLMResponse(provider, content, signature)
    
    def cross_validate(self, responses: list[LLMResponse]) -> bool:
        """Cross-Validation: Prueft ob mind. 2 Provider aehnliche Antworten liefern."""
        if len(responses) < 2:
            return False
        contents = [r.content[:50] for r in responses]
        return len(set(contents)) <= len(contents) - 1  # Mind. 2 identische Anfaenge


# ---------------------------------------------------------------------------
# 4. DOMAIN ORCHESTRATOR (5-Phase Loop)
# ---------------------------------------------------------------------------

class DomainOrchestrator:
    """5-Phase-Loop fuer HeyLou Travel Domain Processing."""
    
    def __init__(self):
        self.knowledge_graph = TravelKnowledgeGraph()
        self.adapter_factory = SkeletonKeyFactory()
        self.llm_router = LLMRouter()
        self.phases = ["QUERY", "ENRICH", "ROUTE", "DECIDE", "ACT"]
    
    def process_travel_request(self, user_id: str, query: str, hotel_id: str = "") -> dict:
        """Verarbeitet eine Reiseanfrage durch alle 5 Phasen."""
        result = {
            "user_id": user_id,
            "query": query,
            "phases": {},
            "final_response": "",
            "timestamp": time.time()
        }
        
        # Phase 1: QUERY - Anfrage analysieren
        pref = self.knowledge_graph.get_user_preference(user_id)
        context = self.knowledge_graph.to_context_string()
        result["phases"]["QUERY"] = {
            "preference": asdict(pref) if pref else {},
            "context_length": len(context)
        }
        
        # Phase 2: ENRICH - Mit Knowledge Graph anreichern
        enriched = ""
        if hotel_id:
            hotel = self.knowledge_graph.get_hotel(hotel_id)
            rates = self.knowledge_graph.get_rates_for_hotel(hotel_id)
            enriched = f"Hotel: {hotel}, Rates: {len(rates)} Optionen" if hotel else "Kein Hotel gefunden"
        result["phases"]["ENRICH"] = {"enriched_data": enriched}
        
        # Phase 3: ROUTE - LLM-Calls routen
        llm_responses = []
        for provider in [LLMProvider.OLLAMA, LLMProvider.GEMINI, LLMProvider.OPENAI]:
            resp = self.llm_router.call_llm(provider, query, context)
            llm_responses.append(resp)
        
        cross_valid = self.llm_router.cross_validate(llm_responses)
        result["phases"]["ROUTE"] = {
            "responses": [{"provider": r.provider.value, "content": r.content, "hmac": r.hmac_signature[:8]} for r in llm_responses],
            "cross_validated": cross_valid
        }
        
        # Phase 4: DECIDE - Entscheidung treffen
        best_response = max(llm_responses, key=lambda r: len(r.content))
        result["phases"]["DECIDE"] = {
            "chosen_provider": best_response.provider.value,
            "decision_rationale": "Laengste Antwort als beste Qualitaet gewaehlt"
        }
        
        # Phase 5: ACT - Aktion ausfuehren (Adapter nutzen)
        adapter = self.adapter_factory.create_adapter("mews" if hotel_id else "booking.com")
        adapter.connect()
        if hotel_id:
            booking = adapter.book_room(hotel_id, "standard")
            result["phases"]["ACT"] = {"action": "booking", "result": booking}
        else:
            data = adapter.fetch_hotel_data("MOCK001")
            result["phases"]["ACT"] = {"action": "fetch", "result": data}
        
        result["final_response"] = f"HeyLou hat Ihre Reiseanfrage bearbeitet: {query}. Gewaehlte LLM-Antwort: {best_response.content[:100]}..."
        return result


# ---------------------------------------------------------------------------
# 5. AUDIT LOGGER (HMAC-SHA256)
# ---------------------------------------------------------------------------

class AuditLogger:
    """Protokolliert Aktionen mit HMAC-SHA256-Signatur."""
    
    def __init__(self, secret: bytes = b"heylou-audit-secret"):
        self.secret = secret
        self.log: list[dict] = []
    
    def log_action(self, action: str, data: dict) -> str:
        signature = hmac.new(self.secret, json.dumps(data, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        entry = {
            "action": action,
            "data": data,
            "signature": signature,
            "timestamp": time.time()
        }
        self.log.append(entry)
        return signature
    
    def verify_log_entry(self, entry: dict) -> bool:
        expected = hmac.new(self.secret, json.dumps(entry["data"], sort_keys=True).encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(entry["signature"], expected)


# ---------------------------------------------------------------------------
# API-Funktionen fuer Tests
# ---------------------------------------------------------------------------

def create_travel_knowledge_graph() -> TravelKnowledgeGraph:
    """Erstellt und gibt einen initialisierten TravelKnowledgeGraph zurueck."""
    return TravelKnowledgeGraph()

def query_hotel(graph: TravelKnowledgeGraph, hotel_id: str) -> Optional[dict]:
    """Query-Funktion fuer Hotel-Daten."""
    hotel = graph.get_hotel(hotel_id)
    if hotel:
        return asdict(hotel)
    return None

def route_llm_query(query: str, context: str = "") -> list[dict]:
    """Fuehrt einen gerouteten LLM-Call aus und gibt Ergebnisse zurueck."""
    router = LLMRouter()
    results = []
    for provider in LLMProvider:
        resp = router.call_llm(provider, query, context)
        results.append({
            "provider": provider.value,
            "content": resp.content,
            "hmac": resp.hmac_signature
        })
    return results

def skeleton_key_booking(software: str, hotel_id: str) -> dict:
    """Fuehrt eine Buchung via Skeleton-Key-Adapter aus."""
    factory = SkeletonKeyFactory()
    adapter = factory.create_adapter(software)
    adapter.connect()
    return adapter.book_room(hotel_id, "standard")
# [CRUX-MK]
