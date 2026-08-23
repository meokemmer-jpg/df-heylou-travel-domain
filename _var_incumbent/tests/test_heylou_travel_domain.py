import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
from heylou_travel_domain import (
    TravelKnowledgeGraph,
    Hotel, Route, TravelPreference,
    MEWSAdapter, BookingComAdapter, IdeasRevenueAdapter, GenericAPIAdapter,
    LLMRouter, LLMProvider, LLMResponse,
    TravelDomainOrchestrator,
    create_heylou_orchestrator,
    quick_search,
    cross_validate_travel_recommendation,
    health_check,
    DF_HEYLOU_REAL_LLM_ENABLED
)
import json

class TestTravelKnowledgeGraph:
    def setup_method(self):
        self.graph = TravelKnowledgeGraph()
    
    def test_loads_mock_data(self):
        assert len(self.graph.hotels) == 5, f"Expected 5 hotels, got {len(self.graph.hotels)}"
        assert len(self.graph.routes) == 5, f"Expected 5 routes, got {len(self.graph.routes)}"
        assert len(self.graph.preferences) == 2, f"Expected 2 preferences, got {len(self.graph.preferences)}"
    
    def test_get_hotel(self):
        hotel = self.graph.get_hotel("H-001")
        assert hotel is not None
        assert hotel.name == "Grand Palace Hotel"
        assert hotel.city == "Berlin"
        assert hotel.stars == 5
        assert hotel.base_rate == 250.00
    
    def test_get_hotel_not_found(self):
        assert self.graph.get_hotel("INVALID") is None
    
    def test_search_hotels_by_city(self):
        berlin_hotels = self.graph.search_hotels(city="Berlin")
        assert len(berlin_hotels) == 2
        assert all(h.city == "Berlin" for h in berlin_hotels)
    
    def test_search_hotels_by_stars(self):
        luxury = self.graph.search_hotels(min_stars=4)
        assert len(luxury) == 3  # H-001 (5), H-003 (4), H-004 (4)
        assert all(h.stars >= 4 for h in luxury)
    
    def test_search_hotels_by_budget(self):
        cheap = self.graph.search_hotels(max_budget=100.0)
        assert len(cheap) >= 2  # H-002 (89), H-005 (45)
        assert all(h.base_rate <= 100.0 for h in cheap)
    
    def test_find_routes(self):
        routes = self.graph.find_routes("Berlin", "Zürich")
        assert len(routes) == 1
        assert routes[0].id == "R-001"
        assert routes[0].duration_minutes == 90
    
    def test_find_routes_case_insensitive(self):
        routes = self.graph.find_routes("berlin", "zürich")
        assert len(routes) == 1
    
    def test_get_preference(self):
        pref = self.graph.get_preference("U-001")
        assert pref is not None
        assert pref.min_stars == 3
        assert pref.max_budget == 500.00


class TestAdapters:
    def setup_method(self):
        self.mews = MEWSAdapter()
        self.booking = BookingComAdapter()
        self.ideas = IdeasRevenueAdapter()
        self.generic = GenericAPIAdapter()
    
    def test_mews_connect_and_search(self):
        assert self.mews.connect()
        result = self.mews.search({"hotel_id": "H-001", "check_in": "2026-08-01"})
        assert result["status"] == "available"
        assert "Single" in result["room_types"]
    
    def test_mews_book(self):
        result = self.mews.book("H-001", {"room_type": "Double", "guest_name": "Test User", "total_amount": 500.0})
        assert result["status"] == "confirmed"
        assert result["booking_id"].startswith("MEWS-BK-")
    
    def test_mews_cancel(self):
        book = self.mews.book("H-001", {"room_type": "Single"})
        cancel = self.mews.cancel(book["booking_id"])
        assert cancel["status"] == "cancelled"
    
    def test_booking_com_search(self):
        assert self.booking.connect()
        result = self.booking.search({"city": "Berlin", "guests": 2})
        assert result["status"] == "success"
        assert len(result["properties"]) == 2
    
    def test_booking_com_book(self):
        result = self.booking.book("P001", {"room_type": "Standard", "total_amount": 150.0})
        assert result["status"] == "booked"
        assert result["booking_id"].startswith("BC-BK-")
    
    def test_ideas_revenue_search(self):
        assert self.ideas.connect()
        result = self.ideas.search({"hotel_id": "H-001", "date_from": "2026-08-01"})
        assert result["status"] == "success"
        assert "rate_recommendations" in result
        assert result["rate_recommendations"]["Double"]["recommended"] > result["rate_recommendations"]["Double"]["current"]
    
    def test_generic_api_discovery(self):
        endpoints = self.generic.discover_endpoints()
        assert len(endpoints) == 4
        assert "search" in endpoints
        assert "book" in endpoints
    
    def test_generic_api_search(self):
        result = self.generic.search({"test": "data"})
        assert result["status"] == "ok"


