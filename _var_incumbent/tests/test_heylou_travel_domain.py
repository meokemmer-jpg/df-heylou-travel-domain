import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
from heylou_travel_domain import AuditLogger, HumanGatewayNote, plan_trip


def test_plan_trip_cross_validates_and_signs_in_sandbox_by_default(monkeypatch):
    monkeypatch.delenv("DF_HEYLOU_REAL_LLM_ENABLED", raising=False)
    monkeypatch.delenv("PHRONESIS_TICKET", raising=False)

    result = plan_trip(
        {
            "origin": "Berlin",
            "destination": "Paris",
            "check_in": "2026-07-01",
            "nights": 2,
            "traveler_type": "business",
            "criticality": "K_0",
        },
        adapter_name="generic_api",
        primary_provider="ollama_local",
        credentials={"token": "valid-token"},
        secret="test-secret",
    )

    assert result["context"]["hotel"]["name"] == "HeyLou Paris Rive Gauche"
    assert result["context"]["route"]["mode"] == "train"

    adapter_result = result["adapter_result"]
    assert adapter_result["ok"] is True
    assert adapter_result["source"] == "generic_api"
    assert "/offers" in adapter_result["endpoints"][1]

    llm_result = result["llm_result"]
    assert llm_result["sandbox_mode"] is True
    assert llm_result["cross_validated"] is True
    assert len(llm_result["providers_used"]) >= 2
    assert llm_result["consensus"] is True

    first_call = llm_result["calls"][0]
    assert AuditLogger.verify_signature(
        first_call["request_envelope"],
        "test-secret",
        first_call["signature"],
    )

    assert llm_result["final_recommendation"]["destination"] == "paris"
    assert llm_result["final_recommendation"]["itinerary_id"] == result["context"]["itinerary_id"]


def test_adapter_auth_failure_returns_human_gateway_note():
    result = plan_trip(
        {
            "origin": "Berlin",
            "destination": "Rome",
            "check_in": "2026-07-10",
            "nights": 3,
            "traveler_type": "leisure",
            "criticality": "K_1",
        },
        adapter_name="mews",
        credentials={"token": "bad-token"},
    )

    adapter_result = result["adapter_result"]
    assert adapter_result["ok"] is False
    assert isinstance(adapter_result["gateway_note"], HumanGatewayNote)
    assert adapter_result["gateway_note"].reason == "authentication_failed"

