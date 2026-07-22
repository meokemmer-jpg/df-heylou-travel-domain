import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
"""test_heylou_travel_domain.py - pytest-Tests fuer heylou_travel_domain.py."""
import json
import hmac
import hashlib
import time
from heylou_travel_domain import (
    TravelKnowledgeGraph, Hotel, Route, Rate, UserPreference,
    TravelSoftwareAdapter, SkeletonKeyFactory, AdapterType,
    LLMRouter, LLMProvider, LLMResponse,
    DomainOrchestrator, AuditLogger,
    create_travel_knowledge_graph, query_hotel, route_llm_query, skeleton_key_booking
)


class TestTravelKnowledgeGraph:
    """Tests fuer den Travel-Knowledge-Graph."""

    def test_initialization_creates_mock_data(self):
        graph = create_travel_knowledge_graph()
        assert len(graph.hotels) == 3
        assert len(graph.routes) == 3
        assert len(graph.rates) == 6
        assert "USER001" in graph.preferences

    def test_get_hotel_returns_correct_hotel(self):
        graph = TravelKnowledgeGraph()
        hotel = graph.get_hotel("H001")
        assert hotel is not None
        assert hotel.name == "Grand Palace Hotel"
        assert hotel.city == "Berlin"
        assert hotel.star_rating == 5

    def test_get_hotel_returns_none_for_invalid_id(self):
        graph = TravelKnowledgeGraph()
        assert graph.get_hotel("INVALID") is None

    def test_get_route_returns_correct_route(self):
        graph = TravelKnowledgeGraph()
        route = graph.get_route("R001")
        assert route is not None
        assert route.origin == "Berlin"
        assert route.destination == "Muenchen"
        assert route.airline == "Lufthansa"

    def test_get_rates_for_hotel_returns_filtered_rates(self):
        graph = TravelKnowledgeGraph()
        rates = graph.get_rates_for_hotel("H001")
        assert len(rates) == 2
        assert all(r.hotel_id == "H001" for r in rates)

    def test_get_user_preference_returns_correct_pref(self):
        graph = TravelKnowledgeGraph()
        pref = graph.get_user_preference("USER001")
        assert pref is not None
        assert pref.max_budget == 500.0
        assert "Berlin" in pref.preferred_cities

    def test_search_hotels_by_city_case_insensitive(self):
        graph = TravelKnowledgeGraph()
        hotels = graph.search_hotels_by_city("berlin")
        assert len(hotels) == 1
        assert hotels[0].name == "Grand Palace Hotel"

    def test_to_context_string_contains_hotel_and_route_data(self):
        graph = TravelKnowledgeGraph()
        context = graph.to_context_string()
        assert "Grand Palace Hotel" in context
        assert "Berlin -> Muenchen" in context
        assert "Lufthansa" in context

    def test_query_hotel_function(self):
        graph = TravelKnowledgeGraph()
        result = query_hotel(graph, "H002")
        assert result is not None
        assert result["name"] == "City Stay Inn"
        assert result["city"] == "Muenchen"
        assert result["star_rating"] == 3

    def test_query_hotel_invalid_returns_none(self):
        graph = TravelKnowledgeGraph()
        assert query_hotel(graph, "INVALID") is None


class TestSkeletonKeyAdapter:
    """Tests fuer das Skeleton-Key-Adapter-Pattern."""

    def test_create_mews_adapter(self):
        factory = SkeletonKeyFactory()
        adapter = factory.create_adapter("mews")
        assert adapter.type == AdapterType.PMS
        assert "mews.com" in adapter.endpoint

    def test_create_booking_com_adapter(self):
        factory = SkeletonKeyFactory()
        adapter = factory.create_adapter("booking.com")
        assert adapter.type == AdapterType.OTA
        assert "booking.com" in adapter.endpoint

    def test_create_ideas_adapter(self):
        factory = SkeletonKeyFactory()
        adapter = factory.create_adapter("ideas")
        assert adapter.type == AdapterType.RMS
        assert "ideas.com" in adapter.endpoint

    def test_create_generic_adapter(self):
        factory = SkeletonKeyFactory()
        adapter = factory.create_adapter("unknown_software")
        assert adapter.type == AdapterType.GENERIC

    def test_adapter_connect(self):
        adapter = TravelSoftwareAdapter(AdapterType.PMS)
        assert adapter.connect() is True
        assert adapter.connected is True

    def test_adapter_fetch_hotel_data(self):
        adapter = TravelSoftwareAdapter(AdapterType.OTA)
        adapter.connect()
        data = adapter.fetch_hotel_data("H001")
        assert data["id"] == "H001"
        assert data["source"] == "ota"
        assert data["connected"] is True

    def test_adapter_book_room(self):
        adapter = TravelSoftwareAdapter(AdapterType.PMS)
        adapter.connect()
        booking = adapter.book_room("H001", "deluxe")
        assert booking["status"] == "confirmed"
        assert booking["hotel_id"] == "H001"
        assert booking["room_type"] == "deluxe"
        assert booking["booking_id"].startswith("BK-H001-")

    def test_skeleton_key_booking_function(self):
        result = skeleton_key_booking("mews", "H003")
        assert result["status"] == "confirmed"
        assert result["adapter"] == "pms"