class TestLLMRouter:
    def setup_method(self):
        self.graph = TravelKnowledgeGraph()
        self.router = LLMRouter(self.graph)
    
    def test_router_has_all_providers(self):
        assert len(self.router.providers) == 6
        assert "Ollama-Local" in self.router.providers
        assert "Gemini" in self.router.providers
        assert "OpenAI" in self.router.providers
        assert "Grok" in self.router.providers
        assert "Mistral" in self.router.providers
        assert "DeepSeek" in self.router.providers
    
    def test_query_ollama_local(self):
        response = self.router.query_provider("Ollama-Local", "Find hotels in Berlin")
        assert response.provider == "Ollama-Local"
        assert response.content.startswith("[Ollama-Local")
        assert len(response.hmac_signature) == 64  # SHA256 hex
    
    def test_query_gemini(self):
        response = self.router.query_provider("Gemini", "Plan 7-day itinerary")
        assert response.provider == "Gemini"
        assert "itinerary" in response.content.lower()
    
    def test_query_mistral_eu_dsgvo(self):
        response = self.router.query_provider("Mistral", "Personenbezogene Daten prüfen")
        assert "EU-DSGVO" in response.content or "privacy" in response.content.lower()
    
    def test_query_invalid_provider(self):
        try:
            self.router.query_provider("InvalidAI", "test")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown provider" in str(e)
    
    def test_cross_validation_two_providers(self):
        responses, valid = self.router.cross_validate("Find cheap flights", {}, min_providers=2)
        assert len(responses) == 2
        assert valid == True
        assert all(r.hmac_signature for r in responses)
    
    def test_hmac_signature_unique(self):
        r1 = self.router.query_provider("OpenAI", "Same query", {})
        r2 = self.router.query_provider("DeepSeek", "Same query", {})
        assert r1.hmac_signature != r2.hmac_signature  # Different providers -> different content
    
    def test_call_history(self):
        initial_count = len(self.router._call_history)
        self.router.query_provider("Grok", "test")
        assert len(self.router._call_history) == initial_count + 1


