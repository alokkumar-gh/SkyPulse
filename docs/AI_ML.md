# SkyPulse — AI/ML Intelligence Layer

**Version:** 2.0 (Step 5 — Real AI/ML Intelligence Layer)  
**Status:** Production-Ready (Trainable on Google Colab, Deployable on ₹0 Oracle VM CPU)

---

## Architecture Overview

The SkyPulse AI/ML intelligence layer operates as a multi-tier, CPU-optimized machine learning pipeline that seamlessly combines genuine trainable models with deterministic fallback providers:

```text
Incoming Report (Kafka/REST)
          │
          ▼
Text Preprocessing & Multilingual Normalization (English / Hindi / Hinglish)
          │
          ▼
┌────────────────────────────────────────────────────────┐
│ ML Inference Service (backend/ml/inference_service.py) │
│ 1. Weather Event Classifier (DistilBERT/MiniLM/ONNX)  │
│ 2. Semantic Embedding Model (all-MiniLM-L6-v2)         │
│ 3. Misinformation Credibility Model (Tabular ML)       │
│ 4. Spatiotemporal Anomaly Detector (Isolation Forest)  │
└────────────────────────────────────────────────────────┘
          │
          ├── [If Model Trained & Available] ──► ML Output + Probabilities + Model Version
          └── [If NOT_TRAINED or Low Conf]  ──► FallbackAIProvider (Offline Deterministic Heuristic)
          │
          ▼
Multi-Level Deduplication Engine (Embedding Cosine + Spatiotemporal Radius)
          │
          ▼
Multi-Source Verification Engine (IMD + data.gov.in + Citizen Corroboration + Media)
          │
          ▼
Dynamic Weather Evidence Graph (DWEG) & Confidence Engine
```

### Zero-Cost Compute & Self-Hosted Design
- **Training:** Google Colab Free Tier (`ml_training/SkyPulse_ML_Training.ipynb`)
- **Inference:** Oracle Always-Free VM (Single/Dual Core CPU via ONNX Runtime / PyTorch `map_location='cpu'`)
- **No Paid APIs:** Zero dependency on OpenAI, Gemini, Claude, or Groq for core weather intelligence
- **Zero-Crash Resiliency:** If any model artifact is missing or corrupt, `MODEL_STATUS = NOT_TRAINED` is reported and ingestion continues uninterrupted via `FallbackAIProvider`.

---

## 1. Model Registry & Lifecycle Management (`backend/ml/model_registry.py`)

Every model in SkyPulse is explicitly registered and version-controlled with immutable metadata:
- `model_name`: Unique identifier (e.g., `weather_event_classifier`)
- `version`: Semantic version string (`1.0.0`)
- `task`: `TEXT_CLASSIFICATION`, `CREDIBILITY`, `ANOMALY_DETECTION`, `EMBEDDING`
- `framework`: `ONNX`, `PYTORCH`, `HUGGINGFACE`, `SCIKIT_LEARN`
- `artifact_path`: Relative or absolute path in `ML_MODEL_DIR`
- `checksum`: SHA-256 integrity hash of model weights
- `status`: `NOT_TRAINED`, `TRAINED`, `LOADED`, `NOT_LOADED`, `ERROR`
- `metrics`: Training & evaluation metrics (`macro_f1`, `accuracy`, `confusion_matrix`)

---

## 2. Weather Event Classifier

### Model Architecture
- **Base Architecture:** Compact fine-tuned transformer (`distilbert-base-uncased` or `sentence-transformers/all-MiniLM-L6-v2`) exported to ONNX Runtime graph with dynamic batch and sequence axes.
- **Inference Runtime:** CPU Execution Provider (`onnxruntime` or PyTorch CPU).
- **Inference Latency:** ~8–15 ms per sample on single CPU thread.

### Canonical Weather Categories
1. `RAINFALL`
2. `THUNDERSTORM`
3. `FLOODING`
4. `HEATWAVE`
5. `FOG`
6. `DUST_STORM`
7. `STRONG_WINDS`
*(Supported extensions: `CYCLONE`, `HAILSTORM`, `SNOWFALL`, `SMOG`, `UNKNOWN`)*