class TestLLMRouter:
    """Tests fuer den LLM-Sub-Funktion-Router."""

    def test_ollama_call_returns_ollama_mock(self):
        router = LLMRouter()
        resp = router.call_llm(LLMProvider.OLLAMA, "Finde ein Hotel")
        assert resp.provider == LLMProvider.OLLAMA
        assert "Ollama-Local" in resp.content

    def test_gemini_call_returns_gemini_mock(self):
        router = LLMRouter()
        resp = router.call_llm(LLMProvider.GEMINI, "Erstelle Reiseroute")
        assert resp.provider == LLMProvider.GEMINI
        assert "Gemini-Itinerary" in resp.content

    def test_openai_call_returns_openai_mock(self):
        router = LLMRouter()
        resp = router.call_llm(LLMProvider.OPENAI, "Pruefe Buchung")
        assert resp.provider == LLMProvider.OPENAI
        assert "OpenAI-Reasoning" in resp.content

    def test_grok_call_returns_grok_mock(self):
        router = LLMRouter()
        resp = router.call_llm(LLMProvider.GROK, "Aktuelle Lage")
        assert resp.provider == LLMProvider.GROK
        assert "Grok-RealTime" in resp.content

    def test_mistral_call_returns_mistral_mock(self):
        router = LLMRouter()
        resp = router.call_llm(LLMProvider.MISTRAL, "DSGVO-Check")
        assert resp.provider == LLMProvider.MISTRAL
        assert "Mistral-EU-DSGVO" in resp.content

    def test_deepseek_call_returns_deepseek_mock(self):
        router = LLMRouter()
        resp = router.call_llm(LLMProvider.DEEPSEEK, "Billigste Route")
        assert resp.provider == LLMProvider.DEEPSEEK
        assert "DeepSeek-Routine" in resp.content

    def test_hmac_signature_is_valid(self):
        router = LLMRouter()
        resp = router.call_llm(LLMProvider.OLLAMA, "Test")
        assert resp.verify_hmac(router.secret) is True

    def test_hmac_signature_wrong_secret_fails(self):
        router = LLMRouter(hmac_secret=b"secret1")
        resp = router.call_llm(LLMProvider.OLLAMA, "Test")
        assert resp.verify_hmac(b"secret2") is False

    def test_all_providers_return_unique_content(self):
        responses = route_llm_query("Buche Hotel in Berlin")
        assert len(responses) == 6
        providers = [r["provider"] for r in responses]
        assert len(set(providers)) == 6

    def test_cross_validation_with_two_same_responses(self):
        router = LLMRouter()
        content = "Gleiche Antwort"
        secret = router.secret
        sig = hmac.new(secret, content.encode(), hashlib.sha256).hexdigest()
        resp1 = LLMResponse(LLMProvider.OLLAMA, content, sig)
        resp2 = LLMResponse(LLMProvider.GEMINI, content, sig)
        assert router.cross_validate([resp1, resp2]) is True

    def test_cross_validation_with_different_responses(self):
        router = LLMRouter()
        resp1 = router.call_llm(LLMProvider.OLLAMA, "A")
        resp2 = router.call_llm(LLMProvider.GEMINI, "B")
        assert router.cross_validate([resp1, resp2]) is False