class TestTravelDomainOrchestrator:
    def setup_method(self):
        self.orch = create_heylou_orchestrator()
    
    def test_creation(self):
        assert isinstance(self.orch.graph, TravelKnowledgeGraph)
        assert len(self.orch.adapters) == 4
        assert isinstance(self.orch.llm_router, LLMRouter)
    
    def test_phase1_knowledge_loading(self):
        result = self.orch.phase1_knowledge_loading()
        assert result["phase"] == "knowledge_loading"
        assert result["hotels_loaded"] == 5
        assert result["routes_loaded"] == 5
    
    def test_phase2_adapter_connect(self):
        result = self.orch.phase2_adapter_connect()
        assert result["phase"] == "adapter_connect"
        assert result["all_connected"] == True
    
    def test_phase3_llm_subfunction(self):
        result = self.orch.phase3_llm_subfunction("Finde beste Hotels in Zürich")
        assert isinstance(result, LLMResponse)
        assert result.provider == "Ollama-Local"
    
    def test_phase4_cross_validation(self):
        responses, valid = self.orch.phase4_cross_validation("Reise nach Barcelona")
        assert len(responses) >= 2
        assert valid == True
    
    def test_phase5_booking_workflow_mews(self):
        result = self.orch.phase5_booking_workflow("MEWS", "H-001", {
            "check_in": "2026-08-01",
            "check_out": "2026-08-05",
            "guest_name": "Test",
            "total_amount": 1000.0
        })
        assert result["phase"] == "booking_workflow"
        assert result["adapter"] == "MEWS"
        assert result["booking"]["status"] == "confirmed"
    
    def test_phase5_unknown_adapter(self):
        result = self.orch.phase5_booking_workflow("UNKNOWN", "H-001", {})
        assert "error" in result
    
    def test_full_cycle(self):
        result = self.orch.run_full_cycle("Urlaub in Barcelona für 1 Woche")
        assert "phases" in result
        assert "summary" in result
        assert "knowledge_loading" in result["phases"]
        assert "adapter_connect" in result["phases"]
        assert "llm_subfunction" in result["phases"]
        assert "cross_validation" in result["phases"]
        assert "booking_workflow" in result["phases"]
        assert result["phases"]["cross_validation"]["valid"] == True
    
    def test_full_cycle_unknown_user(self):
        result = self.orch.run_full_cycle("test", user_id="UNKNOWN")
        assert "error" in result["phases"]["booking_workflow"]


class TestQuickSearch:
    def test_quick_search_returns_list(self):
        results = quick_search("Berlin")
        assert isinstance(results, list)
        assert len(results) > 0
    
    def test_quick_search_filters(self):
        results = quick_search("Berlin", min_stars=4)
        assert all(r["stars"] >= 4 for r in results)
    
    def test_quick_search_empty(self):
        results = quick_search("Mordor")
        assert len(results) == 0


class TestCrossValidation:
    def test_cross_validate_returns_dict(self):
        result = cross_validate_travel_recommendation("Beste Reiseziele im August")
        assert "query" in result
        assert "validated" in result
        assert "responses" in result
        assert len(result["responses"]) >= 2


class TestHealthCheck:
    def test_health_check_returns_status(self):
        status = health_check()
        assert status["status"] == "operational"
        assert status["system"] == "DF-HeyLou-Travel-Domain"
        assert "modules" in status
        assert "health_check" in status
        assert status["health_check"]["all_adapters_connected"] == True


class TestEdgeCases:
    def test_preference_limits_applied(self):
        graph = TravelKnowledgeGraph()
        pref = graph.get_preference("U-002")
        assert pref is not None
        hotels = graph.search_hotels(min_stars=pref.min_stars, max_budget=pref.max_budget)
        assert all(h.base_rate <= 100.0 for h in hotels)  # U-002 has max_budget 100
    
    def test_adapter_disconnect(self):
        adapter = MEWSAdapter()
        adapter.connect()
        assert adapter.disconnect() == True
    
    def test_llm_response_dataclass(self):
        response = LLMResponse(
            provider="TestAI",
            content="Hello World",
            travel_context={"key": "value"},
            hmac_signature="abcd" * 16
        )
        assert response.provider == "TestAI"
        assert response.timestamp > 0
    
    def test_real_llm_mode_env(self):
        # In test environment, should be False
        assert DF_HEYLOU_REAL_LLM_ENABLED == False
    
    def test_skeleton_key_pattern(self):
        # GenericAPIAdapter is the Skeleton-Key
        adapter = GenericAPIAdapter()
        endpoints = adapter.discover_endpoints()
        assert len(endpoints) == 4
        # Test that it dynamically resolves endpoints
        search_result = adapter.search({"destination": "Paris"})
        assert search_result["endpoint_used"].endswith("search")


if __name__ == "__main__":
    # Run all tests with verbose output
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])

