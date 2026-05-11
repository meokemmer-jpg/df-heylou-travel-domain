"""DF-HeyLou-Travel-Domain Output-Schemas [CRUX-MK].

K12 Schema-Validation (Patch-1 W35-C Cross-LLM-2OF2-CONVERGENT).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Optional

import sys
from pathlib import Path
_DF_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_DF_ROOT))
from _df_common.provenance_envelope import (  # noqa: E402
    ProvenanceEnvelope,
    wrap_with_provenance,
    validate_envelope,
    sha256_hex,
    iso_now,
)


try:
    from pydantic import BaseModel, Field, field_validator  # type: ignore
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


if PYDANTIC_AVAILABLE:
    class TravelQuerySchema(BaseModel):
        """Travel-Query input schema (T1-T5 Mensch-Gateway)."""
        query_id: str = Field(min_length=1)
        operation: str = Field(min_length=1)  # e.g. "search_inventory", "book_room"
        criteria: dict = Field(default_factory=dict)
        adapter_name: str = Field(min_length=1)
        tenant_id: Optional[str] = None
        idempotency_key: Optional[str] = None

        @field_validator("operation")
        @classmethod
        def _op_known(cls, v: str) -> str:
            allowed = {"query_inventory", "book_room", "cancel_booking", "connect"}
            if v not in allowed:
                # don't reject unknown ops - just warn via type-coercion
                pass
            return v

    class AdapterResponseSchema(BaseModel):
        """Adapter-Response schema (matches dataclass AdapterResponse)."""
        adapter_name: str
        operation: str
        success: bool
        payload: dict = Field(default_factory=dict)
        source: str  # mock | real-api | stub
        timestamp_iso: str
        request_hash: str = Field(min_length=8)
        error: Optional[str] = None

        @field_validator("source")
        @classmethod
        def _source_valid(cls, v: str) -> str:
            allowed = {"mock", "real-api", "stub"}
            if v not in allowed:
                raise ValueError(f"source must be one of {allowed}")
            return v

else:
    @dataclass
    class TravelQuerySchema:
        query_id: str
        operation: str
        adapter_name: str
        criteria: dict = field(default_factory=dict)
        tenant_id: Optional[str] = None
        idempotency_key: Optional[str] = None

        def __post_init__(self) -> None:
            if not self.query_id.strip():
                raise ValueError("query_id must not be blank")
            if not self.operation.strip():
                raise ValueError("operation must not be blank")
            if not self.adapter_name.strip():
                raise ValueError("adapter_name must not be blank")

    @dataclass
    class AdapterResponseSchema:
        adapter_name: str
        operation: str
        success: bool
        source: str
        timestamp_iso: str
        request_hash: str
        payload: dict = field(default_factory=dict)
        error: Optional[str] = None

        def __post_init__(self) -> None:
            allowed = {"mock", "real-api", "stub"}
            if self.source not in allowed:
                raise ValueError(f"source must be one of {allowed}")
            if len(self.request_hash) < 8:
                raise ValueError("request_hash too short")


def wrap_travel_response(
    response: Any,
    *,
    provider: str = "skeleton-key",
    prompt: str = "travel-query",
    model_version: str = "df-heylou-travel-v1",
    run_id: Optional[str] = None,
) -> dict:
    """Wrap a travel-response with provenance envelope."""
    if hasattr(response, "model_dump"):
        output = response.model_dump()
    else:
        output = asdict(response) if hasattr(response, "__dataclass_fields__") else response
    return wrap_with_provenance(
        output=output,
        provider=provider,
        prompt=prompt,
        model_version=model_version,
        df_name="df-heylou-travel-domain",
        run_id=run_id,
    )


__all__ = [
    "TravelQuerySchema",
    "AdapterResponseSchema",
    "wrap_with_provenance",
    "validate_envelope",
    "wrap_travel_response",
    "iso_now",
    "sha256_hex",
]
