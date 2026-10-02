# SkyPulse — Implementation Plan

**Version:** 1.0  
**Audience:** Coding agent  
**Status:** Implementation-Ready

---

## Implementation Principles

1. **Never skip a phase** — each phase produces working, testable output
2. **No placeholder code** — every implemented feature must work end-to-end
3. **Test as you build** — write tests alongside the code that requires them
4. **Environment variables always** — no secrets or config in source code
5. **Migrations for all schema changes** — never edit a table directly

---

## Dependency Graph (Phases)

```
Phase 1 (Setup)
    ↓
Phase 2 (Database)
    ↓
Phase 3 (Backend API) ──────────────┐
    ↓                               │
Phase 4 (Ingestion) ←── depends on Phase 3 (source/report endpoints)
    ↓
Phase 5 (AI/ML) ←── depends on Phase 4 (raw records to process)
    ↓
Phase 6 (Verification) ←── depends on Phase 5 (AI output)
    ↓
Phase 7 (Real-time) ←── depends on Phases 3, 5, 6
    ↓
Phase 8 (Dashboard) ←── depends on Phases 3, 7
    ↓
Phase 9 (Admin Panel) ←── depends on Phase 3
    ↓
Phase 10 (DWEG) ←── depends on Phases 5, 6, 7, 8
    ↓
Phase 11 (Testing) ←── depends on all phases
    ↓
Phase 12 (Deployment)
```

---

## Phase 1 — Project Setup

### Goal
Running infrastructure with empty application scaffolding.

### Tasks

1. **Initialize repository structure**
   - Create directories: `backend/`, `frontend/`, `infra/`, `scripts/`, `tests/`
   - Create `README.md`, `.gitignore`, `.env.example`

2. **Docker Compose — full stack**
   - File: `docker-compose.yml`
   - Services: `postgres`, `redis`, `redpanda`, `minio`, `opensearch`, `neo4j`, `nginx`
   - File: `docker-compose.demo.yml` — extends base + adds `connector-demo`, `ai-worker` pre-seeded

3. **Backend scaffold**
   - `backend/requirements.txt` — include: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic[email], redis, aiokafka, boto3, opensearch-py, neo4j, sentence-transformers, transformers, spacy, opencv-python-headless, python-jose[cryptography], passlib[bcrypt], python-multipart, httpx, tenacity
   - `backend/app/main.py` — FastAPI app with CORS, lifespan events, router mounting
   - `backend/app/core/config.py` — Settings class reading from env vars
   - `backend/app/core/security.py` — JWT creation/validation, password hashing
   - `backend/app/db/session.py` — Async SQLAlchemy engine + session factory
   - `backend/app/db/base.py` — Base model with `id`, `created_at`, `updated_at`

4. **Frontend scaffold**
   - Bootstrap with Vite + React + TypeScript: `npm create vite@latest frontend -- --template react-ts`
   - Install: `react-router-dom`, `zustand`, `socket.io-client`, `recharts`, `maplibre-gl`, `@maplibre/maplibre-gl-leaflet`
   - Create directory structure: `src/components/`, `src/pages/`, `src/store/`, `src/hooks/`, `src/utils/`, `src/types/`
   - `src/index.css` — Full design system CSS variables (from UI_UX.md)

5. **Nginx config**
   - `infra/nginx/nginx.conf` — Proxy `/api` to backend:8000, `/ws` to backend:8000, `/` to frontend:3000

6. **Health check endpoints**
   - `GET /health` — Returns `{"status": "ok"}`

### Dependencies
None (first phase)

### Files to Create
```
docker-compose.yml
docker-compose.demo.yml
.env.example
.gitignore
backend/
  requirements.txt
  app/
    main.py
    core/
      config.py
      security.py
    db/
      session.py
      base.py
frontend/
  package.json
  vite.config.ts
  src/
    index.css
    main.tsx
    App.tsx
infra/
  nginx/
    nginx.conf
```

### Completion Criteria
- `docker compose up -d` starts all infrastructure services
- `GET /health` returns 200
- React dev server starts without errors
- Frontend renders at `http://localhost:3000`

---

## Phase 2 — Database

### Goal
Complete database schema deployed and migrated.

### Tasks

1. **Alembic setup**
   - `backend/alembic.ini` — point to DATABASE_URL
   - `backend/alembic/env.py` — import all models for autogenerate

2. **SQLAlchemy models** (one file per model)
   - `backend/app/models/user.py` → `users` table
   - `backend/app/models/source.py` → `sources`, `source_reputation_history`, `connector_health`
   - `backend/app/models/weather_report.py` → `weather_reports` (partitioned)
   - `backend/app/models/weather_event.py` → `weather_events`
   - `backend/app/models/event_evidence.py` → `event_evidence`
   - `backend/app/models/media.py` → `media`
   - `backend/app/models/location.py` → `locations`
   - `backend/app/models/verification.py` → `verification_results`, `verification_evidence`
   - `backend/app/models/duplicate_cluster.py` → `duplicate_clusters`
   - `backend/app/models/notification.py` → `notifications`
   - `backend/app/models/audit_log.py` → `audit_logs` (partitioned)

