import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
from heylou_travel_domain import DomainOrchestrator, LLMSubFunctionRouter, verify_signature


def test_end_to_end_cross_validation_and_hmac_signature():
    providers = {
        "ollama-local": lambda task, context, sandbox: {
            "text": "ollama-primary",
            "confidence": 0.91,
            "details": {"task": task, "sandbox": sandbox, "hotels": len(context["hotels"])},
        },
        "openai": lambda task, context, sandbox: {
            "text": "openai-validator",
            "confidence": 0.88,
            "details": {"task": task, "sandbox": sandbox, "hotels": len(context["hotels"])},
        },
    }
    router = LLMSubFunctionRouter(secret="top-secret", providers=providers, cross_validate_threshold=0.25)
    orchestrator = DomainOrchestrator(secret="top-secret", router=router)

    result = orchestrator.handle_travel_request(
        request={
            "origin": "BER",
            "destination": "Paris",
            "city": "Paris",
            "budget_max": 200,
            "adapter_payload": {
                "token": "valid-token",
                "base_url": "https://mock.example",
                "endpoints": {"availability": "/availability", "rates": "/rates"},
            },
        },
        user_preferences={"tags": ["wifi"]},
        adapter_name="generic",
        preferred_provider="ollama-local",
        uncertainty=0.10,
    )

    assert len(result["context"]["hotels"]) == 2
    assert result["context"]["route"]["mode"] == "flight"
    assert result["llm"]["providers_used"] == ["ollama-local", "openai"]
    assert result["llm"]["validations"][0]["agrees_on_task"] is True
    assert result["adapter"]["status"] == "ok"
    assert result["adapter"]["discovered_endpoints"]["availability"] == "https://mock.example/availability"
    assert verify_signature(
        "top-secret",
        result["llm"]["signed_payload"],
        result["llm"]["signature"],
    )
    assert verify_signature(
        "top-secret",
        result["audit"]["envelope"],
        result["audit"]["signature"],
    )


def test_auth_failure_creates_human_gateway_note():
    orchestrator = DomainOrchestrator(secret="top-secret")

    result = orchestrator.handle_travel_request(
        request={
            "origin": "BER",
            "destination": "Paris",
            "city": "Paris",
            "budget_max": 200,
            "adapter_payload": {"token": "wrong-token"},
        },
        user_preferences={"tags": ["wifi"]},
        adapter_name="mews",
        uncertainty=0.60,
    )

    assert result["adapter"]["status"] == "auth_failed"
    assert "T5-Mensch-Gateway-Inbox-Note" in result["inbox_notes"][0]
    assert "MEWSAdapter authentication failed" in result["adapter"]["error"]
