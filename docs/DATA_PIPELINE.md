# SkyPulse Data Ingestion & Processing Pipeline

## 1. Pipeline Overview

The SkyPulse data pipeline ingests heterogeneous, high-volume meteorological signals across India, normalizes unstructured and structured payloads, extracts geographic entities, deduplicates incoming reports into canonical weather events, verifies claims against physical telemetry, and powers real-time alerts.

```mermaid
flowchart TD
    subgraph Sources [Heterogeneous Signal Ingestion]
        S1[Open-Meteo AWS Mesh]
        S2[Data.gov.in IMD Feeds]
        S3[Google News RSS Feeds]
        S4[Mastodon Weather Network]
        S5[Citizen Ground Reports]
    end

    subgraph Normalization [Ingestion & Sanitization]
        N1[BaseConnector Ingestion]
        N2[Secret Redaction & Security Filter]
        N3[Schema Normalizer & Pydantic Validation]
    end

    subgraph Geospatial [Spatial-Temporal Resolution]
        G1[Location Extraction Engine]
        G2[State & District Centroid Lookup]
        G3[Spatial Adjacency Indexing]
    end

    subgraph AI_Verification [AI Intelligence & Verification]
        V1[Groq Llama-3.3-70B / Rule Classifier]
        V2[Spatial-Temporal Deduplicator]
        V3[Physical Telemetry Corroboration Engine]
        V4[Dynamic Weather Evidence Graph DWEG]
    end

    subgraph Storage [Multi-Tier Storage & Streaming]
        DB1[(PostgreSQL / SQLite Storage)]
        DB2[(OpenSearch Text & Geospatial Index)]
        DB3[(Neo4j Graph Store)]
        WS[WebSocket Live Broadcast /ws/events]
    end

    subgraph Consumers [Operational Consumption]
        FE[SkyPulse React GIS Map & Radar]
        AN[National & State Analytics]
        AL[Alert Propagation Engine]
    end

    S1 & S2 & S3 & S4 & S5 --> N1
    N1 --> N2 --> N3
    N3 --> G1 --> G2 --> G3
    G3 --> V1 --> V2 --> V3 --> V4
    V4 --> DB1 & DB2 & DB3 & WS
    DB1 & WS --> FE & AN & AL
```

---

## 2. Stage-by-Stage Processing Architecture

### Stage 1: Source Discovery & Polling
- **Workers**: Asynchronous polling workers (`backend/connectors/`) orchestrate rate-limited requests to external APIs and web feeds.
- **Connectors**:
  - `OpenMeteoConnector`: Polls hourly surface observations (temperature, humidity, precipitation, wind speed, pressure) across hundreds of district coordinates.
  - `DataGovConnector`: Ingests official IMD datasets from api.data.gov.in.
  - `NewsWebsiteConnector`: Aggregates news headlines and articles via Google News RSS for weather hazards.
  - `SocialWebConnector`: Searches Mastodon feeds for hyper-local hashtags (`#mumbairains`, `#delhiweather`, `#chennairains`, `#bengalururains`).
  - `ReportService`: Handles direct citizen crowdsourced submissions with media attachments.

### Stage 2: Schema Normalization & Sanitization
- **Pydantic Validation**: Payload is converted to `RawReportSchema` with mandatory UTC timestamps, ISO strings, and standard floating-point telemetry.
- **Redaction Engine**: Filters and scrubs embedded API keys, tokens, session IDs, and private user identifiers before database persistence.

### Stage 3: Geospatial & Entity Extraction
- **Location Extraction**: Textual reports are scanned against Indian States (28 states, 8 UTs) and 700+ District Gazettes.
- **Centroid & Bounding Box**: When GPS coordinates are not provided by the source, the centroid and district bounding box are assigned.
- **Spatial Resolution**: Categorizes resolution as `EXACT_POINT`, `CITY`, `DISTRICT`, or `STATE`.

### Stage 4: Deduplication & Canonical Event Clustering
- **Clustering Rule**: Reports occurring within:
  1. **Spatial radius**: ≤ 45 km
  2. **Temporal window**: ≤ 6 hours
  3. **Phenomenon similarity**: Same meteorological category (e.g. `FLOODING`, `HEATWAVE`, `THUNDERSTORM`)
- **Canonical Weather Event**: Grouped into a single canonical `WeatherEvent` (`EVT-...`), updating signal counts, evidence arrays, and confidence tiers (`MODERATE`, `HIGH`, `VERY HIGH`).

### Stage 5: Multi-Signal Verification & AI Engine
- **Telemetry Corroboration**: Cross-references report claims against nearby automated weather station (AWS) observations.
- **Status Determination**:
  - `VERIFIED`: Multiple independent sources or ground sensor corroboration (Confidence $\ge 0.70$).
  - `LIKELY`: Single high-credibility publisher with corroborating regional signals ($0.50 \le \text{Confidence} < 0.70$).
  - `UNVERIFIED`: Single uncorroborated report awaiting telemetry corroboration ($\text{Confidence} < 0.50$).
  - `CONTRADICTED`: Ground station telemetry contradicts the reported condition.
- **AI Intelligence**: Summaries, impact narratives, and hazard classifications are produced via Groq Llama-3.3-70B with instantaneous rule-based fallback.

### Stage 6: Graph & Search Indexing
- **DWEG Knowledge Graph**: Ingested entities are linked in Neo4j (`EVT` $\xrightarrow{\text{LOCATED\_AT}}$ `LOC`, `REP` $\xrightarrow{\text{CORROBORATES}}$ `EVT`, `SRC` $\xrightarrow{\text{PUBLISHED}}$ `REP`).
- **OpenSearch Indexing**: Full-text descriptions and vector embeddings are indexed for semantic similarity search.

### Stage 7: Real-Time Broadcast & REST APIs
- **WebSocket Gateway**: Dispatches event creations and updates over `wss://.../ws/events`.
- **REST Endpoints**: Serves geojson `/api/v1/map/features`, paginated `/api/v1/events`, and analytics `/api/v1/metrics/national`.