3. **Initial migration**
   - `alembic revision --autogenerate -m "initial_schema"`
   - `alembic upgrade head`
   - Verify all tables created in PostgreSQL

4. **PostGIS + pgvector setup**
   - Migration includes `CREATE EXTENSION` statements
   - Verify `ST_Distance` and `<=>` vector operator work

5. **Partition management script**
   - `scripts/create_partitions.py` — creates next 12 monthly partitions for `weather_reports` and `audit_logs`
   - Called at startup and by monthly cron

6. **OpenSearch index creation**
   - `backend/app/db/opensearch_indexes.py` — creates `weather_reports` index with mapping from DATABASE_SCHEMA.md

7. **Seed locations data**
   - `scripts/seed_locations.py` — loads Indian states, districts, cities from GeoJSON (use `india-districts.geojson` from public domain sources)
   - Computes and stores `adjacent_location_ids` for each district from boundary intersections

### Dependencies
Phase 1 complete.

### Files to Create
```
backend/
  alembic.ini
  alembic/
    env.py
    versions/
      001_initial_schema.py
  app/
    models/
      __init__.py
      user.py
      source.py
      weather_report.py
      weather_event.py
      event_evidence.py
      media.py
      location.py
      verification.py
      duplicate_cluster.py
      notification.py
      audit_log.py
    db/
      opensearch_indexes.py
scripts/
  create_partitions.py
  seed_locations.py
data/
  india-districts.geojson
```

### Tests
- `tests/unit/test_models.py` — test model instantiation and relationships
- `tests/integration/test_db.py` — test spatial queries, vector similarity

### Completion Criteria
- `alembic upgrade head` runs without error
- All tables exist with correct columns, indexes, and constraints
- PostGIS spatial query returns correct results
- `weather_reports` table has monthly partitions
- `locations` table populated with Indian districts

---

## Phase 3 — Backend API

### Goal
All REST API endpoints implemented, authenticated, and tested.

### Tasks

1. **Pydantic schemas** (request/response)
   - `backend/app/schemas/` — one file per domain: `auth.py`, `report.py`, `event.py`, `verification.py`, `source.py`, `analytics.py`, `map.py`, `admin.py`, `dweg.py`, `media.py`

2. **Auth endpoints**
   - `backend/app/api/auth.py`
   - `POST /api/v1/auth/login`
   - `POST /api/v1/auth/register`
   - `POST /api/v1/auth/logout`
   - `GET /api/v1/auth/me`

3. **Report endpoints**
   - `backend/app/api/reports.py`
   - `POST /api/v1/reports`
   - `POST /api/v1/reports/media`
   - `GET /api/v1/reports`
   - `GET /api/v1/reports/{report_id}`
   - `GET /api/v1/reports/search`

4. **Event endpoints**
   - `backend/app/api/events.py`
   - All event endpoints from API_SPECIFICATION.md

5. **Verification endpoints**
   - `backend/app/api/verification.py`

6. **Source endpoints**
   - `backend/app/api/sources.py`

7. **Analytics endpoints**
   - `backend/app/api/analytics.py`

8. **Map endpoints**
   - `backend/app/api/map.py`

9. **Admin endpoints**
   - `backend/app/api/admin.py`

10. **Media endpoint**
    - `backend/app/api/media.py` — stream from MinIO

11. **Role-based access control**
    - `backend/app/core/dependencies.py` — `get_current_user`, `require_role(role)` FastAPI dependencies
    - Applied to every protected endpoint

12. **Audit logging middleware**
    - `backend/app/core/audit.py` — logs every write operation

13. **Rate limiting**
    - Redis-backed rate limiter for `/api/v1/reports` (citizen endpoint)

14. **MinIO integration**
    - `backend/app/services/storage.py` — upload, get presigned URL, delete
    - Bucket created on startup

15. **Services layer**
    - `backend/app/services/report_service.py`
    - `backend/app/services/event_service.py`
    - `backend/app/services/verification_service.py`
    - `backend/app/services/analytics_service.py`

### Dependencies
Phase 2 complete.

### Files to Create
```
backend/app/
  api/
    __init__.py
    router.py
    auth.py
    reports.py
    events.py
    verification.py
    sources.py
    analytics.py
    map.py
    admin.py
    media.py
    dweg.py (placeholder for Phase 10)
  schemas/
    auth.py
    report.py
    event.py
    verification.py
    source.py
    analytics.py
    map.py
    admin.py
    dweg.py
    media.py
  core/
    dependencies.py
    audit.py
    rate_limit.py
  services/
    report_service.py
    event_service.py
    verification_service.py
    analytics_service.py
    storage_service.py
```

### Tests
- `tests/integration/test_auth_api.py`
- `tests/integration/test_reports_api.py`
- `tests/integration/test_events_api.py`
- `tests/integration/test_analytics_api.py`

