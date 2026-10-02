# SkyPulse — System Architecture

**Version:** 1.0  
**Status:** Implementation-Ready

---

## 1. Architecture Principles

1. **Connector-first:** Every data source is a replaceable connector implementing a common interface
2. **Event-driven core:** Data flows through Kafka; no direct DB writes from connectors
3. **AI as middleware:** AI pipeline is a processing stage, not a feature — outputs flow into the same storage layer as manual data
4. **Explainability by design:** Every AI decision is stored as structured evidence, not a black box score
5. **Demo-safe:** The entire platform operates in demo mode with zero external dependencies
6. **No over-engineering:** Technologies are chosen for what the prototype needs today, with clear scaling paths

---

## 2. High-Level Architecture

```mermaid
graph TD
    subgraph SOURCES["Data Sources"]
        S1[Weather APIs<br/>OpenWeatherMap, IMD]
        S2[Government Portals<br/>IMD Official & data.gov.in OGD]
        S3[Public Datasets<br/>Historical Baselines]
        S4[RSS/Atom Feeds<br/>News Weather Feeds]
        S5[Citizen Reports<br/>Platform Submission]
        S6[Demo Connector<br/>Synthetic Generator]
    end

    subgraph CONNECTORS["Connector Layer (Python Workers)"]
        C1[WeatherAPIConnector]
        C2[IMDConnector]
        C3[DataGovConnector]
        C4[DatasetConnector]
        C5[FeedConnector]
        C6[CitizenReportConnector]
        C7[DemoConnector]
    end

    subgraph BROKER["Message Broker"]
        K1[Kafka/Redpanda<br/>Topic: skypulse.raw]
    end

    subgraph AIML["Real AI/ML Processing Pipeline (backend/ml)"]
        A0[ML Inference Service & Registry]
        A1[Event Text Classifier ONNX/PyTorch]
        A2[Semantic Embedding Model MiniLM]
        A3[Multi-Modal Feature Extractor 16-dim]
        A4[Credibility & Misinformation Model]
        A5[Spatiotemporal Anomaly Detector]
        A6[Multi-Level Deduplicator & Verifier]
        A7[DWEG Knowledge Graph Updater]
    end

    subgraph STORAGE["Storage Layer"]
        DB[(PostgreSQL + PostGIS)]
        RD[(Redis Cache)]
        OS[(OpenSearch)]
        MN[(MinIO / S3)]
        N4[(Neo4j DWEG)]
    end

    subgraph API["API Layer"]
        FA[FastAPI]
        WS[WebSocket Manager]
    end

    subgraph FRONT["Frontend"]
        FE[React Dashboard]
        AN[Analyst Interface]
        ADM[Admin Panel]
        CIT[Citizen Interface]
    end

    S1 --> C1
    S2 --> C2
    S3 --> C3
    S4 --> C4
    S5 --> C5

    C1 & C2 & C3 & C4 & C5 --> K1

    K1 --> A1 --> A2 --> A3 --> A4 --> A5 --> A6 --> A7

    A7 --> DB & OS & N4
    A6 --> RD
    A4 --> MN

    DB & RD & OS & N4 --> FA
    FA --> WS
    FA --> FE & AN & ADM & CIT
    WS --> FE & AN
```

---

## 3. Technology Stack — Justified