---

## 3. Google Colab Training Pipeline (`ml_training/SkyPulse_ML_Training.ipynb`)

1. **Environment Setup:** Installs `transformers`, `torch`, `onnx`, `scikit-learn`, `evaluate`, `accelerate` on free Colab runtime.
2. **Dataset Ingestion:** Combines IMD bulletins, data.gov.in public weather records, historical reports, and verified ground citizen reports.
3. **Class Balancing & Split:** Stratified 70/15/15 Train/Validation/Test split with macro-F1 evaluation.
4. **ONNX Export:** Quantizes and exports `model.onnx` optimized for CPU execution.
5. **Packaging:** Calculates SHA-256 checksum and produces `metadata.json` and a deployable zip archive.

### Severity Classification

Severity is independently classified on a 1–4 scale:

| Score | Label | Example |
|---|---|---|
| 1 | Minor | Light rain, mild fog |
| 2 | Moderate | Heavy rain, dense fog |
| 3 | Severe | Flooding, heatwave > 44°C |
| 4 | Extreme | Cloudburst, flash flood with casualties |

Severity is estimated from: textual severity words, numeric values (temperature, wind speed, rainfall mm), mention of impact (casualties, rescue, road closure).

---

## 2. NLP Extraction

### Pipeline

Uses **spaCy** (`en_core_web_sm` + custom Indian location NER) as the primary NER engine, augmented by an LLM structured extraction prompt for complex reports.

### Extracted Fields

| Field | Method | Example |
|---|---|---|
| `event_mentions` | NER + keyword matching | "flooding", "heavy rain" |
| `location_mentions` | NER (GPE, LOC) + Indian location dictionary | "Chennai", "Tamil Nadu" |
| `severity_mentions` | Pattern matching + NER | "extremely heavy", "5 feet deep" |
| `time_mentions` | spaCy time entity + dateparser | "yesterday evening", "3 PM IST" |
| `numeric_values` | Regex + unit normalization | "150mm rainfall", "45°C" |
| `impact_mentions` | NER + pattern | "road blocked", "5 casualties" |
| `evidence_phrases` | Noun chunks filtered for relevance | "knee-deep water on the road" |

### LLM Extraction Prompt (Structured Output)

When `LLM_PROVIDER != disabled`:

```
You are a weather intelligence extraction system. Extract structured data from the following weather report.

Report: {text}

Extract the following fields as JSON:
- event_type: one of [RAINFALL, THUNDERSTORM, FLOODING, HEATWAVE, FOG, DUST_STORM, STRONG_WINDS, UNKNOWN]
- location: city, district, state if mentioned
- severity: 1-4 integer, 0 if unknown
- time_reference: ISO8601 datetime or relative string, null if not mentioned
- evidence_summary: 1-2 sentence factual summary of the weather evidence
- confidence: 0.0-1.0 how confident you are in this extraction

Return ONLY valid JSON. Do not explain.
```

**Output validation:** The JSON output is parsed and validated with Pydantic. If parsing fails, the system falls back to spaCy-only extraction.

### Fallback

If LLM is unavailable:
1. spaCy NER for entities
2. Regex patterns for numeric values and severity
3. Keyword lookup for event type
4. dateparser for time
5. Result confidence is capped at 0.65 when fallback is used

---

## 3. Image Analysis

### Purpose

Extract visual weather evidence from attached photos to:
1. Corroborate or contradict the textual report
2. Provide additional confidence signal to the verification engine

### Tools