### Completion Criteria
- All endpoints return correct responses per API_SPECIFICATION.md
- Authentication works; protected endpoints return 401 without token
- Role-based access enforced (ANALYST endpoint returns 403 for CITIZEN role)
- Media upload stores to MinIO and returns media_id
- FastAPI auto-generated docs at `/docs` show all endpoints

---

## Phase 4 — Data Ingestion

### Goal
Working connector framework with at minimum Demo and WeatherAPI connectors.

### Tasks

1. **Base connector interface**
   - `backend/connectors/base.py` — `BaseConnector` abstract class with `poll()`, `parse()`, `health_check()`, `metadata()`

2. **Kafka producer utility**
   - `backend/connectors/producer.py` — `KafkaProducer` wrapper using `aiokafka`

3. **Demo connector**
   - `backend/connectors/demo_connector.py`
   - Generates synthetic weather reports for Indian cities
   - Realistic distribution: all 7 event types, all severity levels
   - Configurable rate (default: 1 report every 10 seconds)
   - Tags all records with `is_demo: true`
   - Supports configurable burst mode for demonstrations

4. **WeatherAPI connector** (real, marked as REAL integration)
   - `backend/connectors/weather_api_connector.py`
   - Polls WeatherAPI.com for current conditions in top 50 Indian cities
   - Converts API response to normalized weather report format
   - Requires `WEATHERAPI_KEY` env var; skips gracefully if not set

5. **IMD Government Connector** (Step 3 real government integration)
   - `backend/connectors/imd_connector.py`
   - Ingests official IMD current weather, nowcasts, warnings, AWS/ARG observations, rainfall
   - Sets `source_type = 'GOVERNMENT_API'` with high-trust government provenance

6. **data.gov.in Government Dataset Connector** (Step 4 real open government data integration)
   - `backend/connectors/data_gov_connector.py`
   - Ingests published Indian government datasets (CWC river levels, OGD rainfall, heatwave observatories)
   - Sets `source_type = 'GOVERNMENT_DATASET'`, provider = `data.gov.in`

7. **RSS Feed connector** (demo/test feeds available)
   - `backend/connectors/rss_connector.py`
   - Parses standard RSS/Atom feeds
   - Pre-configured with test weather news feeds

7. **Connector worker runner**
   - `backend/workers/connector_runner.py`
   - Reads enabled sources from DB
   - Instantiates the appropriate connector class
   - Runs each connector in an asyncio task
   - Updates `connector_health` table every 60 seconds

8. **Raw record consumer → DB writer**
   - `backend/workers/ingestion_writer.py`
   - Consumes `skypulse.raw` Kafka topic
   - Validates record schema
   - Writes raw `weather_report` with `status=PENDING`
   - Publishes report ID to `skypulse.pending_ai` topic for AI processing

9. **Connector health monitor**
   - Updates `connector_health.last_check_at` and `status`
   - Sends notification if connector goes DOWN

### Connector Distinction

Clearly distinguish in code and DB:
- `is_demo = True` — Demo/simulated connectors
- `source_type = 'WEATHER_API'` — Real API integrations
- All sources stored in `sources` table with `connector_class` field

### Files to Create
```
backend/
  connectors/
    __init__.py
    base.py
    producer.py
    demo_connector.py
    weather_api_connector.py
    openweathermap_connector.py
    rss_connector.py
  workers/
    connector_runner.py
    ingestion_writer.py
    connector_health_monitor.py
```

### Tests
- `tests/unit/test_demo_connector.py` — verify demo connector output schema
- `tests/unit/test_connector_base.py` — test base class interface

### Completion Criteria
- Demo connector produces records at configured rate
- Records appear in `weather_reports` table with `status=PENDING` within 5 seconds
- Connector health table updated for all active connectors
- Disabling a connector in DB stops its ingestion within 60 seconds

---

## Phase 5 — Real AI/ML Intelligence Layer

### Goal
Full genuine AI/ML processing pipeline from raw report to classified, geolocated, deduplicated, and verified weather intelligence. Designed for ₹0 deployment (Google Colab free-tier training + Oracle VM Always-Free CPU inference with ONNX/PyTorch and deterministic fallback safety).

### Tasks

1. **Real ML Core Architecture (`backend/ml/`)**
   - `backend/ml/model_registry.py` — Centralized registry with metadata, checksum verification, latency tracking, and status management (`NOT_TRAINED`, `TRAINED`, `LOADED`, `NOT_LOADED`, `ERROR`).
   - `backend/ml/model_loader.py` — Lazy loader supporting ONNX Runtime CPU, PyTorch CPU, and Scikit-Learn with zero crash guarantees.
   - `backend/ml/inference_service.py` — Unified gateway coordinating text classification, embeddings, credibility, and anomaly detection.
   - `backend/ml/text_classifier.py` — Weather event text classification on 7 canonical categories + extensions with softmax distributions.
   - `backend/ml/duplicate_model.py` — 384-dimensional dense semantic embeddings and cosine duplicate evaluation.
   - `backend/ml/credibility_model.py` — Multi-modal credibility & misinformation scoring.
   - `backend/ml/anomaly_model.py` — Isolation Forest / LOF spatiotemporal anomaly detection.
   - `backend/ml/feature_extraction.py` — 16-dimensional tabular/dense feature extractor synthesizing text, spatiotemporal, source trust, weather telemetry, and DWEG topology.
   - `backend/ml/preprocessing.py` — Multilingual text cleaning and token statistics for English, Hindi, and Hinglish.

