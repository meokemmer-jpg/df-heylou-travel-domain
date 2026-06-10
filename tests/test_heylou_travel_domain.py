import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
from heylou_travel_domain import (
    AuditLogger,
    GenericAPIAdapter,
    LLMSubfunctionRouter,
    TravelKnowledgeGraph,
    build_default_orchestrator,
    execute_heylou_travel_planning,
)


def test_execute_heylou_travel_planning_cross_validates_and_signs():
    result = execute_heylou_travel_planning(origin="HAM", destination="Berlin", nights=2)

    assert result.request_id.startswith("heylou-")
    assert result.cross_validated is True
    assert len(result.llm_results) == 2
    assert {r.provider for r in result.llm_results} == {"ollama", "openai"}
    assert all(r.mode == "sandbox" for r in result.llm_results)
    assert all(len(r.signature) == 64 for r in result.llm_results)

    hotels = result.enriched_context["hotel_candidates"]
    assert hotels
    assert hotels[0]["city"] == "Berlin"

    recommended = {r.answer["recommended_hotel"] for r in result.llm_results}
    assert recommended == {"Mock Berlin Mitte Hotel"}

    totals = {r.answer["estimated_total_eur"] for r in result.llm_results}
    assert totals == {290}

    assert len(result.adapter_results) == 4
    assert all(item["ok"] is True for item in result.adapter_results)
    assert result.audit_event["payload"]["cross_validated"] is True
    assert len(result.audit_event["signature"]) == 64


def test_generic_adapter_auth_failure_emits_human_gateway_note():
    adapter = GenericAPIAdapter(auth_token="")
    adapter.authenticate = lambda: False  # force sandbox auth failure path

    response = adapter.fetch_availability(destination="Berlin", nights=1)

    assert response["ok"] is False
    assert response["reason"] == "auth_failed"
    assert "T5 inbox" in response["human_gateway_note"]


def test_router_rejects_unknown_provider():
    graph = TravelKnowledgeGraph.with_mock_data()
    router = LLMSubfunctionRouter(secret="x")
    enriched = graph.enrich_request(
        {"origin": "HAM", "destination": "Berlin", "nights": 1, "traveler_id": "default"}
    )

    try:
        router.route(enriched, providers=["unknown-provider"])
    except ValueError as exc:
        assert "Unsupported provider" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported provider")


def test_audit_logger_signature_changes_with_payload():
    logger = AuditLogger(secret="same-secret")

    first = logger.log("evt", {"a": 1})
    second = logger.log("evt", {"a": 2})

    assert first["signature"] != second["signature"]
    assert len(logger.events) == 2


def test_build_default_orchestrator_produces_working_instance():
    orchestrator = build_default_orchestrator(secret="abc")
    result = orchestrator.plan_trip(origin="HAM", destination="Berlin", nights=1)

    assert result.cross_validated is True
    assert result.llm_results[0].answer["within_budget"] is True