- **OpenCV:** Basic image processing (blur detection, color analysis)
- **CLIP (OpenAI's model via HuggingFace):** Zero-shot visual classification against weather evidence prompts
- **Perceptual hashing (pHash):** Image deduplication

### Visual Classification Prompts (CLIP zero-shot)

```python
WEATHER_EVIDENCE_PROMPTS = [
    "flooded street with water",
    "heavy rain falling",
    "lightning in dark sky",
    "thick fog reducing visibility",
    "dust storm approaching",
    "heatwave dry cracked land",
    "strong winds bending trees",
    "hailstones on ground",
    "waterlogged roads",
    "rescue operation in flood",
    "clear sky sunny day",  # negative
    "normal weather conditions",  # negative
]
```

### Output

```json
{
  "image_evidence_labels": [
    {"label": "flooded street with water", "confidence": 0.82},
    {"label": "waterlogged roads", "confidence": 0.74}
  ],
  "supports_claimed_event": true,
  "visual_severity_boost": 1,
  "is_blurry": false,
  "phash": "a3f4e1b2c9...",
  "faces_detected": false,
  "analysis_method": "clip_zero_shot"
}
```

### Privacy

Before analysis, face detection is run. If faces are detected, faces are blurred in the stored version. Raw original is stored in a restricted MinIO bucket.

### Fallback

If CLIP is unavailable: only perceptual hash computed. `supports_claimed_event` defaults to `null` (neutral). Verification engine treats null image evidence as absent, not contradicting.

---

## 4. Duplicate Detection

### Problem

Multiple reports — from different sources or citizens — may describe the same real-world weather event. These must be grouped into a **Canonical Event** with all original reports preserved as **Evidence Reports**.

### Detection Algorithm

A candidate is considered a duplicate of an existing canonical event if it passes all three gates:

**Gate 1 — Temporal window**
```
|report.time - canonical.time| ≤ DEDUP_TIME_WINDOW (default: 6 hours)
```

**Gate 2 — Spatial proximity**
```
distance(report.location, canonical.centroid) ≤ DEDUP_SPATIAL_RADIUS (default: 50 km)
```

**Gate 3 — Composite similarity score ≥ threshold (default: 0.75)**
```
score = (
    0.40 × semantic_similarity(report.embedding, canonical.embedding)
  + 0.25 × event_category_match         # 1.0 if same, 0.0 if different
  + 0.20 × spatial_score(distance)       # 1.0 at 0km, 0.0 at 50km
  + 0.15 × image_hash_similarity         # pHash similarity if images present
)
```

### Embedding Model

`sentence-transformers/all-MiniLM-L6-v2` — 384-dimensional embeddings, fast inference, good multilingual performance.

Embeddings are stored in PostgreSQL `vector` column (pgvector extension) or in Redis for fast nearest-neighbor lookup.

### Canonical Event Update

When a new report is added to a duplicate cluster:
1. Canonical event centroid is recomputed (weighted average of all report locations)
2. Canonical event time range is extended to include the new report's time
3. Confidence score is updated (more corroborating sources → higher confidence)
4. DWEG graph is updated with the new evidence node

### Never Delete Policy

Original reports are **never deleted**. They are marked as `is_duplicate = true` with `canonical_event_id` set. They remain queryable and are shown as evidence in the event detail view.

### Manual Cluster Operations (Analyst)

- **Split:** Analyst marks a report as not belonging to a cluster → new canonical event created
- **Merge:** Analyst combines two canonical events → one canonical supersedes the other, all reports reassigned

All manual operations are logged in the audit trail.

---

## 5. Verification Engine

### Design Principle

The verification engine does **not** ask an LLM "is this report true?" Instead it assembles independent evidence signals and weighs them to produce a structured verification result.

### Verification Status Values

| Status | Meaning |
|---|---|
| `VERIFIED` | Strong corroborating evidence from multiple independent signals |
| `LIKELY` | Moderate evidence; consistent but not fully corroborated |
| `UNVERIFIED` | Insufficient data to determine; report accepted provisionally |
| `CONTRADICTED` | Official data or majority of nearby reports contradict this report |
| `REQUIRES_REVIEW` | Conflicting signals or suspicious patterns; needs analyst attention |

### Evidence Signals

| Signal | Weight | Source |
|---|---|---|
| Official API data match | 0.30 | OpenWeatherMap / IMD at report location + time |
| Nearby corroborating reports | 0.25 | Count of VERIFIED/LIKELY reports within 30km, 3 hours |
| Source trust score | 0.20 | Historical reliability of this source |
| Image evidence match | 0.10 | CLIP analysis supports claimed event |
| Temporal consistency | 0.10 | Report time is plausible for the event season/hour |
| Historical baseline | 0.05 | Event type is historically common for this location/season |

### Scoring Function

```python
def compute_verification_score(signals: VerificationSignals) -> float:
    score = (
        0.30 * signals.official_api_match      # 1.0 match, 0.5 partial, 0.0 no data, -1.0 contradicts
      + 0.25 * signals.nearby_corroboration    # min(count/5, 1.0)
      + 0.20 * signals.source_trust_score      # 0.0–1.0
      + 0.10 * signals.image_evidence_score    # 1.0 supports, 0.5 null, 0.0 contradicts
      + 0.10 * signals.temporal_consistency    # 0.0–1.0
      + 0.05 * signals.historical_baseline     # 0.0–1.0
    )
    return max(0.0, min(1.0, score))

def score_to_status(score: float, has_contradictions: bool) -> VerificationStatus:
    if has_contradictions and score < 0.3:
        return CONTRADICTED
    if score >= 0.75:
        return VERIFIED
    if score >= 0.50:
        return LIKELY
    if score >= 0.25:
        return UNVERIFIED
    return REQUIRES_REVIEW
```

### Explainable Verification

Every verification result includes a structured explanation:

```json
{
  "status": "LIKELY",
  "confidence_score": 0.64,
  "explanation": "Moderate rainfall of 45mm/h confirmed by OpenWeatherMap for Chennai at report time. 2 nearby citizen reports corroborate heavy rain in Adyar and Tambaram. Source 'CWC Chennai' has a trust score of 0.78. No image attachment to analyze. Historical data shows Chennai receives heavy rain during Oct-Dec.",
  "evidence_items": [
    {
      "type": "OFFICIAL_API",
      "source": "OpenWeatherMap",
      "description": "45mm/h rain recorded at Chennai at 14:30 IST",
      "weight_contribution": 0.15
    },
    {
      "type": "NEARBY_REPORT",
      "count": 2,
      "description": "2 verified/likely reports within 30km in the past 3 hours",
      "weight_contribution": 0.10
    }
  ]
}
```

---

## 6. Source Trust Engine

### Design

Source trust is calculated dynamically from historical performance. It is NOT a fixed value.

### Trust Score Formula

For each source, after each verified/rejected event:

```python
def update_trust_score(source_id: str, outcome: str, current_score: float) -> float:
    """
    outcome: 'VERIFIED' | 'LIKELY' | 'UNVERIFIED' | 'CONTRADICTED' | 'REQUIRES_REVIEW'
    """
    REWARD = {'VERIFIED': +0.05, 'LIKELY': +0.02, 'UNVERIFIED': 0, 'CONTRADICTED': -0.10, 'REQUIRES_REVIEW': -0.03}
    delta = REWARD[outcome]
    
    # Weighted moving average: recent outcomes weighted higher
    new_score = current_score + (delta * LEARNING_RATE)
    return max(0.1, min(0.99, new_score))  # floor 0.1, ceiling 0.99
```

### Initial Values

| Source Type | Initial Trust Score |
|---|---|
| Official government API | 0.85 |
| Established news feed | 0.70 |
| Registered citizen (verified phone) | 0.55 |
| Anonymous citizen | 0.40 |
| Demo/simulated connector | 0.50 |

### Trust Score History

Every update is stored in `source_reputation_history` table for full auditability and trend visualization.

---

## 7. Confidence Scoring

The **Confidence Score** on a canonical event represents how certain the system is that the event is real and correctly classified.

### Formula

```python
confidence = (
    0.35 * verification_score           # From verification engine
  + 0.25 * min(evidence_count / 5, 1.0) # More evidence = higher confidence
  + 0.20 * avg_source_trust             # Average trust of all contributing sources
  + 0.10 * classification_confidence    # AI classifier confidence
  + 0.10 * location_confidence          # GPS-provided vs geocoded vs estimated
)
```

Confidence is recomputed whenever a new evidence report is added to the cluster.

---

## 8. Anomaly Detection

### Purpose

Detect unusual weather activity: events that are historically anomalous for the location and season.

### Method

For each new canonical event, compare against a **Location-Season Baseline**:

```python
def is_anomalous(event: CanonicalEvent) -> AnomalyResult:
    baseline = get_baseline(
        state=event.state,
        district=event.district,
        event_type=event.category,
        month=event.occurred_at.month
    )
    
    z_score = (event.severity - baseline.mean_severity) / baseline.std_severity
    return AnomalyResult(
        is_anomalous = z_score > ANOMALY_THRESHOLD,  # default: 2.0
        z_score = z_score,
        baseline_mean = baseline.mean_severity,
        description = f"Severity {event.severity} is {z_score:.1f} standard deviations above historical mean for {event.category} in {event.district} in {month_name}"
    )
```

### Baseline Data

- Loaded from IMD historical open datasets (seeded at startup)
- Populated from verified events accumulated over time
- District × event_category × month granularity

### Anomaly Display

Anomalous events receive an **Anomaly Badge** in the dashboard and are surfaced first in the analyst queue.

---

## 9. Signature Innovation — Dynamic Weather Evidence Graph (DWEG)

### 9.1 Concept

DWEG is a live knowledge graph in Neo4j that models the relationship between weather events, their evidence, their locations, and their temporal evolution. It answers questions that a relational database cannot efficiently answer:

- "What path did this flood follow through districts over the past 6 hours?"
- "Which reports corroborate each other, and which contradict?"
- "Is this new report in District B an expansion of the event in District A, or a separate event?"

### 9.2 Graph Schema

**Node Types:**

| Node Label | Properties |
|---|---|
| `WeatherEvent` | `event_id`, `category`, `severity`, `confidence`, `status`, `occurred_at` |
| `EvidenceReport` | `report_id`, `source_type`, `trust_score`, `submitted_at`, `text_summary` |
| `Location` | `location_id`, `name`, `level` (city/district/state), `lat`, `lon` |
| `WeatherCondition` | `condition_id`, `api_source`, `temperature`, `rain_mm`, `wind_speed`, `recorded_at` |
| `Source` | `source_id`, `name`, `type`, `trust_score` |

**Edge Types:**

| Relationship | From → To | Properties |
|---|---|---|
| `CORROBORATES` | EvidenceReport → WeatherEvent | `corroboration_score`, `added_at` |
| `CONTRADICTS` | EvidenceReport → WeatherEvent | `contradiction_score`, `added_at` |
| `LOCATED_AT` | WeatherEvent/EvidenceReport → Location | `location_confidence` |
| `SPATIALLY_ADJACENT` | Location → Location | `distance_km`, `direction`, `shares_boundary` |
| `TEMPORALLY_FOLLOWS` | WeatherEvent → WeatherEvent | `time_delta_minutes`, `is_propagation` |
| `ORIGINATED_FROM` | EvidenceReport → Source | `retrieved_at` |
| `OFFICIAL_DATA_FOR` | WeatherCondition → Location | `valid_at` |
| `CONTRADICTED_BY` | WeatherEvent → WeatherCondition | `contradiction_reason` |

### 9.3 Algorithm — Propagation Detection

```python
def detect_propagation(new_event: WeatherEvent, graph: Neo4jSession) -> PropagationResult:
    """
    Determines if new_event is a propagation of an existing event.
    """
    # Find spatially adjacent locations with recent same-category events
    query = """
    MATCH (new_loc:Location {location_id: $loc_id})
    MATCH (existing:WeatherEvent {category: $category})
          -[:LOCATED_AT]->(existing_loc:Location)
          -[:SPATIALLY_ADJACENT]->(new_loc)
    WHERE existing.occurred_at > datetime() - duration({hours: 12})
      AND existing.event_id <> $event_id
    RETURN existing, existing_loc,
           existing_loc.distance_km AS distance,
           existing_loc.direction AS direction,
           duration.inMinutes(existing.occurred_at, new_event.occurred_at) AS time_delta
    ORDER BY existing.occurred_at ASC
    LIMIT 5
    """
    
    results = graph.run(query, ...)
    
    if results and results[0].time_delta > 0:
        # Event is later in time than adjacent event → likely propagation
        return PropagationResult(
            is_propagation=True,
            parent_event_id=results[0].existing.event_id,
            direction=results[0].direction,
            time_delta_minutes=results[0].time_delta,
            confidence=compute_propagation_confidence(results)
        )
    return PropagationResult(is_propagation=False)
```

### 9.4 Event Confidence Field (Spatial)

The Event Confidence Field is a GeoJSON heatmap layer derived from the DWEG:

```python
def compute_confidence_field(event_id: str) -> GeoJSON:
    """
    Returns a GeoJSON FeatureCollection with point features
    weighted by evidence density, suitable for MapLibre heatmap layer.
    """
    reports = get_all_evidence_reports(event_id)
    
    features = []
    for report in reports:
        weight = report.trust_score * report.corroboration_score
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [report.lon, report.lat]},
            "properties": {"weight": weight, "source_type": report.source_type}
        })
    
    return {"type": "FeatureCollection", "features": features}
```

This GeoJSON is served via the DWEG API and rendered as a MapLibre heatmap layer in the frontend.

### 9.5 Evidence Chain Narrative

Generated by LLM (or template when LLM unavailable):

**LLM Prompt:**
```
You are a weather intelligence analyst. Based on the following evidence graph data for a weather event, 
write a concise 3-5 sentence evidence chain narrative in plain English.

Event: {category} in {location}, severity {severity}
Evidence reports (chronological): {report_summaries}
Propagation: {propagation_data}
Official data: {official_conditions}

Write a factual narrative describing how the event developed, what evidence supports it, and if it has propagated.
Do not speculate beyond the evidence. Do not use the word "I".
```

**Template fallback:**
```
{category} event first reported in {first_location} at {first_time} by {first_source}.
{count} evidence reports collected over {duration}. 
{official_match_text}
{propagation_text}
Confidence: {confidence:.0%}.
```

### 9.6 Required Data

- `weather_events` and `weather_reports` tables (PostgreSQL)
- District adjacency data (pre-loaded from Indian administrative boundary GeoJSON)
- Official API weather condition snapshots stored every 15 minutes per district

### 9.7 DWEG APIs

| Endpoint | Purpose |
|---|---|
| `GET /api/dweg/events/{event_id}/graph` | Full graph data for visualization |
| `GET /api/dweg/events/{event_id}/confidence-field` | GeoJSON heatmap data |
| `GET /api/dweg/events/{event_id}/propagation-timeline` | Ordered propagation nodes |
| `GET /api/dweg/events/{event_id}/evidence-chain` | Narrative + structured evidence |
| `GET /api/dweg/propagation-alerts` | Active propagation alerts |

### 9.8 UI Components

1. **Graph Visualization** — Force-directed graph using D3.js (or Cytoscape.js) showing nodes and edges
2. **Confidence Field Heatmap** — MapLibre heatmap layer overlaid on India map
3. **Propagation Timeline** — Animated timeline showing event movement through districts
4. **Evidence Chain Panel** — Narrative text + structured evidence list with source badges

### 9.9 Implementation Strategy

**Phase 1 (MVP):** Graph stored in Neo4j, basic CORROBORATES and LOCATED_AT edges, confidence field computed from report locations.

**Phase 2:** Add SPATIALLY_ADJACENT edges from pre-loaded district boundary data, propagation detection algorithm.

**Phase 3:** LLM-generated evidence chain narrative, propagation alerts via WebSocket.

---

## 10. AI Safety

### 10.1 Hallucination Mitigation

- LLM outputs are **always** parsed and validated with Pydantic before use
- LLM is used for **extraction and summarization only**, never for classification decisions alone
- All LLM outputs are stored with `method = "llm_extraction"` for auditability
- If LLM output fails validation 3 times: fall back to spaCy; mark confidence as `fallback`

### 10.2 Prompt Injection Protection

- User-submitted text is **HTML-escaped** and **length-limited** (max 2000 chars) before insertion into LLM prompts
- Prompts use delimited sections: `<report>...</report>` to separate instructions from content
- System prompt is hardcoded; user content is never merged into system prompt position

### 10.3 Output Validation

Every AI output passes through a Pydantic schema before being accepted:
- Classification: valid category from the enum list
- Severity: integer 1–4
- Confidence: float 0.0–1.0
- Coordinates: valid latitude/longitude range
- Verification status: valid enum value

If validation fails → fallback used, incident logged.

### 10.4 Fallback Behavior

| AI Component | Fallback |
|---|---|
| LLM extraction | spaCy NER + keyword rules |
| CLIP image analysis | pHash only; `supports_claimed_event = null` |
| Geocoding | Manual district-level location from text keywords |
| Verification | Score-based without image evidence signal |
| DWEG narrative | Template-based narrative |

### 10.5 Human Review

- Any report with `confidence < 0.3` is automatically routed to `REQUIRES_REVIEW`
- Any contradicted report is automatically routed to analyst queue
- Analysts can flag any report for secondary review
- Admin can disable individual AI components and default to manual processing

---

## 11. Real Weather ML Training Dataset Assembly (Step 6)

### 11.1 Multi-Source Provenance Architecture
The dataset assembly pipeline (`ml_training/build_dataset.py`) extracts and synthesizes records across four authoritative sources:
1. **Source A (IMD):** Official Indian meteorological reports, warnings, nowcasts, and AWS/ARG observations.
2. **Source B (data.gov.in):** Open government weather datasets (CWC flood gauges, historical rainfall summaries).
3. **Source C (ERA5 / ERA5-Land):** Historical reanalysis from the Copernicus Climate Data Store (CDS). Provides historical environmental context and conservative weak labels. **ERA5 is never treated as ground truth.**
4. **Source D (SkyPulse Verified):** Platform observations with explicit `VERIFIED` or `SUPPORTED` status.

### 11.2 Labeling System & Hierarchy
- **Strong Labels:** Official IMD warnings/bulletins (`label_confidence >= 0.90`) and ground observations with multi-source corroboration.
- **Weak Labels:** Meteorological threshold matches from raw sensor records or extreme ERA5 slices (`label_confidence: 0.60–0.80`).
- **Unlabeled / Conflicted:** Records with insufficient signals or contradictory observations (e.g., Heatwave vs Fog). Flagged with `conflict_flag=True` and category set to `UNKNOWN`.

### 11.3 Conservative Meteorological Thresholds
Thresholds are configuration-driven (`ml_training/labeling.py`):
- **Heavy Rainfall:** >= 64.5 mm / 24h
- **Heatwave (Plains):** >= 45.0 °C
- **Gale Winds:** >= 62.0 km/h
- **Dense Fog:** Visibility < 200 m

### 11.4 Spatiotemporal Alignment & Leakage Prevention
- **Temporal Alignment:** Bucketed into configurable windows (±1h, ±3h, ±6h).
- **Spatial Alignment:** `location_method` explicitly tracked (`EXACT_COORDINATE`, `STATION`, `DISTRICT_CENTROID`, `ERA5_GRID`, `GEOCODED`).
- **ERA5 Environmental Joining:** Nearest ERA5 grid features joined (`temperature_2m`, `total_precipitation`, `u_wind_10m`, `v_wind_10m`, `wind_speed = sqrt(u² + v²)`, `surface_pressure`, `dewpoint_2m`).
- **Chronological & Event-Clustered Split:** Train (70%), Val (15%), Test (15%) partitioned strictly by timestamp (`Train_end <= Val_start <= Test_start`). All reports belonging to the same canonical event cluster are assigned to a single partition to guarantee **zero spatial and temporal data leakage**.

### 11.5 Auditing, Manifest & Readiness
- **Quality Engine (`ml_training/quality.py`):** Physical bounds validation and unit normalization (°C, mm, km/h, hPa, km). Rejection tracking classifies samples into `VALID`, `SUSPICIOUS`, and `INVALID`.
- **Dataset Manifest (`dataset_manifest.json`):** SHA-256 integrity hash, class distribution, temporal boundaries, source availability status (`AVAILABLE`, `NOT_CONFIGURED`, `NO_DATA`, `ERROR`).
- **Readiness Evaluation (`DatasetReadinessReport`):** Classifies dataset readiness (`READY`, `READY_WITH_WARNINGS`, `NOT_READY`) based on sample volume, per-class representation, class imbalance ratio, and leakage checks.