2. **Google Colab Training Pipeline (`ml_training/`)**
   - `ml_training/SkyPulse_ML_Training.ipynb` — End-to-end training notebook runnable on Google Colab free tier (dataset ingestion, class balancing, fine-tuning, macro F1 evaluation, ONNX CPU export, SHA-256 checksumming, packaging).
   - `ml_training/dataset_loader.py` — Canonical dataset ingestion combining IMD bulletins, data.gov.in records, citizen reports, and historical weather texts.

3. **AI Worker Integration**
   - `backend/workers/ai_pipeline.py` — Integrates `MLInferenceService` with fallback to `FallbackAIProvider` when models are in `NOT_TRAINED` state or low confidence.
   - `backend/ai/event_classifier.py` — Attempts real ML inference before falling back to deterministic heuristic.

4. **NLP extractor & Image Analyzer**
   - `backend/ai/nlp_extractor.py` — Meteorological entity and measurement parser.
   - `backend/ai/image_analyzer.py` — Perceptual hash and media heuristic analyzer.
   - LLM extraction with OpenAI or Ollama (configurable)
   - Fallback to spaCy when LLM unavailable
   - Output: structured extraction result stored in `ai_extraction` JSONB

3. **Event classifier**
   - `backend/ai/event_classifier.py`
   - HuggingFace `zero-shot-classification` pipeline
   - Fallback: keyword rule-based classifier
   - Output: `primary_category`, `sub_category`, `classification_confidence`

4. **Geolocator**
   - `backend/ai/geolocator.py`
   - Nominatim geocoding for India (with local caching in Redis)
   - Indian location dictionary for NLP-extracted location names
   - PostGIS reverse geocode for GPS coordinates → state/district/city
   - Output: `location_point`, `location_state`, `location_district`, `location_city`, `location_confidence`

5. **Image analyzer**
   - `backend/ai/image_analyzer.py`
   - Downloads image from MinIO
   - CLIP zero-shot classification against `WEATHER_EVIDENCE_PROMPTS`
   - Perceptual hash computation
   - Face detection (OpenCV Haar cascade)
   - Face blurring and re-upload if detected
   - Output: `image_analysis` JSONB stored in `media` table

6. **Deduplicator**
   - `backend/ai/deduplicator.py`
   - sentence-transformers embedding generation
   - pgvector similarity search for candidate duplicates
   - Composite scoring (semantic + spatial + temporal + image hash)
   - Cluster assignment or new canonical event creation
   - Updates `weather_report.canonical_event_id`, `weather_event.evidence_count`

7. **Anomaly detector**
   - `backend/ai/anomaly_detector.py`
   - Loads district × category × month baselines from `locations` table (updated from historical data)
   - Z-score computation
   - Updates `weather_event.is_anomalous`, `weather_event.anomaly_z_score`

8. **Embedding model initialization**
   - Download and cache `all-MiniLM-L6-v2` at worker startup
   - Configurable via `EMBEDDING_MODEL` env var

9. **Model caching**
   - Models loaded once at worker startup, not per-record
   - Warm-up ping on startup to verify model works

### Files to Create
```
backend/
  ai/
    __init__.py
    nlp_extractor.py
    event_classifier.py
    geolocator.py
    image_analyzer.py
    deduplicator.py
    anomaly_detector.py
    model_manager.py
  workers/
    ai_pipeline.py
```

### Tests
- `tests/unit/test_nlp_extractor.py` — test extraction on sample texts
- `tests/unit/test_event_classifier.py` — test classification on labeled examples (>85% accuracy on 100 samples)
- `tests/unit/test_deduplicator.py` — test composite scoring with known duplicate/non-duplicate pairs
- `tests/unit/test_geolocator.py` — test known Indian city names resolve correctly

### Completion Criteria
- A report entering `skypulse.pending_ai` exits with all AI fields populated within 10 seconds
- Classification accuracy >85% on 100-sample labeled test set
- Duplicate detection correctly clusters 90%+ of simulated duplicate pairs
- LLM fallback to spaCy works when `LLM_PROVIDER=disabled`
- Image face blurring verified on test image with faces

---

## Phase 6 — Verification Engine

### Goal
Evidence-based verification with explainable results for all canonical events.

### Tasks

1. **Verification worker**
   - `backend/workers/verification_worker.py`
   - Triggered after deduplication step (via Kafka `skypulse.pending_verification` topic)
   - Orchestrates all verification signal collectors

2. **Official API signal collector**
   - `backend/ai/verification/official_api_signal.py`
   - Queries OpenWeatherMap for conditions at event location + time
   - Returns match score: 1.0 (matches), 0.5 (similar), 0.0 (no data), -1.0 (contradicts)

