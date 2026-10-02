# SkyPulse PRD — Product Requirements Document

**Version:** 1.0  
**Platform:** National Weather Big Data Analytics Platform  
**Status:** Implementation-Ready

---

## 1. Product Overview

### 1.1 Problem Statement

India's weather-related information is fragmented across government agencies, social media, citizen observations, weather APIs, and public datasets. There is no unified platform that:

- Aggregates these heterogeneous signals in real time
- Verifies their accuracy and reliability
- Detects duplicate reports
- Provides a searchable, filterable, geospatially-aware intelligence layer for analysts and emergency responders

The result is delayed situational awareness during critical weather events, leading to inadequate disaster response.

### 1.2 Solution

SkyPulse is a **national weather intelligence platform** — not a forecasting application — that:

1. Continuously ingests weather-related data from authorized multi-source connectors
2. Applies AI/ML for extraction, classification, deduplication, and verification
3. Stores structured weather event intelligence in a centralized database
4. Presents a real-time operational dashboard, analyst interface, admin panel, and citizen reporting interface

### 1.3 Target Users

| Role | Description |
|---|---|
| **Public Viewer** | General public accessing the national weather map |
| **Citizen Reporter** | Citizen submitting first-hand weather observations |
| **Analyst** | IMD/state agency analyst verifying and triaging reports |
| **Administrator** | Platform administrator managing connectors, users, moderation |
| **Government / Disaster Management** | NDMA/state agencies consuming event intelligence for response |

### 1.4 Core Value Proposition

- Single national view of verified weather events, updated in real time
- AI-assisted verification that explains its reasoning
- Full audit trail from raw source to verified event
- No report is deleted — all evidence is preserved and traceable
- Operable without dependence on any single external API (demo mode, graceful fallback)

### 1.5 Scope (v1.0)

**In Scope:**
- Seven weather event types: Rainfall, Thunderstorm, Flooding, Heatwave, Fog, Dust Storm, Strong Winds
- India geography (states, districts, cities, GPS coordinates)
- Authorized API connectors, public dataset connectors, citizen reporting interface
- AI classification, NLP extraction, image analysis, deduplication, verification
- Real-time dashboard, analyst interface, admin panel
- Dynamic Weather Evidence Graph (DWEG) innovation

**Out of Scope (v1.0):**
- Direct scraping of social media without API authorization
- Weather forecasting or predictive modeling
- Mobile native app (web-responsive only in v1)
- International geography

---

## 2. User Roles and Permissions

| Permission | Public | Citizen | Analyst | Admin | Gov/NDMA |
|---|---|---|---|---|---|
| View public dashboard | ✓ | ✓ | ✓ | ✓ | ✓ |
| Submit citizen report | — | ✓ | ✓ | ✓ | ✓ |
| Upload media | — | ✓ | ✓ | ✓ | ✓ |
| View analyst queue | — | — | ✓ | ✓ | ✓ |
| Verify / override reports | — | — | ✓ | ✓ | — |
| View all source details | — | — | ✓ | ✓ | ✓ |
| Manage users | — | — | — | ✓ | — |
| Manage connectors | — | — | — | ✓ | — |
| View audit logs | — | — | — | ✓ | — |
| Export data | — | — | ✓ | ✓ | ✓ |
| Access DWEG full graph | — | — | ✓ | ✓ | ✓ |

---

## 3. Weather Event Taxonomy

The following event categories are supported. This taxonomy is extensible via the admin panel.

| ID | Category | Sub-categories |
|---|---|---|
| EVT-001 | Rainfall | Light Rain, Moderate Rain, Heavy Rain, Extremely Heavy Rain, Cloudburst |
| EVT-002 | Thunderstorm | Lightning, Hail, Thunderstorm with Rain |
| EVT-003 | Flooding | Flash Flood, Urban Flood, River Flood, Coastal Flood |
| EVT-004 | Heatwave | Heatwave, Severe Heatwave |
| EVT-005 | Fog | Dense Fog, Very Dense Fog |
| EVT-006 | Dust Storm | Dust Storm, Sand Storm, Haboob |
| EVT-007 | Strong Winds | Squall, Gale Force Wind, Cyclonic Wind |

Severity scale: **1 (Minor)** → **2 (Moderate)** → **3 (Severe)** → **4 (Extreme)**

---

## 4. Functional Requirements

### 4.1 Data Ingestion

**FR-001** The system shall ingest weather-related data from multiple authorized source connectors continuously.

**FR-002** Each connector shall be independently configurable (polling interval, credentials, enabled/disabled) without restarting the platform.

