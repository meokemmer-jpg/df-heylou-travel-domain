"""DF-HeyLou-Travel-Domain [CRUX-MK].

11. Foundation-DF: HeyLou Travel-Domain-Knowledge + Skeleton-Key-Adapter
+ 5-LLM-Sub-Funktion-Pattern (6 Provider inkl. Ollama-Local-Fallback).

Welle-35 Architekt-autonom built per Martin-Direktive 2026-05-11:
*"HeyLou Reisen wie ich es will AI OTA APP die zu allem einen Schnittstelle hat
... Skeleton-Key-Schnittstelle ... Sub-Funktion von Gemini OpenAI Grok Mistral
DeepSeek ... HeyLou ist die Reise KI da diese das Domainknowledge ueber das
Reisen hat"*.

Module:
- travel_knowledge_graph: Hotels + Routes + Rates + Preferences
- skeleton_key_adapter: PMS/OTA/RMS-Connector-Pattern (4 Adapter)
- llm_subfunction_router: 6-LLM-Provider-Routing (HMAC-Signed per W30-G)
- domain_orchestrator: 5-Phase-Loop + LaunchAgent-Entry
- audit_logger: HMAC-SHA256 audit per W30-G

Reference-Files:
- df-100-forschen-research-pipeline/src/research_pipeline.py (W30-G HMAC)
- df-9os-next/src/loop_orchestrator.py (Loop-Pattern)
- df-self-healing-daily/src/__init__.py (Lazy-Import-Pattern)
- ~/.claude/rules/df-akzeptanz-kriterien.md (K11-K16)
- ~/.claude/rules/df-lose-coupling.md (LC1-LC5)
- ~/.claude/rules/env-var-gated-real-integration-default.md
"""

__version__ = "0.1.0"
__all__ = [
    "TravelKnowledgeGraph",
    "Hotel",
    "Route",
    "Rate",
    "GuestPreference",
    "TravelSoftwareAdapter",
    "MEWSAdapter",
    "BookingComAdapter",
    "IdeasRevenueAdapter",
    "GenericAPIAdapter",
    "LLMSubfunctionRouter",
    "LLMProvider",
    "HeyLouTravelDomainOrchestrator",
    "AuditLogger",
]


# Welle-35-Pattern (per df-self-healing-daily): Lazy-Imports verhindern
# Doppel-Load wenn Modul via `python -m src.domain_orchestrator` aufgerufen wird
# (RuntimeWarning + `__name__` != "__main__" Bug). Eager-Import wuerde Modul
# beim Package-Load bereits in sys.modules eintragen, bevor `__main__`-Logik
# laeuft.
def __getattr__(name):
    if name == "TravelKnowledgeGraph":
        from .travel_knowledge_graph import TravelKnowledgeGraph
        return TravelKnowledgeGraph
    if name == "Hotel":
        from .travel_knowledge_graph import Hotel
        return Hotel
    if name == "Route":
        from .travel_knowledge_graph import Route
        return Route
    if name == "Rate":
        from .travel_knowledge_graph import Rate
        return Rate
    if name == "GuestPreference":
        from .travel_knowledge_graph import GuestPreference
        return GuestPreference
    if name == "TravelSoftwareAdapter":
        from .skeleton_key_adapter import TravelSoftwareAdapter
        return TravelSoftwareAdapter
    if name == "MEWSAdapter":
        from .skeleton_key_adapter import MEWSAdapter
        return MEWSAdapter
    if name == "BookingComAdapter":
        from .skeleton_key_adapter import BookingComAdapter
        return BookingComAdapter
    if name == "IdeasRevenueAdapter":
        from .skeleton_key_adapter import IdeasRevenueAdapter
        return IdeasRevenueAdapter
    if name == "GenericAPIAdapter":
        from .skeleton_key_adapter import GenericAPIAdapter
        return GenericAPIAdapter
    if name == "LLMSubfunctionRouter":
        from .llm_subfunction_router import LLMSubfunctionRouter
        return LLMSubfunctionRouter
    if name == "LLMProvider":
        from .llm_subfunction_router import LLMProvider
        return LLMProvider
    if name == "HeyLouTravelDomainOrchestrator":
        from .domain_orchestrator import HeyLouTravelDomainOrchestrator
        return HeyLouTravelDomainOrchestrator
    if name == "AuditLogger":
        from .audit_logger import AuditLogger
        return AuditLogger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