3. **Nearby reports signal collector**
   - `backend/ai/verification/nearby_reports_signal.py`
   - PostGIS query: VERIFIED/LIKELY events within 30km, 3 hours
   - Returns count-based score

4. **Source trust signal collector**
   - `backend/ai/verification/source_trust_signal.py`
   - Reads trust score from `sources` table

5. **Image evidence signal collector**
   - `backend/ai/verification/image_evidence_signal.py`
   - Reads `image_analysis.supports_claimed_event` from `media` table

6. **Temporal consistency signal collector**
   - `backend/ai/verification/temporal_signal.py`
   - Checks if event type is plausible at time of day and season for location

7. **Historical baseline signal collector**
   - `backend/ai/verification/historical_signal.py`
   - Checks historical frequency of event type at location and month

8. **Verification scorer**
   - `backend/ai/verification/scorer.py`
   - Assembles all signals, applies weights from AI_ML.md
   - Produces `VerificationStatus` and `confidence_score`

9. **Explanation generator**
   - `backend/ai/verification/explainer.py`
   - LLM prompt for narrative explanation (template fallback)
   - Stores in `verification_results.explanation_text`

10. **Source trust updater**
    - `backend/ai/verification/trust_updater.py`
    - Updates `sources.trust_score` based on verification outcome
    - Inserts row in `source_reputation_history`

### Files to Create
```
backend/
  ai/
    verification/
      __init__.py
      official_api_signal.py
      nearby_reports_signal.py
      source_trust_signal.py
      image_evidence_signal.py
      temporal_signal.py
      historical_signal.py
      scorer.py
      explainer.py
      trust_updater.py
  workers/
    verification_worker.py
```

### Tests
- `tests/unit/test_verification_scorer.py` — test scoring with known signal combinations
- `tests/unit/test_trust_updater.py` — test trust score update formula
- `tests/integration/test_verification_flow.py` — end-to-end from report to verification result

### Completion Criteria
- Every canonical event has a `verification_results` row after processing
- Verification result includes `explanation_text` (non-empty)
- `verification_evidence` rows created for each signal
- Source trust score updated after each verification outcome
- Manual override via `PUT /api/v1/verification/{event_id}` persists and is logged in audit

---

## Phase 7 — Real-time Processing

### Goal
WebSocket-driven real-time updates from backend to frontend.

### Tasks

1. **WebSocket manager**
   - `backend/app/core/websocket_manager.py`
   - Manages active WebSocket connections
   - Supports broadcast and targeted (user-specific) messages
   - Uses Redis pub/sub as the broadcast channel (so multiple API instances share state)

2. **WebSocket endpoint**
   - `backend/app/api/ws.py`
   - `WS /ws/events` — authenticated via `?token=` query param
   - On connect: send last 10 active events as initial state
   - Subscribe to Redis channel for incoming messages
   - Handle PING/PONG heartbeat

3. **Event publisher**
   - `backend/workers/event_publisher.py`
   - Consumes `skypulse.events` Kafka topic
   - Publishes to Redis pub/sub channel `skypulse:realtime`
   - Includes: `EVENT_PUBLISHED`, `EVENT_UPDATED`, `DWEG_PROPAGATION_ALERT`, `SYSTEM_NOTIFICATION`

4. **AI pipeline → event publish hook**
   - After processing completes successfully: publish `EVENT_PUBLISHED` to `skypulse.events`
   - After verification update: publish `EVENT_UPDATED`

5. **Notification service**
   - `backend/app/services/notification_service.py`
   - Creates `notifications` rows for relevant users
   - Publishes via WebSocket for real-time delivery

### Files to Create
```
backend/
  app/
    core/
      websocket_manager.py
    api/
      ws.py
  workers/
    event_publisher.py
  app/
    services/
      notification_service.py
```

### Tests
- `tests/integration/test_websocket.py` — connect to WS, verify event appears within 10 seconds of report submission

### Completion Criteria
- Browser receives `EVENT_PUBLISHED` message within 10 seconds of report ingestion
- Multiple browser tabs all receive the same real-time updates
- Connection loss and reconnection handled gracefully
- Notifications appear in topbar for relevant users

---

## Phase 8 — Dashboard Frontend

### Goal
Complete public dashboard, event detail, analytics, and citizen report interface.

### Tasks

1. **API client**
   - `frontend/src/utils/api.ts` — Axios-based API client with auth header injection and error handling

2. **WebSocket client**
   - `frontend/src/hooks/useWebSocket.ts` — Socket.io client with reconnect, event handlers

3. **Zustand store**
   - `frontend/src/store/` — `eventsStore`, `filtersStore`, `authStore`, `notificationsStore`

4. **Design system components**
   - `frontend/src/components/ui/` — Badge, Chip, Card, Button, Input, Select, DatePicker, Modal, Toast, Spinner, Skeleton