| Technology | Role | Why | Prototype Required? | Scaling Path |
|---|---|---|---|---|
| **FastAPI** | Backend REST + WebSocket API | Async Python, excellent performance, auto-OpenAPI docs | Yes | Add Gunicorn workers; deploy behind Nginx |
| **PostgreSQL 16 + PostGIS 3.4** | Primary relational + spatial database | ACID compliance, mature spatial support, JSON columns for flexible metadata | Yes | Read replicas, table partitioning, PgBouncer |
| **Redis 7** | Cache, session store, pub/sub for real-time | Microsecond reads; pub/sub for WebSocket fan-out | Yes | Redis Cluster for horizontal scale |
| **Kafka / Redpanda** | Message broker | Durable event log; decouples connectors from processors; enables replay | Yes (Redpanda single-node for prototype) | Scale partitions + consumer groups |
| **MinIO** | Object storage for media | S3-compatible; self-hosted for prototype | Yes | Replace with AWS S3 / GCS in production |
| **OpenSearch 2.x** | Full-text search, analytics aggregations | Better suited to weather text search than Postgres full-text at scale | Yes | OpenSearch cluster (3 nodes) for production |
| **Neo4j 5** | DWEG graph database | Native graph traversal for evidence chain and propagation queries | Yes (community edition) | Neo4j Aura managed in production |
| **React 18 + TypeScript** | Frontend | Component ecosystem; strong typing; large talent pool | Yes | CDN static hosting |
| **MapLibre GL JS** | Interactive map rendering | Open-source (Mapbox fork); supports custom tile layers and vector overlays | Yes | Same in production |
| **Redpanda** | Kafka-compatible broker (prototype) | Single binary, no ZooKeeper, faster startup for dev/demo | Yes | Replace with managed Kafka for production |
| **Docker + Compose** | Containerization | Consistent environments; single-command setup | Yes | Kubernetes with Helm in production |
| **Prometheus + Grafana** | Metrics and monitoring | Industry standard; easy Docker integration | Optional for prototype | Same in production |
| **Nginx** | Reverse proxy + static serving | Route /api to FastAPI, / to React build | Yes | Same in production |

**Not used and why:**
- **Apache Spark:** Not needed for prototype volumes. Batch reprocessing can run as Python scripts. Add if ingestion exceeds 1M records/day.
- **Apache Flink:** Real-time stream processing is handled by Python consumer workers. Add for complex stream joins at scale.
- **TailwindCSS:** Vanilla CSS used per project guidelines.

---

## 4. Data Flow Diagram

```mermaid
sequenceDiagram
    participant SRC as Data Source
    participant CON as Connector
    participant KFK as Kafka
    participant WRK as AI Worker
    participant PG as PostgreSQL
    participant OS as OpenSearch
    participant N4 as Neo4j
    participant API as FastAPI
    participant WS as WebSocket
    participant FE as Browser

    SRC->>CON: Raw data (poll/push)
    CON->>KFK: Publish raw record (skypulse.raw)
    KFK->>WRK: Consume record
    WRK->>WRK: NLP Extract + Classify
    WRK->>WRK: Geolocate
    WRK->>WRK: Image Analysis (async)
    WRK->>WRK: Deduplicate
    WRK->>WRK: Verify
    WRK->>PG: Write weather_report + event + verification
    WRK->>OS: Index for search
    WRK->>N4: Update DWEG graph
    WRK->>KFK: Publish to skypulse.events
    API->>KFK: Consume skypulse.events
    API->>WS: Push event update
    WS->>FE: WebSocket message (event_update)
    FE->>FE: Update map + analytics
```

---

## 5. Real-time Pipeline

```mermaid
flowchart LR
    subgraph INGEST["Ingestion (< 1s)"]
        CON[Connector] -->|publish| RAW[skypulse.raw topic]
    end

    subgraph PROCESS["AI Processing (2-8s)"]
        RAW -->|consume| NLP[NLP + Classify]
        NLP --> GEO[Geolocate]
        GEO --> IMG[Image Analyze]
        IMG --> DEDUP[Deduplicate]
        DEDUP --> VER[Verify]
    end

    subgraph STORE["Store + Index (< 1s)"]
        VER --> PG[(PostgreSQL)]
        VER --> OS[(OpenSearch)]
        VER --> N4[(Neo4j)]
    end

    subgraph PUSH["Push (< 1s)"]
        PG -->|trigger| EVT[skypulse.events topic]
        EVT -->|consume| WSM[WebSocket Manager]
        WSM -->|broadcast| FE[Connected Clients]
    end
```

**End-to-end p95 target:** < 10 seconds from connector receipt to browser render.

