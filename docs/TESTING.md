# SkyPulse Testing & Quality Assurance Suite

SkyPulse includes an automated testing framework spanning unit, integration, visual regression, spatial validation, and synchronicity tests.

---

## 1. Test Architecture & Coverage

```
SkyPulse Testing Matrix
│
├── Frontend Tests (Vitest + React Testing Library)
│   ├── Component Tests (EventCard, KPIBar, Badges, Metrics, Drawers)
│   ├── Page Tests (Dashboard, LiveMap, Events, Reports, Analytics, DWEGView)
│   ├── State Store Tests (eventsStore, filtersStore, authStore)
│   ├── Integration Tests (WebSocketClient, API Client, SynchronizationAudit)
│   └── Synthetic Telemetry Tests (DemoDataLayer: Rothfusz Heat Index, WSI Index, RNG Determinism)
│
└── Backend Tests (Pytest + Asyncio + FastAPI TestClient)
    ├── Connector Tests (OpenMeteo, DataGov, NewsWebsite, SocialWeb)
    ├── AI/ML & Provider Tests (GroqProvider, FallbackProvider, ConfidenceEngine)
    ├── Deduplication & Normalization Tests (Spatial/Temporal Clustering)
    ├── API Route Tests (/events, /map, /metrics, /sources, /admin)
    └── Security & Sanity Tests (Secret Redaction, Token Verification)
```

---

## 2. Frontend Test Suite

### Running Frontend Tests
```bash
cd frontend
npm test
```

### Key Verified Frontend Test Suites (108 Tests across 22 Files):
1. **`DemoDataLayer.test.ts`**: Verifies meteorological formulas (NOAA Rothfusz Heat Index equation, SkyPulse Weather Severity Index), PRNG determinism, 240+ station mesh generation, and non-destructive additive merging.
2. **`SynchronizationAudit.test.tsx`**: Verifies that counts across KPI bar, Dashboard cards, and geospatial markers reconcile without discrepancies.
3. **`EventCard.test.tsx` / `EventDetailDrawer.test.tsx`**: Verifies severity styling, telemetry panel rendering, verification status badges, and dossier drawers.
4. **`WebSocketClient.test.ts`**: Verifies WebSocket auto-reconnect, exponential backoff, heartbeat pings, and delta-sync merges.
5. **`GoogleWeatherMap.test.tsx`**: Verifies marker clustering, coordinate sanitization, and map click callbacks.

---

## 3. Backend Test Suite

### Running Backend Tests
```bash
cd backend
pytest tests/ -v
```

### Key Backend Test Suites:
1. **`test_openmeteo_connector.py`**: Verifies HTTP polling, schema parsing, and weather code mapping.
2. **`test_groq_llm_integration.py`**: Verifies Groq API client, prompt formatting, payload parsing, and fallback triggers when upstream API is unavailable.
3. **`test_deduplicator.py`**: Tests spatial bounding box and Haversine distance calculations for multi-source report clustering.
4. **`test_security_redaction.py`**: Verifies regex redactors for credentials, auth tokens, and sensitive headers.

---

## 4. Continuous Integration Checks

Every pull request must pass:
1. `npm test` (0 failures across all frontend test suites)
2. `npm run build` (TypeScript compilation and Vite asset bundling)
3. `pytest` (Backend unit tests)