**FR-003** The system shall support the following connector types:
- Official Weather API connectors (OpenWeatherMap, IMD open data where available)
- Public dataset connectors (historical IMD datasets, NOAA open data)
- RSS/Atom feed connectors (authorized news weather feeds)
- Citizen report connector (platform's own report submission API)
- Demo/simulated connector (synthetic data generation for demonstration)

**FR-004** Each ingested raw record shall be stored with: source identifier, raw content, ingestion timestamp, and source metadata.

**FR-005** Connector failures shall be logged, retried with exponential backoff, and alerted via admin notifications without halting other connectors.

**FR-006** All ingested data shall flow through a message broker (Kafka/Redpanda) before processing, ensuring decoupling and replayability.

### 4.2 Data Collection Fields

**FR-007** For every collected weather report, the system shall capture or extract:
- Date and time (with timezone, stored as UTC)
- City / district / state
- GPS coordinates (latitude, longitude) — either provided or extracted via NLP
- Event category and sub-category
- Severity estimate
- Source identifier and source type
- Raw text content
- Media references (photos, videos) where available
- Source metadata (author, platform, URL, trust score)

**FR-008** Where GPS coordinates are not explicitly provided, the system shall attempt NLP-based location extraction and geocode the result.

**FR-009** Media attachments (photos, videos) shall be stored in object storage (MinIO/S3) with references in the database.

### 4.3 AI Extraction and Classification

**FR-010** The AI pipeline shall extract the following entities from unstructured text: event type, location mentions, severity indicators, time references, and supporting evidence phrases.

**FR-011** The AI pipeline shall classify each report into one or more weather event categories defined in Section 3.

**FR-012** Image analysis shall be applied to attached media to extract visual weather evidence (e.g., waterlogged roads = flood evidence, dust haze = dust storm evidence).

**FR-013** AI extraction confidence scores shall be stored with every report and exposed in the UI.

**FR-014** When the LLM provider is unavailable, the system shall fall back to rule-based extraction (spaCy NER + keyword patterns) without data loss.

### 4.4 Geolocation

**FR-015** All weather reports shall have a geographic coordinate stored as a PostGIS geometry point.

**FR-016** The system shall perform reverse geocoding to populate state, district, and city from GPS coordinates.

**FR-017** Location confidence shall be tracked (GPS-provided = high; geocoded from text = medium; estimated = low).

**FR-018** Spatial queries (bounding box, radius, state/district) shall be supported.

### 4.5 Deduplication

**FR-019** The system shall detect duplicate reports: multiple reports about the same real-world weather event from different sources or the same source.

**FR-020** Deduplication shall use combined signals: semantic text similarity (embeddings), location proximity, time proximity, event category match, and image perceptual hash similarity.

**FR-021** Duplicate reports shall be grouped into a **Duplicate Cluster** under a **Canonical Event**. No original report shall be deleted.

**FR-022** Each canonical event shall aggregate evidence from all its duplicate reports (multi-source corroboration increases confidence).

**FR-023** The system shall allow analysts to manually split incorrect clusters or merge clusters.

### 4.6 Verification

**FR-024** Each canonical weather event shall receive a **Verification Status**: `VERIFIED`, `LIKELY`, `UNVERIFIED`, `CONTRADICTED`, or `REQUIRES_REVIEW`.

**FR-025** Verification shall be evidence-based, using: official API data for the location/time, nearby corroborating reports, source trust score, temporal and spatial consistency checks, image evidence analysis, and historical weather context.

**FR-026** The verification engine shall produce an **explainable verification result**: a human-readable summary of why the status was assigned with supporting evidence items.

**FR-027** Analysts shall be able to manually set verification status with a required reason, overriding the AI recommendation.

**FR-028** Every verification override shall be logged in the audit trail.

### 4.7 Source Trust

**FR-029** Each data source shall have a **Trust Score** (0.0–1.0) calculated from historical verification accuracy, not from fixed assumptions.

**FR-030** New sources start with a neutral trust score (0.5) that adjusts based on the outcome of their reports.

**FR-031** Trust score history shall be visible in the admin panel.

### 4.8 Real-time Processing

**FR-032** Reports shall appear in the dashboard within 10 seconds of ingestion under normal load.

**FR-033** The platform shall use WebSocket connections to push real-time event updates to connected dashboard clients.

**FR-034** Processing throughput shall sustain at minimum 500 reports/minute in the prototype and be architecturally scalable to 50,000 reports/minute.

### 4.9 Dashboard — Public

**FR-035** A public dashboard shall display an interactive India map with real-time active weather events.

**FR-036** The map shall support event clustering, heatmap overlay, and individual event markers.

**FR-037** The dashboard shall show: total active events, events by category, events by state, event timeline, and source distribution.

**FR-038** Filters shall be supported: date range, event category, state, district, verification status, severity, and confidence level.

**FR-039** Event detail view shall show: full event information, verification result with explanation, AI reasoning, all evidence reports, media gallery, source breakdown, and event evolution timeline.

### 4.10 Analyst Interface

**FR-040** Analysts shall have a dedicated queue of incoming reports requiring triage.

**FR-041** The analyst interface shall display AI classification results, verification recommendation, duplicate cluster, and evidence summary for each item.

**FR-042** Analysts shall be able to: confirm AI classification, override classification, verify/reject a report, split/merge duplicate clusters, and add notes.

### 4.11 Admin Panel

**FR-043** Administrators shall manage: users and roles, source connectors (add, edit, enable/disable), verification overrides, system health monitoring, and flagged content moderation.

**FR-044** The admin panel shall display: connector health status, ingestion rate, processing queue depth, error rates, and recent audit log entries.

**FR-045** Administrators shall have access to full audit logs searchable by user, action, entity, and time range.

### 4.12 Citizen Reporting

**FR-046** Citizens shall submit weather reports without requiring registration (anonymous reports accepted with lower initial trust score).

**FR-047** Registered citizens shall have a higher base trust score than anonymous reporters.

**FR-048** The citizen interface shall support: selecting event type, entering description, attaching photos/videos, providing GPS location (device GPS or map pin), and specifying time if different from submission time.

**FR-049** Citizens shall receive a submission confirmation with a report tracking ID and status updates.

**FR-050** The citizen report interface shall work offline (PWA-style) and queue submissions for when connectivity is restored.

### 4.13 Search and Filtering

**FR-051** All reports and events shall be searchable via full-text search (OpenSearch).

**FR-052** Search shall support: text, date range, event type, state, district, city, source, verification status, severity, and confidence filters.

**FR-053** Search results shall be paginated and sortable.

### 4.14 Notifications

**FR-054** Analysts shall receive real-time notifications for: new high-severity unverified events, items assigned to them, and DWEG propagation alerts.

**FR-055** Administrators shall receive alerts for: connector failures, abnormal ingestion rates, and system health degradation.

### 4.15 Auditability

**FR-056** Every write action on the platform shall be logged in the audit log with: user, action type, entity type, entity ID, old value, new value, and timestamp.

**FR-057** Audit logs shall be immutable (insert-only) and retained for minimum 2 years.

---

## 5. Non-Functional Requirements

### 5.1 Scalability

**NFR-001** The architecture shall be horizontally scalable at the connector, AI processing, and API layers via containerization.

**NFR-002** The database shall support table partitioning by date for `weather_reports` and `audit_logs` to maintain query performance at scale.

**NFR-003** The Kafka topic shall support consumer group scaling to increase processing throughput by adding worker instances.

### 5.2 Latency

**NFR-004** Dashboard real-time update latency (from ingestion to browser render) shall be under 10 seconds at p95 under normal load.

**NFR-005** API response time for list and detail endpoints shall be under 500ms at p95.

**NFR-006** Full-text search responses shall complete within 1 second at p95.

### 5.3 Reliability

**NFR-007** The system shall sustain connector failures without affecting the processing pipeline for other connectors.

**NFR-008** The Kafka message broker shall retain messages for 7 days, enabling replay for failed processing.

**NFR-009** System availability target: 99.5% uptime for the dashboard and API layer.

### 5.4 Security

**NFR-010** All API endpoints shall require authentication except explicitly public endpoints.

**NFR-011** Passwords shall be stored as bcrypt hashes with minimum cost factor 12.

**NFR-012** JWT tokens shall have configurable expiration and shall be invalidated on logout.

**NFR-013** All API communication shall be over HTTPS in production.

**NFR-014** Media uploads shall be scanned for malware before processing.

**NFR-015** SQL queries shall use parameterized statements exclusively; no raw string interpolation.

**NFR-016** Rate limiting shall be applied to the citizen report submission endpoint (10 requests/minute per IP).

### 5.5 Privacy

**NFR-017** Citizen report GPS coordinates shall be stored at district-level precision for public display (full precision stored securely for verification purposes only).

**NFR-018** PII in unstructured text (phone numbers, addresses beyond city-level) shall be detected and redacted before storing the public-facing representation.

**NFR-019** GDPR-equivalent data deletion requests shall be fulfillable for registered user accounts.

### 5.6 Maintainability

**NFR-020** All connectors shall implement a common `BaseConnector` interface, making them independently deployable and replaceable.

**NFR-021** AI models shall be swappable via configuration (model name + provider) without code changes.

**NFR-022** Database schema changes shall be managed via Alembic migrations with rollback support.

**NFR-023** All services shall expose a `/health` endpoint.

---

## 6. Acceptance Criteria

| Requirement | Acceptance Criterion |
|---|---|
| Multi-source ingestion | At least 3 distinct connector types active simultaneously, data appearing in DB within 30 seconds |
| Real-time dashboard | Events appear on map within 10 seconds of ingestion at p95 |
| AI classification | >85% classification accuracy on labeled test set of 500 reports |
| Deduplication | Duplicate cluster correctly formed for 90%+ of simulated duplicate sets |
| Verification | Verification status assigned with explanation for 100% of canonical events |
| Citizen reporting | Report submitted, processed, and visible in dashboard within 30 seconds |
| Filtering | All defined filter combinations return correct results within 1 second |
| Admin panel | All connector health statuses visible and accurate within 30 seconds |
| DWEG | Graph updates within 15 seconds of a new corroborating report; propagation alert fires within 30 seconds |
| Demo mode | Full pipeline demonstrable with zero external API keys |

---

## 7. User Workflows

### 7.1 Citizen Reporter Workflow

1. Opens SkyPulse website on mobile
2. Taps "Report Weather Event"
3. Selects event type from categorized list
4. Provides description (free text)
5. Attaches photos/videos (optional)
6. Location captured via device GPS or map pin selection
7. Submits report (works offline; queued if no connectivity)
8. Receives confirmation with tracking ID
9. Receives status notification when report is verified or rejected

### 7.2 Analyst Workflow

1. Logs into analyst interface
2. Views incoming report queue (sorted by severity × confidence)
3. Opens a report; sees AI classification, verification recommendation, evidence, duplicate cluster
4. Reviews evidence (attached media, nearby reports, official API data)
5. Confirms AI classification or overrides with reason
6. Sets verification status with explanation
7. Merges/splits duplicate cluster if needed
8. Receives DWEG propagation alert if event is expanding
9. Exports event summary for government stakeholders

### 7.3 Administrator Workflow

1. Logs into admin panel
2. Checks system health dashboard (connector status, queue depth, error rate)
3. Enables/disables or reconfigures a connector
4. Reviews flagged content (hate speech, fake reports flagged by AI)
5. Reviews audit log for suspicious activity
6. Manages user roles (promotes citizen to analyst)
7. Reviews duplicate cluster decisions

### 7.4 Government / NDMA Workflow

1. Logs into government view (read-only analyst role)
2. Applies state + date filter to view active events in jurisdiction
3. Views DWEG event propagation for an active flood event
4. Exports verified event list as CSV/GeoJSON for emergency systems
5. Views state-level event statistics and trend charts

### 7.5 Public Viewer Workflow

1. Opens public dashboard (no login required)
2. Views India map with active weather events
3. Applies state filter to view local area
4. Clicks on an event marker to view details and media
5. Views event timeline and severity trend
6. Navigates to citizen reporting page to submit own observation

---

## 8. Signature Innovation — Dynamic Weather Evidence Graph (DWEG)

### 8.1 Concept

DWEG is a live knowledge graph maintained in Neo4j that models:

- **Nodes:** WeatherEvent, EvidenceReport, Location, Source, WeatherCondition (official API snapshot)
- **Edges:** CORROBORATES, SPATIALLY_ADJACENT, TEMPORALLY_FOLLOWS, ORIGINATED_FROM, CONTRADICTS, PROPAGATED_TO

As new evidence arrives, DWEG updates the graph and computes:

1. **Event Confidence Field:** A spatial confidence surface showing where an event is most likely occurring, built from the weighted density of corroborating evidence nodes
2. **Propagation Timeline:** Directed temporal graph showing how an event moved through locations over time
3. **Evidence Chain:** Full provenance from raw source to canonical event

### 8.2 User Workflow (Analyst using DWEG)

1. Analyst selects an active canonical event
2. Opens DWEG panel alongside the event detail view
3. Sees graph visualization: event node at center, evidence report nodes linked by CORROBORATES edges, location nodes linked by SPATIALLY_ADJACENT, official data node linked by CORROBORATES or CONTRADICTS
4. Sees the Event Confidence Field heatmap overlaid on the India map for this event
5. Plays the Propagation Timeline animation to see how the event evolved
6. Reads the AI-generated Evidence Chain narrative: "Event first reported in [Location A] at [T], corroborated by 3 citizen reports and 1 official API reading at [T+15min], propagated northeast to [Location B] at [T+30min]"
7. If DWEG detects propagation toward a new district, a propagation alert is fired

### 8.3 What Makes This Distinctive

Unlike simple spatial clustering, DWEG:
- Tracks **directional event propagation** using temporal ordering of evidence nodes
- Uses **spatial adjacency edges** pre-built from district boundary data, not just Euclidean distance
- Incorporates **official API readings** as first-class graph nodes that can corroborate or contradict citizen evidence
- Produces an **evidence chain narrative** that explains the event's lifecycle in natural language
- Can detect when a **new** report in a distant location is more likely a separate event vs. propagation of an existing one

### 8.4 Innovation Acceptance Criteria

- Graph updates within 15 seconds of a new corroborating report
- Propagation alert fires within 30 seconds of detecting spatial expansion
- Evidence chain narrative generated for all events with 3+ reports
- Confidence field visualization renders on India map with <2 second load time
