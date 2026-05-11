# DF-HeyLou-Travel-Domain [CRUX-MK]

**11. Foundation-DF im Kemmer Dark-Factories System.**

Welle-35 Foundation-DF: Travel-Domain-Knowledge + Skeleton-Key-Adapter + 5-LLM-Provider-Sub-Funktion-Pattern.

Built per Martin-Direktive 2026-05-11:
> *"HeyLou Reisen wie ich es will AI OTA APP die zu allem einen Schnittstelle hat ... Skeleton-Key-Schnittstelle ... Sub-Funktion von Gemini OpenAI Grok Mistral DeepSeek ... HeyLou ist die Reise KI da diese das Domainknowledge ueber das Reisen hat"*

Mosaic-Plan: `branch-hub/findings/HEYLOU-TRAVEL-MOSAIC-PLAN-WELLE-35-PLUS-2026-05-11.md`

## Scope

Travel-Domain-Knowledge zentralisiert + Adapter-Pattern fuer beliebige Hotel-/OTA-/PMS-/RMS-Software + LLM-Sub-Funktion-Routing ueber 6 Provider (Ollama-Local + Gemini + OpenAI + Grok + Mistral + DeepSeek).

**Eigenstaendig:** kein Cross-DF-Coupling zu Mac-Foundation-DFs notwendig.

## 5-LLM-Sub-Funktion-Pattern

HeyLou orchestriert 5 General-Purpose-LLMs als Sub-Funktion mit Travel-Domain-Knowledge als Specialization-Layer. Jeder LLM-Call wird:

1. Mit Travel-Knowledge-Graph-Context angereichert
2. Via HMAC-SHA256 (per W30-G) signed fuer Provenance
3. Cross-LLM-validated (mind. 2 Provider) bei K_0/Q_0-Naehe
4. Sandbox-default; Real-Calls nur via `DF_HEYLOU_REAL_LLM_ENABLED=true` + PHRONESIS_TICKET

```
HeyLou-Travel-Domain (Specialization)
        |
        +--> Ollama-Local (Primary, Internet-unabhaengig)
        |
        +--> Gemini (Long-Context Travel-Itineraries)
        +--> OpenAI (Reasoning, Booking-Logic)
        +--> Grok (Real-time Travel-Disruption)
        +--> Mistral (EU-DSGVO-konform)
        +--> DeepSeek (Cost-effective Routine)
```

## Skeleton-Key-Pattern

Adapter-Interface `TravelSoftwareAdapter` mit 4 konkreten Implementierungen (alle MOCK im Sandbox-Mode):

- `MEWSAdapter` — PMS-Industry-Leader (Mock)
- `BookingComAdapter` — OTA-Industry-Leader (Mock)
- `IdeasRevenueAdapter` — RMS-Industry-Leader (Mock)
- `GenericAPIAdapter` — Skeleton-Key-Pattern: HTTP-API-Connector mit Endpoint-Discovery

T5-Mensch-Gateway-Inbox-Note bei Adapter-Auth-Failures (per skeleton-key Pattern).

## Architektur (5 Module)

```
src/
  travel_knowledge_graph.py    # Hotels + Routes + Rates + Preferences (In-Memory + Mock-Daten)
  skeleton_key_adapter.py      # PMS/OTA/RMS-Connector-Pattern (4 Adapter)
  llm_subfunction_router.py    # 6-LLM-Provider-Routing (HMAC-Signed)
  domain_orchestrator.py       # 5-Phase-Loop + LaunchAgent-Entry
  audit_logger.py              # HMAC-SHA256 audit per W30-G
```

## CRUX-Bindung

- **K_0:** Travel-Decisions ohne Phronesis bleiben Sandbox-Mock; Real-API-Calls nur via PHRONESIS_TICKET
- **Q_0:** Domain-Knowledge zentralisiert, kein Drift zwischen Hotels/Routes
- **W_0:** Skeleton-Key-Pattern reduziert N×M Adapter-Aufwand auf N+M
- **L_Martin:** Real-Daten gegated, Override jederzeit via STOP.flag

## Lokal-Run

```bash
cd ~/Projects/dark-factories/df-heylou-travel-domain
python3 -c "from src.domain_orchestrator import HeyLouTravelDomainOrchestrator
orch = HeyLouTravelDomainOrchestrator()
report = orch.run('hildesheim', 'Daily Travel-Domain-Health-Check')
print(report.final_status)"
```

## Tests

```bash
cd ~/Projects/dark-factories/df-heylou-travel-domain
pytest tests/ -v
```

Total >=29 Tests pflicht (5 Module).

## LaunchAgent-Install

```bash
cp scripts/com.kemmer.df-heylou-travel-domain.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.kemmer.df-heylou-travel-domain.plist
```

Cadence: RunAtLoad + StartInterval=3600 (hourly).

## Status

- **Tier:** SKELETON (Welle-35)
- **Promotion-Pfad:** PRE-PRODUCTION-CONDITIONAL pending Cross-LLM-Wargame Welle-36
- **Real-Mode:** Sandbox-Default (DF_HEYLOU_REAL_LLM_ENABLED=false + DF_HEYLOU_REAL_ADAPTER_ENABLED=false)

## Reference-Patterns

- `_df_common/self_healing.py` (W32-Schritt-10 Decorator)
- `df-100-forschen-research-pipeline/src/research_pipeline.py` (W30-G HMAC-SHA256)
- `df-9os-next/src/loop_orchestrator.py` (Loop-Phase-Pattern)
- `df-self-healing-daily/src/__init__.py` (Lazy-Import-Pattern)
- `~/.claude/rules/df-akzeptanz-kriterien.md` (K11-K16)
- `~/.claude/rules/df-lose-coupling.md` (LC1-LC5)
- `~/.claude/rules/env-var-gated-real-integration-default.md` (ENV-Var-Pattern)
- `~/.claude/rules/subagent-output-commit-pflicht.md` (W33 git-commit-Pflicht)

[CRUX-MK]