---

## 6. AI / Verification Pipeline

```mermaid
flowchart TD
    RAW[Raw Report from Kafka] --> NLP

    subgraph EXTRACT["Extraction Layer"]
        NLP[spaCy NER + LLM Extract]
        NLP --> LOC[Location Extraction]
        NLP --> EVT[Event Classification]
        NLP --> SEV[Severity Estimation]
        NLP --> TIME[Time Extraction]
    end

    subgraph GEO["Geolocation"]
        LOC --> GC[Geocoder]
        GC --> COORD[lat/lon + state/district]
    end

    subgraph IMAGE["Image Analysis"]
        IMG[Image from MinIO] --> CV[OpenCV + CLIP]
        CV --> VIS[Visual Evidence Label]
    end

    subgraph DEDUP["Deduplication"]
        COORD & EVT & TIME --> EMB[Embedding Similarity]
        EMB & VIS --> CLUSTER[Cluster Assignment]
        CLUSTER --> CANON[Canonical Event Update]
    end

    subgraph VERIFY["Verification Engine"]
        CANON --> OFCL[Official API Check]
        CANON --> NEAR[Nearby Reports Check]
        CANON --> TRUST[Source Trust Score]
        CANON --> HIST[Historical Baseline]
        OFCL & NEAR & TRUST & HIST & VIS --> SCORE[Confidence Score]
        SCORE --> STATUS[Verification Status]
        STATUS --> EXPLAIN[Explanation Generator]
    end

    subgraph DWEG["DWEG Update"]
        EXPLAIN --> GRAPH[Neo4j Graph Update]
        GRAPH --> PROP[Propagation Check]
        PROP --> ALERT[Propagation Alert?]
    end
```

---

## 7. Connector Architecture

All connectors extend `BaseConnector`:

```
BaseConnector
├── poll() → AsyncIterator[RawRecord]
├── parse(raw) → NormalizedRecord
├── health_check() → ConnectorHealth
└── metadata() → ConnectorMetadata

Implementations:
├── WeatherAPIConnector (OpenWeatherMap, WeatherAPI)
├── IMDConnector & IMDHistoricalAdapter (IMD Official API & Gridded NetCDF)
├── DataGovConnector (data.gov.in Open Government Data Platform)
├── RSSFeedConnector (news weather feeds)
├── SocialWebConnector (Social & Web Weather Intelligence)
│   ├── SocialAPIAdapter (Authorized social media APIs with Bearer/API-key auth)
│   ├── RSSAtomAdapter (RSS 2.0 & Atom XML syndication alerts)
│   ├── PublicWebAdapter (Controlled public weather webpages, strict limits)
│   └── PublicJSONAdapter (Configurable JSON REST endpoints)
├── CitizenReportConnector (internal API)
└── DemoConnector (synthetic generator)
```

> **Important Compliance & Access Notice:**  
> Social-media ingestion requires an authorized API/feed or permitted public source. SkyPulse does not bypass platform access controls, solve CAPTCHAs, or implement stealth scraping.

Each connector runs as an independent Python worker process in its own Docker container, publishing to `skypulse.raw` Kafka topic. This allows:
- Independent failure isolation
- Independent scaling
- Hot-swapping connectors without restarting the platform

---

## 8. Deployment Architecture

