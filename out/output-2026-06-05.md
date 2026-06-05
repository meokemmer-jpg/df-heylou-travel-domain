# df-heylou-travel-domain — Output [CRUX-MK]
*Autonom aktiviert 2026-06-05T10:25:43.082427+00:00 | ollama-local/qwen2.5:14b-instruct*

# HeyLou Reisen AI OTA APP Dokumentation

## Mission
HeyLou-Reisen ist eine KI-Funktion, spezialisiert auf den Bereich Reiseplan
Reiseplanung und -buchung, die als Subfunktion in fünf Generalzweck-LLM-Pla
Generalzweck-LLM-Plattformen integriert wird: Gemini, OpenAI (ChatGPT/Codex
(ChatGPT/Codex), Grok (xAI), Mistral und DeepSeek. Zusätzlich bildet sie ei
eine zentrale Webseite zum Onboarding von Hoteliers.

## Architektur
Die Architektur des Systems besteht aus fünf Modulen:

- **travel_knowledge_graph.py**: Enthält in-Memory-Daten für Hotels, Routen
Routen, Preise und Präferenzen (mit Mock-Daten).
- **skeleton_key_adapter.py**: Schnittstellendesign für PMS/OTA/RMS-Konnekt
PMS/OTA/RMS-Konnektoren mit vier konkreten Anwendungen: MEWSAdapter (PMS), 
BookingComAdapter (OTA), IdeasRevenueAdapter (RMS) und GenericAPIAdapter (S
(Schnittstelle zum HTTP-API-Connector).
- **llm_subfunction_router.py**: Routenplaner für sechs LLM-Provider, der j
jedes Aufruf mit HMAC-SHA256-Zugriffssicherheit signiert.
- **domain_orchestrator.py**: Führt einen fünfphasigen Loop aus und dient a
als Entry-Punkt des LaunchAgents.
- **audit_logger.py**: Protokolliert alle Aktionen, die durch die KI ausgef
ausgeführt werden, inklusive HMAC-Signatur.

## Funktionale Bestandteile
Die Hauptfunktion von HeyLou-Reisen umfasst:
1. **Travel-Domain-Knowledge**: Zentralisierte Datenbank mit Reiseinformati
Reiseinformationen.
2. **Skeleton-Key-Adapter**: Adapterpatron, die es ermöglicht, mit jeder be
beliebigen Hotel-/OTA-/PMS-/RMS-Software zu kommunizieren.
3. **LLM-Subfunktion-Routing**: Mechanismus zur Verteilung von Anfragen an 
verschiedene LLMs basierend auf den spezifischen Bedürfnissen des Nutzers.

## Wichtige Verwendungsbestimmungen
1. Alle Adapter sind im Sandboxmodus (Mock-Arbeit) aktiviert.
2. Reale Aufrufe zu LLM-Providern werden nur durch die Umgebungsvariable `D
`DF_HEYLOU_REAL_LLM_ENABLED=true` und das Ticket PHRONESIS aktiviert.

## Zukunftsvision
HeyLou-Reisen soll ein zentrales System für Reiseplanung und -buchung in de
der Hotelindustrie sein, welches dank seiner Flexibilität und Spezialität ü
über verschiedene Plattformen und Anbieter skalierbar ist. Es soll eine eff
effektive Schnittstelle bieten, die es den Hotels ermöglicht, ihre Buchunge
Buchungen zu optimieren und ihren Umsatz zu steigern.

Diese Dokumentation dient als grundlegende Struktur für die Entwicklung und
und Nutzung der HeyLou-Reisen-Technologie und wird im Laufe der Zeit weiter
weiter verbessert und erweitert.