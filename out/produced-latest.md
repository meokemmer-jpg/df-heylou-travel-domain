# df-heylou-travel-domain — PRODUKTION [CRUX-MK]
*2026-06-09T14:43:21.458902+00:00 | ollama-local/kemmer-14b-ctx8k*

# HeyLou Reisen AI OTA APP Dokumentation

## Einführung
HeyLou-Reisen ist eine künstliche Intelligenz, die spezialisiert auf den Bereich der Reiseplanung und -buchung ist. Sie integriert sich als Subfunktion in fünf Generalzweck-LLM-Plattformen: Gemini, OpenAI (ChatGPT/Codex), Grok (xAI), Mistral und DeepSeek. Zusätzlich bildet sie eine zentrale Webseite zum Onboarding von Hoteliers.

Diese Dokumentation dient als grundlegende Strukturierung für den Einsatz der HeyLou-Reisen AI OTA APP in der Industrie, um die Flexibilität und Effizienz bei Reiseplanung und -buchung zu erhöhen. Die Architektur des Systems ist so gestaltet, dass sie sich anpassen kann, um verschiedene Plattformen und Anbieter zu unterstützen.

## Mission

HeyLou-Reisen wurde entwickelt, um die Komplexität der Reiseplanungs- und Buchungsprozesse für Hotels, OTAs, PMSs und RMSs zu reduzieren. Durch ihre Integration in fünf Generalzweck-LLM-Plattformen bietet sie eine zentrale Schnittstelle, die es den Nutzern ermöglicht, alle notwendigen Informationen und Anfragen schnell und effizient abzuarbeiten.

### Zielgruppe
HeyLou-Reisen ist für Hoteliers, Reisebüros, Onlineservice-Portale (OTAs) und Revenue Management Systeme (RMSs) gedacht, die eine zentrale Plattform benötigen, um ihre Reiseangebote zu optimieren und zu verwalten.

## Architektur

Die Architektur von HeyLou-Reisen ist in fünf Hauptmodule unterteilt:

1. **travel_knowledge_graph.py**
2. **skeleton_key_adapter.py**
3. **llm_subfunction_router.py**
4. **domain_orchestrator.py**
5. **audit_logger.py**

### 1. travel_knowledge_graph.py

Dieses Modul enthält die zentrale Datenbank, in der Reiseinformationen wie Hotels, Routen, Preise und Präferenzen gespeichert sind. Die Informationen werden in einem In-Memory-Modell gehalten und können mit Mock-Daten gefüllt sein, um den Testprozess zu erleichtern.

#### Hauptfunktionen:
- Zentralisierung von Reiseinformationen.
- Verwaltung von Hotels, Routen, Preisen und Präferenzen.
- Möglichkeit zur Erweiterung durch externe Datenquellen (APIs).

### 2. skeleton_key_adapter.py

Dieses Modul ist der Schnittstellendesign für PMS/OTA/RMS-Konnektoren. Es umfasst vier konkrete Anwendungen:
- MEWSAdapter: Verbindet HeyLou-Reisen mit dem Property Management System (PMS).
- BookingComAdapter: Integriert die OTAs, wie Booking.com.
- IdeasRevenueAdapter: Verbindet das Revenue Management System (RMS) für optimierte Buchungsstrategien.
- GenericAPIAdapter: Ein allgemeiner HTTP-API-Connector zur Unterstützung unbekannter oder neuen APIs.

#### Hauptfunktionen:
- Adapter-Pattern für interne und externe APIs.
- Erstellung von Schnittstellen, um den Zugriff auf jede beliebige Hotel-/OTA-/PMS-/RMS-Software zu ermöglichen.
- Inklusive Fehlernachrichten und Authentifizierungsmechanismen (T5-Mensch-Gateway-Inbox-Note bei Adapter-Auth-Failures).

### 3. llm_subfunction_router.py

Dieses Modul ist verantwortlich für die Verteilung von Anfragen an verschiedene LLMs basierend auf den spezifischen Bedürfnissen des Nutzers.

#### Hauptfunktionen:
- Routenplaner für sechs LLM-Provider.
- Sicherheit durch HMAC-SHA256-Zugriffssicherheit.
- Validierung aller Anfragen und Antworten durch mindestens zwei Provider, um die Integrität der Antworten zu gewährleisten.

### 4. domain_orchestrator.py

Dieses Modul führt den fünfphasigen Loop aus, der für den Einsatz von HeyLou-Reisen notwendig ist, sowie dient als Entry-Punkt des LaunchAgents.

#### Hauptfunktionen:
- Führen eines fuenfphasigen Loops.
- Eintrittspunkt für den Aufbau und die Laufzeitsteuerung aller Module.

### 5. audit_logger.py

Dieses Modul protokolliert alle Aktionen, die durch die KI ausgeführt werden, einschließlich der HMAC-Signatur.

#### Hauptfunktionen:
- Protokollierung von Aktivitäten.
- Sicherheit durch HMAC-Signaturen bei jedem Zugriff und Verarbeitungsprozess.

## Funktionale Bestandteile

### 1. Travel-Domain-Knowledge
Zentralisierte Datenbank mit Reiseinformationen, welche Hotels, Routen, Preise und Präferenzen enthält.

### 2. Skeleton-Key-Adapter
Schnittstellendesign für PMS/OTA/RMS-Konnektoren, ermöglicht den Zugriff auf jede beliebige Hotel-/OTA-/PMS-/RMS-Software via Adapterpatron (MEWSAdapter, BookingComAdapter, IdeasRevenueAdapter, GenericAPIAdapter).

### 3. LLM-Subfunktion-Routing
Mechanismus zur Verteilung von Anfragen an verschiedene LLMs basierend auf den spezifischen Bedürfnissen des Nutzers.

## Wichtige Verwendungsbestimmungen

1. Alle Adapter sind im Sandboxmodus (Mock-Arbeit) aktiviert.
2. Reale Aufrufe zu LLM-Providern werden nur durch die Umgebungsvariable `DF_HEYLOU_REAL_LLM_ENABLED=true` und das Ticket PHRONESIS aktiviert.

## Zukunftsvision

HeyLou-Reisen soll ein zentrales System für Reiseplanung und -buchung in der Hotelindustrie sein, welches dank seiner Flexibilität und Spezialität über verschiedene Plattformen und Anbieter skalierbar ist. Es soll eine effektive Schnittstelle bieten, die es den Hotels ermöglicht, ihre Buchungen zu optimieren und ihren Umsatz zu steigern.

### Visionäre Ziele:
- Integration mit mehreren weiteren LLMs, um ein breiteres Spektrum an Diensten anzubieten.
- Weiterentwicklung der Travel-Domain-Knowledge für eine detailliertere Reiseplanung.
- Verbesserung der Interaktivität und Benutzerfreundlichkeit für Hoteliers.

Diese Dokumentation dient als grundlegende Strukturierung für die Einführung von HeyLou-Reisen in der Industrie und soll fortlaufend verbessert werden, um den Anforderungen zu entsprechen.