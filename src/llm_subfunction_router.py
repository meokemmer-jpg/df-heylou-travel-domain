"""LLM-Sub-Funktion-Router [CRUX-MK].

6-LLM-Provider-Routing fuer HeyLou Travel-Domain als Specialization-Layer.

Provider-Reihenfolge (Sunk-Cost-Hierarchie per ~/.claude/rules/token-engpass-hierarchie.md):
1. Ollama-Local (Primary, Internet-unabhaengig, $0)
2. Gemini (Long-Context, Ultra Sunk-Cost)
3. OpenAI (Reasoning, ChatGPT Pro Sunk-Cost)
4. Grok (Real-time, Heavy Sunk-Cost)
5. Mistral (EU-DSGVO-konform, optional)
6. DeepSeek (Cost-effective, optional)

K12 Provenance: Jeder Call wird HMAC-SHA256-signed (per W30-G aus df-100).
ENV-Var-Pattern: DF_HEYLOU_REAL_LLM_ENABLED=false per Default (Mock-Fallback).

Welle-35.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """6 LLM-Provider als Sub-Funktion fuer Travel-Domain-Layer."""
    OLLAMA_LOCAL = "ollama-local"
    GEMINI = "gemini"
    OPENAI = "openai"
    GROK = "grok"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"


@dataclass(frozen=True)
class LLMResponse:
    """Antwort eines LLM-Providers (LC4 idempotent + K12 provenance).

    source ∈ {"mock", "real-api", "stub"}
    """
    provider: LLMProvider
    model: str
    query_hash: str
    response_text: str
    confidence: float  # 0.0 - 1.0
    timestamp_iso: str
    tokens_used: int = 0
    source: str = "mock"
    signature: Optional[str] = None  # HMAC-SHA256 per W30-G
    error: Optional[str] = None

    def canonical_payload(self) -> str:
        """W30-G: Deterministischer Payload fuer HMAC-Signature.

        Reihenfolge fix: provider | model | query_hash | source | tokens_used.
        """
        return f"{self.provider.value}||{self.model}||{self.query_hash}||{self.source}||{self.tokens_used}"

    @staticmethod
    def sign_payload(payload: str, secret: Optional[str] = None) -> str:
        """W30-G: HMAC-SHA256 ueber payload.

        Secret-Quelle: DF_HEYLOU_HMAC_SECRET > DF_SERVICE_IDENTITY_SECRET > default.
        """
        if secret is None:
            secret = (
                os.environ.get("DF_HEYLOU_HMAC_SECRET")
                or os.environ.get("DF_SERVICE_IDENTITY_SECRET")
                or "df-heylou-travel-domain-runtime-default"
            )
        return hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def signed(self, secret: Optional[str] = None) -> "LLMResponse":
        """Return new LLMResponse instance with signature populated."""
        sig = self.sign_payload(self.canonical_payload(), secret)
        return LLMResponse(
            provider=self.provider,
            model=self.model,
            query_hash=self.query_hash,
            response_text=self.response_text,
            confidence=self.confidence,
            timestamp_iso=self.timestamp_iso,
            tokens_used=self.tokens_used,
            source=self.source,
            signature=sig,
            error=self.error,
        )

    def verify_signature(self, secret: Optional[str] = None) -> bool:
        """W30-G: True wenn Signature passt (Tamper-Evidence)."""
        if not self.signature:
            return False
        expected = self.sign_payload(self.canonical_payload(), secret)
        return hmac.compare_digest(expected, self.signature)


class LLMSubfunctionRouter:
    """6-Provider-Router mit Sandbox-Mock-Default.

    Public API:
    - route_query(query, context, provider_priority=None) -> LLMResponse
    - cross_validate(query, context, providers, min_consensus=2) -> list[LLMResponse]
    - is_real_enabled() -> bool
    """

    # Default-Priority-Order (Sunk-Cost-Hierarchie)
    DEFAULT_PRIORITY = [
        LLMProvider.OLLAMA_LOCAL,
        LLMProvider.GEMINI,
        LLMProvider.OPENAI,
        LLMProvider.GROK,
        LLMProvider.MISTRAL,
        LLMProvider.DEEPSEEK,
    ]

    # Mock-Models (Sandbox-Default)
    MOCK_MODELS = {
        LLMProvider.OLLAMA_LOCAL: "llama3.1:8b-mock",
        LLMProvider.GEMINI: "gemini-2.5-pro-mock",
        LLMProvider.OPENAI: "gpt-5.4-mock",
        LLMProvider.GROK: "grok-4.20-mock",
        LLMProvider.MISTRAL: "mistral-large-mock",
        LLMProvider.DEEPSEEK: "deepseek-v2-mock",
    }

    def __init__(self):
        self._real_enabled = os.environ.get("DF_HEYLOU_REAL_LLM_ENABLED", "false") == "true"
        self._timeout_s = int(os.environ.get("DF_HEYLOU_REAL_LLM_TIMEOUT_S", "30"))

    def is_real_enabled(self) -> bool:
        return self._real_enabled

    def _query_hash(self, query: str, context: str) -> str:
        canonical = f"query={query}||context={context}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _mock_response(
        self,
        provider: LLMProvider,
        query: str,
        context: str,
    ) -> LLMResponse:
        """Deterministische Mock-Response (sandbox)."""
        qh = self._query_hash(query, context)
        # Deterministischer Mock-Text basierend auf provider + query_hash
        mock_text = (
            f"[MOCK-{provider.value}] HeyLou-Travel-Domain Sub-Funktion-Response.\n"
            f"Query-Hash: {qh}\n"
            f"Context-Length: {len(context)} chars.\n"
            f"Travel-Domain-Insight: Sandbox-mock answer for query='{query[:50]}...'"
        )
        # Deterministisch leichte Variation pro Provider
        confidence_map = {
            LLMProvider.OLLAMA_LOCAL: 0.65,
            LLMProvider.GEMINI: 0.85,
            LLMProvider.OPENAI: 0.82,
            LLMProvider.GROK: 0.78,
            LLMProvider.MISTRAL: 0.75,
            LLMProvider.DEEPSEEK: 0.72,
        }
        return LLMResponse(
            provider=provider,
            model=self.MOCK_MODELS[provider],
            query_hash=qh,
            response_text=mock_text,
            confidence=confidence_map[provider],
            timestamp_iso=self._now_iso(),
            tokens_used=len(query) // 4 + 100,
            source="mock",
        ).signed()

    def _real_response_stub(
        self,
        provider: LLMProvider,
        query: str,
        context: str,
    ) -> LLMResponse:
        """Real-API-Call placeholder (SKELETON)."""
        qh = self._query_hash(query, context)
        return LLMResponse(
            provider=provider,
            model=f"{provider.value}-real-api-stub",
            query_hash=qh,
            response_text="",
            confidence=0.0,
            timestamp_iso=self._now_iso(),
            tokens_used=0,
            source="stub",
            error=f"real-api not implemented in SKELETON for {provider.value}",
        ).signed()

    def route_query(
        self,
        query: str,
        context: str = "",
        provider_priority: Optional[list[LLMProvider]] = None,
    ) -> LLMResponse:
        """Route query to first available provider in priority-order.

        K11 try/except per provider. LC1 graceful_degradation: fallback to next
        provider if first fails.
        """
        priority = provider_priority or self.DEFAULT_PRIORITY
        last_error = None

        for provider in priority:
            try:
                if self._real_enabled:
                    response = self._real_response_stub(provider, query, context)
                    if response.error:
                        last_error = response.error
                        continue
                    return response
                else:
                    return self._mock_response(provider, query, context)
            except Exception as e:
                logger.warning(f"Provider {provider.value} failed: {e}")
                last_error = str(e)
                continue

        # All providers failed -> return error response from last provider
        qh = self._query_hash(query, context)
        return LLMResponse(
            provider=priority[-1] if priority else LLMProvider.OLLAMA_LOCAL,
            model="error-fallback",
            query_hash=qh,
            response_text="",
            confidence=0.0,
            timestamp_iso=self._now_iso(),
            tokens_used=0,
            source="stub",
            error=f"All providers failed. Last: {last_error}",
        ).signed()

    def cross_validate(
        self,
        query: str,
        context: str = "",
        providers: Optional[list[LLMProvider]] = None,
        min_consensus: int = 2,
    ) -> list[LLMResponse]:
        """Cross-LLM-Validation: route to N providers in parallel (sequential here in SKELETON).

        Returns list of LLMResponses. Caller can aggregate via voting.
        """
        providers = providers or self.DEFAULT_PRIORITY[:min_consensus + 1]
        responses = []
        for provider in providers:
            try:
                if self._real_enabled:
                    resp = self._real_response_stub(provider, query, context)
                else:
                    resp = self._mock_response(provider, query, context)
                responses.append(resp)
            except Exception as e:
                logger.warning(f"Cross-validate provider {provider.value} failed: {e}")
                # Generate error-response for this provider
                qh = self._query_hash(query, context)
                responses.append(LLMResponse(
                    provider=provider,
                    model="error",
                    query_hash=qh,
                    response_text="",
                    confidence=0.0,
                    timestamp_iso=self._now_iso(),
                    tokens_used=0,
                    source="stub",
                    error=str(e),
                ).signed())

        return responses