5. **Map component**
   - `frontend/src/components/map/SkyPulseMap.tsx` — MapLibre GL, India bounds, event markers, clusters, heatmap layer
   - `frontend/src/components/map/EventMarker.tsx` — Custom hexagon marker SVG
   - `frontend/src/components/map/HeatmapLayer.tsx`

6. **Filter panel**
   - `frontend/src/components/filters/FilterPanel.tsx`
   - All filter controls from UI_UX.md
   - URL query param sync

7. **Event feed**
   - `frontend/src/components/events/EventFeed.tsx` — Right-side real-time feed

8. **Public Dashboard page**
   - `frontend/src/pages/Dashboard.tsx` — Map + sidebar stats + event feed

9. **Event detail page**
   - `frontend/src/pages/EventDetail.tsx` — All tabs from UI_UX.md

10. **Analytics page**
    - `frontend/src/pages/Analytics.tsx` — All charts from UI_UX.md

11. **Citizen report interface**
    - `frontend/src/pages/SubmitReport.tsx` — Multi-step form
    - `frontend/src/hooks/useOfflineQueue.ts` — IndexedDB + service worker
    - `public/sw.js` — Service worker for offline support

12. **Auth pages**
    - `frontend/src/pages/Login.tsx`
    - `frontend/src/pages/Register.tsx`

13. **Routing**
    - `frontend/src/App.tsx` — React Router v6 with protected routes

### Files to Create
```
frontend/src/
  utils/
    api.ts
    formatters.ts
  hooks/
    useWebSocket.ts
    useOfflineQueue.ts
    useMapEvents.ts
  store/
    eventsStore.ts
    filtersStore.ts
    authStore.ts
    notificationsStore.ts
  components/
    ui/ (all design system components)
    map/
      SkyPulseMap.tsx
      EventMarker.tsx
      HeatmapLayer.tsx
    filters/
      FilterPanel.tsx
    events/
      EventFeed.tsx
      EventCard.tsx
    charts/
      CategoryDonut.tsx
      EventTimeline.tsx
      StatCard.tsx
  pages/
    Dashboard.tsx
    EventDetail.tsx
    Analytics.tsx
    SubmitReport.tsx
    Login.tsx
    Register.tsx
  App.tsx
  types/
    api.ts
    map.ts
```

### Tests
- `frontend/src/__tests__/EventCard.test.tsx`
- `frontend/src/__tests__/FilterPanel.test.tsx`
- `frontend/src/__tests__/api.test.ts`

### Completion Criteria
- Map loads with event markers in under 3 seconds
- New events appear on map and in feed within 10 seconds
- All filters work and update map + feed correctly
- Citizen report submits and confirmation appears
- Offline queue works: report queued when offline, submitted on reconnect
- Event detail page shows all tabs with real data

---

## Phase 9 — Analyst Interface + Admin Panel

### Goal
Full analyst triage workflow and admin operations.

### Tasks

1. **Analyst layout**
   - `frontend/src/layouts/AnalystLayout.tsx` — Extends global layout with analyst sidebar items

2. **Verification queue page**
   - `frontend/src/pages/analyst/VerificationQueue.tsx`
   - Sortable, filterable queue
   - Quick verify/reject actions

3. **Analyst event detail**
   - `frontend/src/pages/analyst/AnalystEventDetail.tsx`
   - Extends public event detail with override form, duplicate cluster panel

4. **Duplicate cluster manager**
   - `frontend/src/components/analyst/DuplicateClusterPanel.tsx`
   - Checkboxes, split/merge actions

5. **Admin layout + routing**
   - `frontend/src/layouts/AdminLayout.tsx`

6. **System health page**
   - `frontend/src/pages/admin/SystemHealth.tsx`
   - Auto-refreshes every 30 seconds

7. **Connector management page**
   - `frontend/src/pages/admin/ConnectorManagement.tsx`
   - Add/edit connector modal

8. **User management page**
   - `frontend/src/pages/admin/UserManagement.tsx`

9. **Audit log page**
   - `frontend/src/pages/admin/AuditLog.tsx`
   - Searchable, filterable table

10. **Flagged reports page**
    - `frontend/src/pages/admin/FlaggedReports.tsx`

### Completion Criteria
- Analyst can view queue, verify a report, and see audit trail entry created
- Admin can enable/disable a connector and observe health status change
- Duplicate cluster split/merge works end-to-end
- Audit log shows all operations performed during testing

---

## Phase 10 — DWEG Signature Innovation

### Goal
Fully implemented Dynamic Weather Evidence Graph with UI.

### Tasks

1. **Neo4j integration**
   - `backend/app/db/neo4j_session.py` — Neo4j async driver setup

2. **DWEG graph service**
   - `backend/app/services/dweg_service.py`
   - `build_event_graph()` — creates/updates Neo4j nodes and edges for an event
   - `compute_confidence_field()` — GeoJSON from evidence report locations
   - `detect_propagation()` — Cypher query from AI_ML.md Section 9.3
   - `get_propagation_timeline()` — ordered propagation steps
   - `generate_evidence_chain()` — LLM narrative or template fallback