class TestDomainOrchestrator:
    """Tests fuer den 5-Phase-Domain-Orchestrator."""

    def test_process_travel_request_returns_all_phases(self):
        orchestrator = DomainOrchestrator()
        result = orchestrator.process_travel_request("USER001", "Suche Hotel in Berlin", "H001")
        assert len(result["phases"]) == 5
        assert "QUERY" in result["phases"]
        assert "ENRICH" in result["phases"]
        assert "ROUTE" in result["phases"]
        assert "DECIDE" in result["phases"]
        assert "ACT" in result["phases"]

    def test_process_travel_request_has_final_response(self):
        orchestrator = DomainOrchestrator()
        result = orchestrator.process_travel_request("USER001", "Reise nach Muenchen")
        assert "final_response" in result
        assert "HeyLou" in result["final_response"]

    def test_process_travel_request_cross_validates_llms(self):
        orchestrator = DomainOrchestrator()
        result = orchestrator.process_travel_request("USER001", "Test")
        assert "cross_validated" in result["phases"]["ROUTE"]

    def test_orchestrator_without_hotel_id_uses_booking_adapter(self):
        orchestrator = DomainOrchestrator()
        result = orchestrator.process_travel_request("USER001", "Suche")
        assert result["phases"]["ACT"]["action"] == "fetch"

    def test_orchestrator_with_hotel_id_uses_mews_adapter(self):
        orchestrator = DomainOrchestrator()
        result = orchestrator.process_travel_request("USER001", "Buchen", "H001")
        assert result["phases"]["ACT"]["action"] == "booking"
        assert result["phases"]["ACT"]["result"]["status"] == "confirmed"


class TestAuditLogger:
    """Tests fuer den Audit-Logger mit HMAC."""

    def test_log_action_returns_signature(self):
        logger = AuditLogger()
        sig = logger.log_action("booking", {"hotel": "H001", "user": "USER001"})
        assert len(sig) == 64  # SHA256 hex length
        assert isinstance(sig, str)

    def test_log_entry_stored_correctly(self):
        logger = AuditLogger()
        data = {"action": "test", "value": 42}
        logger.log_action("test_event", data)
        assert len(logger.log) == 1
        assert logger.log[0]["action"] == "test_event"
        assert logger.log[0]["data"] == data

    def test_verify_log_entry_valid(self):
        logger = AuditLogger()
        sig = logger.log_action("login", {"user": "admin"})
        entry = logger.log[0]
        assert logger.verify_log_entry(entry) is True

    def test_verify_log_entry_tampered_data_fails(self):
        logger = AuditLogger()
        logger.log_action("login", {"user": "admin"})
        entry = logger.log[0]
        entry["data"]["user"] = "hacker"
        assert logger.verify_log_entry(entry) is False


class TestIntegration:
    """Integrationstests fuer das Gesamtsystem."""

    def test_full_travel_request_flow(self):
        """Testet den kompletten Flow: Knowledge Graph -> LLM Routing -> Adapter."""
        orchestrator = DomainOrchestrator()
        result = orchestrator.process_travel_request("USER001", "Buche Hotel in Berlin ab 200EUR", "H001")
        
        assert result["user_id"] == "USER001"
        assert result["phases"]["QUERY"]["preference"]["max_budget"] == 500.0
        assert "Grand Palace Hotel" in result["phases"]["ENRICH"]["enriched_data"]
        assert len(result["phases"]["ROUTE"]["responses"]) == 3
        assert result["phases"]["DECIDE"]["chosen_provider"] in ["ollama", "gemini", "openai"]
        assert result["phases"]["ACT"]["result"]["status"] == "confirmed"

    def test_route_llm_query_returns_signed_responses(self):
        responses = route_llm_query("Test Query", "Travel Context")
        for resp in responses:
            assert len(resp["hmac"]) == 64
            assert resp["provider"] in [p.value for p in LLMProvider]

    def test_skeleton_key_can_switch_between_ota_and_pms(self):
        ota_booking = skeleton_key_booking("booking.com", "H001")
        pms_booking = skeleton_key_booking("mews", "H002")
        
        assert ota_booking["adapter"] == "ota"
        assert pms_booking["adapter"] == "pms"
        assert ota_booking["booking_id"] != pms_booking["booking_id"]
