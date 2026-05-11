"""Tests fuer llm_subfunction_router.py [CRUX-MK]."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_subfunction_router import (
    LLMSubfunctionRouter,
    LLMProvider,
    LLMResponse,
)


def setup_function(_):
    """Ensure clean ENV state before each test."""
    os.environ.pop("DF_HEYLOU_REAL_LLM_ENABLED", None)


def test_default_priority_has_6_providers():
    """6-LLM-Provider-Pattern: default priority list includes all 6."""
    router = LLMSubfunctionRouter()
    priority = LLMSubfunctionRouter.DEFAULT_PRIORITY
    assert len(priority) == 6
    assert priority[0] == LLMProvider.OLLAMA_LOCAL  # Primary local
    assert LLMProvider.GEMINI in priority
    assert LLMProvider.OPENAI in priority
    assert LLMProvider.GROK in priority
    assert LLMProvider.MISTRAL in priority
    assert LLMProvider.DEEPSEEK in priority


def test_sandbox_route_returns_mock_response():
    """LC1 sandbox-default: route_query returns source='mock'."""
    router = LLMSubfunctionRouter()
    assert router.is_real_enabled() is False
    resp = router.route_query("What is the rate for tomorrow?", context="hotel=hildesheim")
    assert resp.source == "mock"
    assert resp.error is None
    assert resp.confidence > 0
    assert "[MOCK-" in resp.response_text


def test_response_signature_is_hmac_sha256():
    """W30-G: signed response has HMAC-SHA256 (64 hex chars)."""
    router = LLMSubfunctionRouter()
    resp = router.route_query("test", "ctx")
    assert resp.signature is not None
    assert len(resp.signature) == 64
    assert all(c in "0123456789abcdef" for c in resp.signature)


def test_signature_verifies_correctly():
    """W30-G: signature verifies via verify_signature()."""
    router = LLMSubfunctionRouter()
    resp = router.route_query("test", "ctx")
    assert resp.verify_signature() is True


def test_signature_tamper_detection():
    """W30-G: tampered response fails verify_signature."""
    router = LLMSubfunctionRouter()
    resp = router.route_query("test", "ctx")
    # Tamper with response_text
    tampered = LLMResponse(
        provider=resp.provider,
        model=resp.model,
        query_hash=resp.query_hash,
        response_text="TAMPERED",  # changed
        confidence=resp.confidence,
        timestamp_iso=resp.timestamp_iso,
        tokens_used=resp.tokens_used,
        source="real-api",  # changed (key field in canonical)
        signature=resp.signature,
    )
    assert tampered.verify_signature() is False


def test_cross_validate_returns_n_responses():
    """Cross-LLM-Validation: returns 1 response per provider in list."""
    router = LLMSubfunctionRouter()
    providers = [LLMProvider.OLLAMA_LOCAL, LLMProvider.GEMINI, LLMProvider.OPENAI]
    responses = router.cross_validate(
        query="What is the room rate?",
        context="hotel=munich",
        providers=providers,
    )
    assert len(responses) == 3
    provider_set = {r.provider for r in responses}
    assert provider_set == set(providers)


def test_real_mode_returns_stub_in_skeleton():
    """SKELETON: real-mode returns stub (real-api not implemented yet)."""
    os.environ["DF_HEYLOU_REAL_LLM_ENABLED"] = "true"
    router = LLMSubfunctionRouter()
    assert router.is_real_enabled() is True
    resp = router.route_query("test", "ctx")
    # All providers fail in real-mode (stub) -> error response
    assert resp.error is not None
    # cleanup
    os.environ.pop("DF_HEYLOU_REAL_LLM_ENABLED", None)


def test_query_hash_is_deterministic():
    """LC4 idempotency: same query+context -> same hash."""
    router = LLMSubfunctionRouter()
    h1 = router._query_hash("test query", "test context")
    h2 = router._query_hash("test query", "test context")
    assert h1 == h2
    assert len(h1) == 16