3. **DWEG worker**
   - `backend/workers/dweg_worker.py`
   - Consumes `skypulse.events` topic
   - Calls `dweg_service.build_event_graph()` after each new event/report
   - Runs propagation detection
   - Fires propagation alert via notification service if detected

4. **DWEG API endpoints** (complete Phase 3 placeholders)
   - `backend/app/api/dweg.py` — all endpoints from API_SPECIFICATION.md DWEG section

5. **Spatial adjacency pre-computation**
   - `scripts/compute_adjacency.py` — PostGIS ST_Touches to find adjacent districts
   - Stores result in `locations.adjacent_location_ids`
   - Loads adjacency into Neo4j as `SPATIALLY_ADJACENT` edges on startup

6. **DWEG frontend — Graph visualization**
   - `frontend/src/components/dweg/EvidenceGraph.tsx`
   - D3 force-directed graph
   - Node types: different shapes/colors per type
   - Edge labels on hover

7. **DWEG frontend — Confidence Field Map**
   - `frontend/src/components/dweg/ConfidenceFieldLayer.tsx`
   - MapLibre heatmap layer using GeoJSON from API

8. **DWEG frontend — Propagation Timeline**
   - `frontend/src/components/dweg/PropagationTimeline.tsx`
   - Scrubber + play button
   - Animates markers appearing on map

9. **DWEG frontend — Evidence Chain**
   - `frontend/src/components/dweg/EvidenceChainPanel.tsx`
   - Narrative text
   - Structured evidence steps

10. **DWEG page**
    - `frontend/src/pages/DWEGView.tsx`
    - Integrates all DWEG components in layout from UI_UX.md

11. **Propagation alert WebSocket handler**
    - Extend `useWebSocket.ts` to handle `DWEG_PROPAGATION_ALERT` → show toast

### Files to Create
```
backend/
  app/
    db/
      neo4j_session.py
    services/
      dweg_service.py
    api/
      dweg.py (complete implementation)
  workers/
    dweg_worker.py
scripts/
  compute_adjacency.py
frontend/src/
  components/
    dweg/
      EvidenceGraph.tsx
      ConfidenceFieldLayer.tsx
      PropagationTimeline.tsx
      EvidenceChainPanel.tsx
  pages/
    DWEGView.tsx
```

### Tests
- `tests/unit/test_dweg_service.py` — test propagation detection with known graph
- `tests/integration/test_dweg_api.py` — test all DWEG endpoints

### Completion Criteria
- Graph builds within 15 seconds of new corroborating report
- Propagation alert fires within 30 seconds of spatial expansion detection
- Confidence field renders on map with real event data
- Evidence chain narrative generated for events with 3+ reports
- Propagation timeline animation plays correctly

---

## Phase 11 — Testing

### Goal
Test coverage sufficient for production confidence.

### Tasks

1. **Backend unit tests (pytest)**
   - AI components: classifier, extractor, deduplicator, verifier
   - Services: report service, event service, DWEG service
   - Core: JWT, rate limiting, audit logging
   - Target: >80% coverage on `ai/` and `services/` directories

2. **Backend integration tests**
   - Full API endpoint tests with real database
   - Real-time pipeline test (submit report → WebSocket event)
   - Connector health monitor
   - Verification end-to-end

3. **Frontend unit tests (Vitest)**
   - Components: FilterPanel, EventCard, EventFeed, StatCard
   - Store logic
   - API client mock tests

4. **E2E tests (Playwright)**
   - `tests/e2e/public_dashboard.spec.ts` — map loads, events visible, filter works
   - `tests/e2e/citizen_report.spec.ts` — submit report end-to-end
   - `tests/e2e/analyst_verify.spec.ts` — analyst verifies a report
   - `tests/e2e/admin_connector.spec.ts` — admin disables/enables connector

5. **Performance test**
   - `tests/perf/load_test.py` — Locust test simulating 100 concurrent users
   - Verify API p95 < 500ms under load

6. **Demo mode test**
   - `tests/integration/test_demo_mode.py` — full pipeline with demo connector, no external APIs

### Files to Create
```
backend/tests/
  unit/
    test_nlp_extractor.py
    test_event_classifier.py
    test_deduplicator.py
    test_verification_scorer.py
    test_dweg_service.py
    test_trust_updater.py
  integration/
    test_auth_api.py
    test_reports_api.py
    test_events_api.py
    test_analytics_api.py
    test_verification_flow.py
    test_websocket.py
    test_dweg_api.py
    test_demo_mode.py
frontend/src/__tests__/
  EventCard.test.tsx
  FilterPanel.test.tsx
  api.test.ts
tests/e2e/
  public_dashboard.spec.ts
  citizen_report.spec.ts
  analyst_verify.spec.ts
  admin_connector.spec.ts
tests/perf/
  load_test.py
```

### Completion Criteria
- All unit tests pass
- All integration tests pass against running stack
- E2E tests pass against full docker-compose stack
- No critical test failures
- Performance test: p95 API < 500ms at 100 concurrent users

---

## Phase 12 — Deployment

