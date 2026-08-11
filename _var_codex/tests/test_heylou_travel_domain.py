import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
from heylou_travel_domain import AuditLogger, GenericAPIAdapter, TravelQuery, run_heylou_travel_domain


def test_heylou_travel_domain_core_flow(monkeypatch):
    monkeypatch.delenv("DF_HEYLOU_REAL_LLM_ENABLED", raising=False)

    query = TravelQuery(
        origin="Hamburg",
        destination="Berlin",
        check_in="2026-09-10",
        check_out="2026-09-12",
        guests=2,
        budget_eur=320,
        intent="hotel_search",
    )
    adapter = GenericAPIAdapter("https://sandbox.example.test", sandbox_mode=True)

    result = run_heylou_travel_domain(
        query,
        secret="test-secret",
        adapter=adapter,
        k0_q0_proximity=0.10,
    )

    assert result["query"]["destination"] == "Berlin"
    assert "Mock Hotel Alexanderplatz" in result["hotel_candidates"]
    assert result["route"]["mode"] == "rail"

    assert result["quote"]["adapter"] == "GenericAPI"
    assert result["quote"]["mode"] == "mock"
    assert result["quote"]["discovered_endpoints"]["rates"] == "https://sandbox.example.test/rates"

    assert result["llm"]["mode"] == "sandbox"
    assert result["llm"]["cross_validated"] is True
    assert result["llm"]["providers_used"] == ["ollama-local", "openai"]
    assert len(result["llm"]["outputs"]) == 2

    logger = AuditLogger("test-secret")
    expected_signature = logger.sign(
        {
            "task": "hotel_search",
            "mode": "sandbox",
            "providers": ["ollama-local", "openai"],
            "context_hash": "c519b8f42253ceff4af05f5a67b558f70bd4a341db1f4a4cf2df94f0d0f555d4",
        }
    )
    assert result["llm"]["signature"] == expected_signature