```mermaid
graph TB
    subgraph CLIENT["Client"]
        BROWSER[Browser]
    end

    subgraph EDGE["Edge / Proxy"]
        NGINX[Nginx<br/>TLS Termination + Routing]
    end

    subgraph APP["Application Layer"]
        FE_STATIC[React Static Build<br/>served by Nginx]
        API[FastAPI + Uvicorn<br/>Multiple Workers]
    end

    subgraph WORKERS["Worker Layer"]
        AI_WRK[AI Processing Workers<br/>N instances]
        CON_WRK[Connector Workers<br/>1 per connector]
        DEMO_WRK[Demo Stream Generator<br/>demo mode only]
    end

    subgraph BROKER["Message Broker"]
        KAFKA[Redpanda / Kafka<br/>skypulse.raw / .processed / .events]
    end

    subgraph DATA["Data Layer"]
        PG[(PostgreSQL + PostGIS)]
        RD[(Redis)]
        OS[(OpenSearch)]
        MN[(MinIO)]
        N4[(Neo4j)]
    end

    subgraph OBS["Observability"]
        PROM[Prometheus]
        GRAF[Grafana]
    end

    BROWSER -->|HTTPS| NGINX
    NGINX -->|/api| API
    NGINX -->|/| FE_STATIC
    API -->|read/write| PG & RD & OS & N4 & MN
    API -->|pub/sub| RD
    API -->|consume| KAFKA
    AI_WRK -->|consume/produce| KAFKA
    AI_WRK -->|write| PG & OS & N4 & MN
    CON_WRK & DEMO_WRK -->|publish| KAFKA
    API & AI_WRK & CON_WRK --> PROM
    PROM --> GRAF
```

### Container Services (docker-compose)

| Service | Image | Purpose |
|---|---|---|
| `postgres` | postgres:16-alpine + postgis | Primary DB |
| `redis` | redis:7-alpine | Cache + pub/sub |
| `redpanda` | redpandadata/redpanda | Kafka-compatible broker |
| `minio` | minio/minio | Object storage |
| `opensearch` | opensearchproject/opensearch:2 | Search engine |
| `neo4j` | neo4j:5-community | DWEG graph store |
| `backend` | skypulse/backend | FastAPI application |
| `ai-worker` | skypulse/ai-worker | AI processing workers (scalable) |
| `connector-weather` | skypulse/connectors | Weather API connector |
| `connector-demo` | skypulse/connectors | Demo synthetic connector |
| `frontend` | skypulse/frontend | React static build |
| `nginx` | nginx:alpine | Reverse proxy |
| `prometheus` | prom/prometheus | Metrics collection |
| `grafana` | grafana/grafana | Metrics visualization |

---

## 9. Security Architecture

- **Authentication:** JWT Bearer tokens, issued on login, validated on every protected endpoint
- **Authorization:** Role-based (PUBLIC, CITIZEN, ANALYST, ADMIN, GOVERNMENT) enforced at FastAPI dependency layer
- **HTTPS:** Nginx terminates TLS in production; all inter-service communication inside Docker network
- **Rate limiting:** Redis-backed rate limiting at Nginx and FastAPI layers
- **Secret management:** Environment variables; no secrets in code or images
- **Media security:** Uploads go to MinIO; backend streams to client — no direct public URLs for citizen uploads
- **SQL injection:** SQLAlchemy ORM with parameterized queries throughout
- **XSS:** React JSX prevents by default; API outputs are JSON

---

## 10. Observability

| Signal | Tool | What is monitored |
|---|---|---|
| Metrics | Prometheus + Grafana | Ingestion rate, processing latency, queue depth, error rate, API response times |
| Logs | Structured JSON logs (stdout) | All services log to stdout; collected by Docker logging driver |
| Health | FastAPI `/health` endpoints | DB connectivity, Kafka connectivity, AI model availability |
| Alerts | Grafana alerting | Connector down, queue depth > threshold, error rate spike |

---

## 11. Scalability Strategy

| Component | Prototype | Production Scale |
|---|---|---|
| Connectors | 1 process per connector | Multiple instances behind Kafka consumer group |
| AI Workers | 2–3 instances | N instances based on Kafka consumer lag |
| FastAPI | 1 server, 4 workers | Multiple containers behind load balancer |
| PostgreSQL | Single instance | Read replicas + connection pooler (PgBouncer) |
| Kafka | Single-node Redpanda | Multi-broker Kafka cluster (MSK / Confluent) |
| OpenSearch | Single node | 3-node cluster with dedicated data/master nodes |
| Neo4j | Community single instance | Neo4j Aura Enterprise (managed) |