### Goal
Production-ready deployment configuration.

### Tasks

1. **Production Docker images**
   - Multi-stage Dockerfiles for backend and frontend
   - Non-root user in all containers
   - `.dockerignore` files

2. **Environment config for production**
   - `docker-compose.prod.yml` — production override
   - Remove debug flags, enable HTTPS, set `APP_ENV=production`

3. **Nginx production config**
   - TLS configuration with Let's Encrypt Certbot
   - Security headers: HSTS, X-Frame-Options, CSP
   - Gzip compression
   - Rate limiting at Nginx level

4. **Database backups**
   - `infra/scripts/pg_backup.sh` — Daily PostgreSQL dump to MinIO
   - Cron job in container

5. **Prometheus metrics**
   - `backend/app/core/metrics.py` — Prometheus counters for ingestion rate, processing latency, error rate
   - Expose `/metrics` endpoint
   - `infra/prometheus/prometheus.yml` — scrape config

6. **Grafana dashboards**
   - `infra/grafana/dashboards/skypulse_ops.json` — operational dashboard
   - Import via Grafana provisioning

7. **Demo mode setup**
   - `scripts/seed_demo.py` — comprehensive demo seed: 50 historical events across India, 200 reports, all event types
   - `scripts/generate_stream.py` — continuous synthetic event stream with configurable rate and burst
   - Demo data clearly marked in DB and UI

8. **Health check probes**
   - All services expose `/health` endpoint
   - Docker `HEALTHCHECK` in all Dockerfiles

9. **Log aggregation**
   - All services log structured JSON to stdout
   - Docker logging driver: `json-file` with rotation

10. **Startup automation**
    - `scripts/start.sh` — runs migrations, creates partitions, seeds demo data if `DEMO_MODE=true`, starts all services

### Files to Create
```
backend/
  Dockerfile
  app/
    core/
      metrics.py
frontend/
  Dockerfile
infra/
  nginx/
    nginx.prod.conf
  prometheus/
    prometheus.yml
  grafana/
    dashboards/
      skypulse_ops.json
    provisioning/
      datasources.yml
      dashboards.yml
  scripts/
    pg_backup.sh
docker-compose.prod.yml
scripts/
  seed_demo.py
  generate_stream.py
  start.sh
```

### Completion Criteria
- Full stack starts with `docker compose -f docker-compose.demo.yml up -d`
- Demo seed completes in under 60 seconds
- Demo events visible on map immediately
- Synthetic event stream produces events every 10 seconds
- Prometheus metrics visible in Grafana dashboard
- `GET /health` returns 200 for all services
- No demo mode requires any external API key

---

## Quick Reference — File Map

### Backend & ML Key Files

| File | Purpose |
|---|---|
| `app/main.py` | FastAPI application entry point |
| `app/core/config.py` | All env var config |
| `app/core/security.py` | JWT + password hashing |
| `app/core/dependencies.py` | Auth + role dependencies |
| `app/db/session.py` | Async DB session factory (`AsyncSessionLocal`) |
| `app/api/v1/connectors.py` | Social & Web Intelligence Connector API routes |
| `backend/connectors/social_web_connector.py` | SocialWebConnector with SocialAPI, RSSAtom, PublicWeb, PublicJSON adapters |
| `backend/ml/schemas.py` | Pydantic contracts for TrainingRecord, Manifest, ReadinessReport |
| `backend/ml/model_registry.py` | Self-hosted model lifecycle, discovery, and checksum verification |
| `backend/ml/inference_service.py` | High-performance ONNX CPU inference service |
| `ml_training/build_dataset.py` | Master dataset builder CLI & orchestrator |
| `ml_training/era5_adapter.py` | Copernicus CDS historical reanalysis acquisition & weak labels |
| `ml_training/quality.py` | Physical bounds validation & unit normalization engine |
| `ml_training/labeling.py` | Conservative meteorological labeling & conflict resolution engine |
| `ml_training/alignment.py` | Spatiotemporal bucket alignment & ERA5 feature joiner |
| `ml_training/splitter.py` | Event-clustered chronological 70/15/15 dataset splitter |
| `ml_training/readiness.py` | Training readiness evaluation engine (`DatasetReadinessReport`) |
| `ml_training/SkyPulse_ML_Training.ipynb` | Google Colab training notebook for Step 7 |

### Frontend Key Files

| File | Purpose |
|---|---|
| `src/App.tsx` | Router + layout |
| `src/index.css` | Design system CSS |
| `src/utils/api.ts` | API client & socialWebAPI client |
| `src/hooks/useWebSocket.ts` | Real-time connection |
| `src/store/eventsStore.ts` | Events global state |
| `src/components/map/SkyPulseMap.tsx` | Main Google Maps component |
| `src/pages/Dashboard.tsx` | Public dashboard |
| `src/pages/EventDetail.tsx` | Event detail |
| `src/pages/DWEGView.tsx` | DWEG innovation UI |
| `src/pages/admin/ConnectorManagement.tsx` | Connector Management & Social/Web smoke testing |

