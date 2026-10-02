# SkyPulse — API Specification

**Version:** 1.0  
**Base URL:** `/api/v1`  
**Auth:** Bearer JWT unless marked `[PUBLIC]`  
**Content-Type:** `application/json`

---

## Conventions

- All timestamps in ISO 8601 UTC: `2026-09-30T15:30:00Z`
- All coordinates: `[longitude, latitude]` (GeoJSON order)
- Pagination: `?page=1&per_page=25` → response includes `total`, `page`, `per_page`, `pages`
- Errors follow: `{"error": "ERROR_CODE", "message": "Human readable", "details": {}}`
- Demo-mode records include `"is_demo": true` field

---

## Authentication

### POST `/api/v1/auth/login`
`[PUBLIC]`

**Request:**
```json
{
  "email": "analyst@imd.gov.in",
  "password": "secret"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "analyst@imd.gov.in",
    "display_name": "IMD Analyst",
    "role": "ANALYST"
  }
}
```

**Errors:** `401 INVALID_CREDENTIALS`, `403 ACCOUNT_DISABLED`

---

### POST `/api/v1/auth/register`
`[PUBLIC]`

Register a citizen account.

**Request:**
```json
{
  "email": "citizen@example.com",
  "password": "strongpassword",
  "display_name": "Ravi Kumar",
  "phone_number": "+919876543210"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "email": "citizen@example.com",
  "role": "CITIZEN",
  "created_at": "2026-09-30T15:30:00Z"
}
```

**Errors:** `409 EMAIL_ALREADY_EXISTS`, `422 VALIDATION_ERROR`

---

### POST `/api/v1/auth/logout`
`[AUTH]`

Invalidates current token.

**Response 200:** `{"message": "Logged out successfully"}`

---

### GET `/api/v1/auth/me`
`[AUTH]`

**Response 200:**
```json
{
  "id": "uuid",
  "email": "analyst@imd.gov.in",
  "display_name": "IMD Analyst",
  "role": "ANALYST",
  "is_active": true,
  "created_at": "2026-09-30T00:00:00Z",
  "last_login_at": "2026-09-30T14:00:00Z"
}
```

---

## Reports

### POST `/api/v1/reports`
`[AUTH: CITIZEN+]`

Submit a new weather report.

**Request:**
```json
{
  "description": "Heavy flooding on Sardar Patel Road. Water is knee-deep.",
  "event_type": "FLOODING",
  "severity": 3,
  "latitude": 13.0827,
  "longitude": 80.2707,
  "location_name": "Chennai, Tamil Nadu",
  "event_time": "2026-09-30T14:15:00Z",
  "media_ids": ["uuid-1", "uuid-2"]
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "status": "PENDING",
  "tracking_id": "SP-2026-093042",
  "message": "Report submitted. You will be notified when it is reviewed.",
  "submitted_at": "2026-09-30T15:30:00Z"
}
```

**Errors:** `422 VALIDATION_ERROR`, `429 RATE_LIMIT_EXCEEDED`

---

### POST `/api/v1/reports/media`
`[AUTH: CITIZEN+]`

Upload media before submitting a report. Returns `media_id` for use in report submission.

**Request:** `multipart/form-data`
- `file`: image (JPEG/PNG/WebP, max 10MB) or video (MP4, max 50MB)
- `media_type`: `IMAGE` | `VIDEO`

**Response 201:**
```json
{
  "media_id": "uuid",
  "media_type": "IMAGE",
  "filename": "flood_photo.jpg",
  "size_bytes": 2048576,
  "status": "UPLOADED"
}
```

**Errors:** `413 FILE_TOO_LARGE`, `415 UNSUPPORTED_MEDIA_TYPE`, `422 MALWARE_DETECTED`

---

### GET `/api/v1/reports`
`[PUBLIC]`

List weather reports with filtering.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `page` | int | Page number (default: 1) |
| `per_page` | int | Results per page (default: 25, max: 100) |
| `category` | string | Filter by event category |
| `state` | string | Filter by state name |
| `district` | string | Filter by district |
| `verification_status` | string | VERIFIED\|LIKELY\|UNVERIFIED\|CONTRADICTED\|REQUIRES_REVIEW |
| `severity_min` | int | Minimum severity (1–4) |
| `date_from` | ISO date | Start date |
| `date_to` | ISO date | End date |
| `source_id` | uuid | Filter by source |
| `is_demo` | bool | Include demo records (default: true in demo mode) |

**Response 200:**
```json
{
  "total": 1542,
  "page": 1,
  "per_page": 25,
  "pages": 62,
  "results": [
    {
      "id": "uuid",
      "primary_category": "FLOODING",
      "sub_category": "URBAN_FLOOD",
      "severity": 3,
      "confidence_score": 0.82,
      "classification_confidence": 0.87,
      "location": {
        "city": "Chennai",
        "district": "Chennai",
        "state": "Tamil Nadu",
        "lat": 13.0827,
        "lon": 80.2707,
        "confidence": "HIGH"
      },
      "event_time": "2026-09-30T14:15:00Z",
      "ingested_at": "2026-09-30T14:16:03Z",
      "canonical_event_id": "uuid",
      "verification_status": "LIKELY",
      "source": {
        "id": "uuid",
        "name": "Citizen Report",
        "type": "CITIZEN",
        "trust_score": 0.55
      },
      "media_count": 2,
      "is_demo": false
    }
  ]
}
```

---

### GET `/api/v1/reports/{report_id}`
`[PUBLIC]`

**Response 200:**
```json
{
  "id": "uuid",
  "normalized_text": "Heavy flooding on Sardar Patel Road. Water is knee-deep.",
  "primary_category": "FLOODING",
  "sub_category": "URBAN_FLOOD",
  "severity": 3,
  "classification_confidence": 0.87,
  "classification_method": "zero_shot",
  "location": { "city": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707, "confidence": "HIGH" },
  "event_time": "2026-09-30T14:15:00Z",
  "ingested_at": "2026-09-30T14:16:03Z",
  "canonical_event_id": "uuid",
  "is_duplicate": false,
  "ai_extraction": {
    "entities": {"event": "flooding", "location": "Sardar Patel Road, Chennai"},
    "evidence_phrases": ["knee-deep water", "heavy flooding"],
    "method": "zero_shot"
  },
  "source": { "id": "uuid", "name": "Citizen Report", "type": "CITIZEN", "trust_score": 0.55 },
  "media": [
    { "id": "uuid", "media_type": "IMAGE", "url": "/api/v1/media/uuid", "thumbnail_url": "/api/v1/media/uuid/thumb" }
  ],
  "verification_status": "LIKELY",
  "is_demo": false
}
```

---

### GET `/api/v1/reports/search`
`[PUBLIC]`

Full-text search over reports.

**Query Parameters:**
- `q` (required): Search query string
- Plus all filter parameters from `GET /reports`

**Response 200:** Same structure as `GET /reports` with `score` field added per result.

---

## Weather Events

### GET `/api/v1/events`
`[PUBLIC]`

List canonical weather events.

**Query Parameters:** Same filters as `/reports` plus:
- `active_only` (bool): Only events where `resolved_at IS NULL`
- `anomalous_only` (bool): Only anomalous events

**Response 200:**
```json
{
  "total": 47,
  "page": 1,
  "per_page": 25,
  "pages": 2,
  "results": [
    {
      "id": "uuid",
      "category": "FLOODING",
      "sub_category": "URBAN_FLOOD",
      "severity": 3,
      "confidence_score": 0.78,
      "verification_status": "VERIFIED",
      "location": {
        "state": "Tamil Nadu",
        "district": "Chennai",
        "city": "Chennai",
        "lat": 13.0827,
        "lon": 80.2707
      },
      "first_reported_at": "2026-09-30T12:00:00Z",
      "last_updated_at": "2026-09-30T15:00:00Z",
      "evidence_count": 8,
      "is_anomalous": false,
      "is_active": true,
      "is_demo": false
    }
  ]
}
```

---

### GET `/api/v1/events/{event_id}`
`[PUBLIC]`

**Response 200:**
```json
{
  "id": "uuid",
  "category": "FLOODING",
  "sub_category": "URBAN_FLOOD",
  "severity": 3,
  "confidence_score": 0.78,
  "verification_status": "VERIFIED",
  "location": { "state": "Tamil Nadu", "district": "Chennai", "lat": 13.0827, "lon": 80.2707 },
  "first_reported_at": "2026-09-30T12:00:00Z",
  "last_updated_at": "2026-09-30T15:00:00Z",
  "resolved_at": null,
  "evidence_count": 8,
  "is_anomalous": false,
  "anomaly_z_score": null,
  "verification": {
    "status": "VERIFIED",
    "confidence_score": 0.82,
    "explanation": "...",
    "evidence_items": [],
    "method": "AI",
    "reviewed_by": null
  },
  "evidence_reports": [
    { "id": "uuid", "source_type": "CITIZEN", "event_time": "...", "severity": 3 }
  ],
  "media_gallery": [
    { "media_id": "uuid", "media_type": "IMAGE", "url": "..." }
  ],
  "is_demo": false
}
```

---

### GET `/api/v1/events/{event_id}/timeline`
`[PUBLIC]`

Evidence reports ordered chronologically for event evolution view.

**Response 200:**
```json
{
  "event_id": "uuid",
  "timeline": [
    {
      "timestamp": "2026-09-30T12:00:00Z",
      "report_id": "uuid",
      "source_type": "CITIZEN",
      "source_name": "Anonymous",
      "severity": 2,
      "location": { "district": "Tambaram" },
      "summary": "Light flooding on roads"
    },
    {
      "timestamp": "2026-09-30T13:30:00Z",
      "report_id": "uuid",
      "source_type": "WEATHER_API",
      "source_name": "OpenWeatherMap",
      "severity": 3,
      "location": { "district": "Chennai" },
      "summary": "85mm/h rainfall confirmed"
    }
  ]
}
```

---

### GET `/api/v1/events/nearby`
`[PUBLIC]`

Events near a coordinate.

**Query Parameters:**
- `lat` (required): Latitude
- `lon` (required): Longitude
- `radius_km` (default: 50): Search radius
- `limit` (default: 20)
- `active_only` (bool, default: true)

**Response 200:** Array of event objects with additional `distance_km` field.

---

## Verification

### GET `/api/v1/verification/{event_id}`
`[AUTH: ANALYST+]`

**Response 200:**
```json
{
  "event_id": "uuid",
  "status": "LIKELY",
  "confidence_score": 0.64,
  "explanation_text": "...",
  "evidence_items": [
    {
      "evidence_type": "OFFICIAL_API",
      "source_name": "OpenWeatherMap",
      "description": "45mm/h rain at Chennai at 14:30",
      "weight_contribution": 0.15
    }
  ],
  "signal_scores": {
    "official_api": 0.5,
    "nearby_reports": 0.4,
    "source_trust": 0.78,
    "image_evidence": 0.5,
    "temporal_consistency": 0.9,
    "historical_baseline": 0.8
  },
  "method": "AI",
  "is_manual_override": false,
  "created_at": "2026-09-30T15:00:00Z"
}
```

---

### PUT `/api/v1/verification/{event_id}`
`[AUTH: ANALYST+]`

Analyst manual verification override.

**Request:**
```json
{
  "status": "VERIFIED",
  "reason": "Visually confirmed flooding from attached image. Official IMD bulletin corroborates."
}
```

**Response 200:** Updated verification result object.

**Errors:** `404 EVENT_NOT_FOUND`, `422 INVALID_STATUS`

---

### GET `/api/v1/verification/queue`
`[AUTH: ANALYST+]`

Reports requiring analyst review, sorted by severity × confidence descending.

**Query Parameters:** `page`, `per_page`, `state`, `category`

**Response 200:** Paginated list of events with verification status `REQUIRES_REVIEW` or `UNVERIFIED` with high severity.

---

## Sources

### GET `/api/v1/sources`
`[PUBLIC]`

**Response 200:**
```json
{
  "results": [
    {
      "id": "uuid",
      "name": "OpenWeatherMap India",
      "source_type": "WEATHER_API",
      "trust_score": 0.85,
      "is_active": true,
      "is_demo": false,
      "last_success_at": "2026-09-30T15:00:00Z",
      "health_status": "HEALTHY",
      "records_ingested_last_hour": 142
    }
  ]
}
```

---

### GET `/api/v1/sources/{source_id}/trust-history`
`[AUTH: ANALYST+]`

**Response 200:**
```json
{
  "source_id": "uuid",
  "current_trust_score": 0.78,
  "history": [
    {
      "recorded_at": "2026-09-30T12:00:00Z",
      "old_score": 0.76,
      "new_score": 0.78,
      "outcome": "VERIFIED",
      "triggering_event_id": "uuid"
    }
  ]
}
```

---

## Analytics

### GET `/api/v1/analytics/national`
`[PUBLIC]`

National-level statistics.

**Query Parameters:** `date_from`, `date_to`, `is_demo`

**Response 200:**
```json
{
  "period": { "from": "2026-09-01T00:00:00Z", "to": "2026-09-30T23:59:59Z" },
  "total_events": 847,
  "active_events": 23,
  "total_reports": 4213,
  "by_category": {
    "RAINFALL": 312, "FLOODING": 187, "THUNDERSTORM": 98,
    "HEATWAVE": 64, "FOG": 104, "DUST_STORM": 42, "STRONG_WINDS": 40
  },
  "by_verification_status": {
    "VERIFIED": 402, "LIKELY": 187, "UNVERIFIED": 156, "CONTRADICTED": 12, "REQUIRES_REVIEW": 90
  },
  "by_severity": { "1": 210, "2": 387, "3": 198, "4": 52 },
  "anomalous_events": 8,
  "top_states": [
    { "state": "Tamil Nadu", "event_count": 124 },
    { "state": "Rajasthan", "event_count": 98 }
  ]
}
```

---

### GET `/api/v1/analytics/state/{state_name}`
`[PUBLIC]`

**Response 200:** Same structure as national but scoped to state, with district breakdown.

---

### GET `/api/v1/analytics/timeseries`
`[PUBLIC]`

**Query Parameters:**
- `metric`: `event_count` | `report_count` | `severity_avg`
- `interval`: `1h` | `6h` | `1d` | `7d`
- `category`: optional filter
- `state`: optional filter
- `date_from`, `date_to`

**Response 200:**
```json
{
  "metric": "event_count",
  "interval": "1h",
  "series": [
    { "timestamp": "2026-09-30T00:00:00Z", "value": 12 },
    { "timestamp": "2026-09-30T01:00:00Z", "value": 8 }
  ]
}
```

---

## Map / Geospatial

### GET `/api/v1/map/events`
`[PUBLIC]`

Bounding box query for map rendering.

**Query Parameters:**
- `bbox` (required): `min_lon,min_lat,max_lon,max_lat` (e.g., `68.0,8.0,97.5,37.5`)
- `zoom`: Current map zoom level (used for clustering)
- `category`, `verification_status`, `severity_min`, `date_from`, `date_to`

**Response 200:** GeoJSON FeatureCollection:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [80.2707, 13.0827] },
      "properties": {
        "event_id": "uuid",
        "category": "FLOODING",
        "severity": 3,
        "verification_status": "VERIFIED",
        "confidence_score": 0.78,
        "evidence_count": 8,
        "is_cluster": false,
        "is_demo": false
      }
    }
  ]
}
```

---

### GET `/api/v1/map/heatmap`
`[PUBLIC]`

Report density heatmap data.

**Query Parameters:** `date_from`, `date_to`, `category`

**Response 200:** GeoJSON FeatureCollection with weight properties.

---

## Admin

### GET `/api/v1/admin/users`
`[AUTH: ADMIN]`

**Query Parameters:** `page`, `per_page`, `role`, `is_active`, `search`

**Response 200:** Paginated user list.

---

### PUT `/api/v1/admin/users/{user_id}/role`
`[AUTH: ADMIN]`

**Request:** `{"role": "ANALYST"}`

**Response 200:** Updated user object.

---

### GET `/api/v1/admin/connectors`
`[AUTH: ADMIN]`

**Response 200:** List of all sources with health status.

---

### PUT `/api/v1/admin/connectors/{source_id}`
`[AUTH: ADMIN]`

Update connector configuration.

**Request:**
```json
{
  "is_active": true,
  "config": { "poll_interval_seconds": 300 }
}
```

**Response 200:** Updated source object.

---

### POST `/api/v1/admin/connectors`
`[AUTH: ADMIN]`

Create new connector.

**Request (WeatherAPI):**
```json
{
  "name": "WeatherAPI India",
  "source_type": "WEATHER_API",
  "connector_class": "WeatherAPIConnector",
  "config": { "api_key_env": "WEATHERAPI_KEY", "cities": ["Mumbai", "Delhi", "Chennai"] },
  "is_demo": false
}
```

**Request (IMD Government Source):**
```json
{
  "name": "India Meteorological Department (Official)",
  "source_type": "GOVERNMENT_API",
  "connector_class": "IMDConnector",
  "config": { "api_base_url": "https://api.imd.gov.in", "poll_interval_seconds": 300 },
  "is_demo": false
}
```

**Request (data.gov.in Government Dataset Source):**
```json
{
  "name": "Open Government Data Platform (data.gov.in)",
  "source_type": "GOVERNMENT_DATASET",
  "connector_class": "DataGovConnector",
  "config": {
    "api_base_url": "https://api.data.gov.in",
    "poll_interval_seconds": 600,
    "resources": [
      {
        "resource_id": "rainfall-district-daily-v1",
        "dataset_name": "Daily District Rainfall Report",
        "agency_name": "Ministry of Earth Sciences / IMD",
        "category": "RAINFALL",
        "limit": 100
      }
    ]
  },
  "is_demo": false
}
```

**Response 201:** Created source object.

---

### GET `/api/v1/admin/audit-logs`
`[AUTH: ADMIN]`

**Query Parameters:** `page`, `per_page`, `user_id`, `action_type`, `entity_type`, `date_from`, `date_to`

**Response 200:** Paginated audit log entries.

---

### GET `/api/v1/admin/system-health`
`[AUTH: ADMIN]`

**Response 200:**
```json
{
  "api_status": "HEALTHY",
  "database_status": "HEALTHY",
  "kafka_status": "HEALTHY",
  "redis_status": "HEALTHY",
  "opensearch_status": "HEALTHY",
  "neo4j_status": "HEALTHY",
  "ai_worker_status": "HEALTHY",
  "ingestion_rate_per_minute": 45,
  "processing_queue_depth": 12,
  "error_rate_last_hour": 0.02,
  "connectors": [
    { "source_id": "uuid", "name": "OpenWeatherMap", "status": "HEALTHY", "records_last_hour": 142 }
  ],
  "checked_at": "2026-09-30T15:30:00Z"
}
```

---

### GET `/api/v1/admin/duplicate-clusters`
`[AUTH: ANALYST+]`

**Query Parameters:** `page`, `per_page`, `event_id`, `state`

**Response 200:** Paginated cluster list with member count.

---

### POST `/api/v1/admin/duplicate-clusters/{cluster_id}/split`
`[AUTH: ANALYST+]`

Split a cluster.

**Request:** `{"report_ids_to_remove": ["uuid-1", "uuid-2"], "reason": "Reports describe different locations"}`

**Response 200:** `{"new_event_id": "uuid", "original_event_id": "uuid"}`

---

### POST `/api/v1/admin/duplicate-clusters/merge`
`[AUTH: ANALYST+]`

Merge two clusters.

**Request:** `{"primary_event_id": "uuid", "secondary_event_id": "uuid", "reason": "Same flood event"}`

**Response 200:** `{"merged_event_id": "uuid"}`

---

## DWEG — Dynamic Weather Evidence Graph

### GET `/api/v1/dweg/events/{event_id}/graph`
`[AUTH: ANALYST+]`

Full graph data for D3/Cytoscape visualization.

**Response 200:**
```json
{
  "event_id": "uuid",
  "nodes": [
    { "id": "evt-uuid", "type": "WeatherEvent", "label": "Flooding - Chennai", "properties": {} },
    { "id": "rep-uuid", "type": "EvidenceReport", "label": "Citizen Report", "properties": {} },
    { "id": "loc-uuid", "type": "Location", "label": "Chennai", "properties": { "lat": 13.08, "lon": 80.27 } }
  ],
  "edges": [
    { "source": "rep-uuid", "target": "evt-uuid", "type": "CORROBORATES", "properties": { "score": 0.9 } },
    { "source": "evt-uuid", "target": "loc-uuid", "type": "LOCATED_AT", "properties": {} }
  ],
  "generated_at": "2026-09-30T15:30:00Z"
}
```

---

### GET `/api/v1/dweg/events/{event_id}/confidence-field`
`[PUBLIC]`

GeoJSON heatmap for confidence field overlay.

**Response 200:** GeoJSON FeatureCollection with weighted point features.

---

### GET `/api/v1/dweg/events/{event_id}/propagation-timeline`
`[AUTH: ANALYST+]`

**Response 200:**
```json
{
  "event_id": "uuid",
  "propagation_steps": [
    {
      "step": 1,
      "timestamp": "2026-09-30T12:00:00Z",
      "location": { "district": "Tambaram", "lat": 12.93, "lon": 80.13 },
      "evidence_count": 2,
      "severity": 2
    },
    {
      "step": 2,
      "timestamp": "2026-09-30T13:30:00Z",
      "location": { "district": "Chennai", "lat": 13.08, "lon": 80.27 },
      "evidence_count": 6,
      "severity": 3,
      "propagation_direction": "NORTH",
      "time_delta_minutes": 90
    }
  ],
  "is_still_propagating": true
}
```

---

### GET `/api/v1/dweg/events/{event_id}/evidence-chain`
`[AUTH: ANALYST+]`

**Response 200:**
```json
{
  "event_id": "uuid",
  "narrative": "Flooding event first reported in Tambaram at 12:00 IST by anonymous citizen. Corroborated by 2 nearby reports in the following hour. OpenWeatherMap data confirms 85mm/h rainfall at Chennai at 13:30. Event has propagated northward to Chennai district.",
  "evidence_chain": [
    { "step": 1, "type": "FIRST_REPORT", "source": "Anonymous Citizen", "at": "12:00", "location": "Tambaram" },
    { "step": 2, "type": "OFFICIAL_CORROBORATION", "source": "OpenWeatherMap", "at": "13:30", "value": "85mm/h rain" }
  ],
  "confidence": 0.78,
  "generated_at": "2026-09-30T15:30:00Z"
}
```

---

### GET `/api/v1/dweg/propagation-alerts`
`[AUTH: ANALYST+]`

Active propagation alerts.

**Response 200:**
```json
{
  "alerts": [
    {
      "id": "uuid",
      "event_id": "uuid",
      "event_category": "FLOODING",
      "alert_type": "PROPAGATION_DETECTED",
      "message": "Flooding event expanding from Chennai to Tiruvallur district",
      "new_district": "Tiruvallur",
      "severity_trend": "INCREASING",
      "created_at": "2026-09-30T15:25:00Z"
    }
  ]
}
```

---

## WebSocket

### `WS /ws/events`
`[AUTH via ?token=]`

Real-time event stream.

**Messages received by client:**

```json
// New event published
{
  "type": "EVENT_PUBLISHED",
  "payload": { "event_id": "uuid", "category": "FLOODING", "severity": 3, "lat": 13.08, "lon": 80.27 }
}

// Event updated (verification status change)
{
  "type": "EVENT_UPDATED",
  "payload": { "event_id": "uuid", "verification_status": "VERIFIED", "confidence_score": 0.82 }
}

// DWEG propagation alert
{
  "type": "DWEG_PROPAGATION_ALERT",
  "payload": { "event_id": "uuid", "message": "Event expanding to Tiruvallur" }
}

// System notification
{
  "type": "SYSTEM_NOTIFICATION",
  "payload": { "title": "Connector Down", "message": "OpenWeatherMap connector failed" }
}
```

**Heartbeat:** Server sends `{"type": "PING"}` every 30s; client responds `{"type": "PONG"}`.

---

## Media

### GET `/api/v1/media/{media_id}`
`[PUBLIC]`

Stream media file. Returns redirect to presigned URL or proxied response.

### GET `/api/v1/media/{media_id}/thumb`
`[PUBLIC]`

Return thumbnail (128×128 WebP) for image media.

---

## Social & Web Weather Intelligence Connector

> **Compliance Notice:** Social-media ingestion requires an authorized API/feed or permitted public source. SkyPulse does not bypass platform access controls, solve CAPTCHAs, or implement stealth scraping.

### GET `/api/v1/connectors/social-web`
`[AUTH: ALL]`

Retrieve connector overview, supported source types (`SOCIAL_API`, `SOCIAL_FEED`, `PUBLIC_WEB`, `RSS_FEED`, `PUBLIC_JSON`), active source counts, and default weather hashtag/keyword filters.

**Response 200:**
```json
{
  "connector_name": "SocialWebConnector",
  "connector_version": "1.0.0",
  "status": "HEALTHY",
  "supported_source_types": ["SOCIAL_API", "SOCIAL_FEED", "PUBLIC_WEB", "RSS_FEED", "PUBLIC_JSON"],
  "default_weather_hashtags": ["#IMD", "#Weather", "#WeatherAlert", "#HeavyRain", "#Rainfall", "#Thunderstorm", "#Flood", "#Heatwave", "#Fog", "#DustStorm", "#StrongWinds"],
  "default_weather_keywords": ["heavy rain", "downpour", "rainfall", "thunderstorm", "lightning", "flood", "heatwave", "dense fog", "cyclone"],
  "active_sources_count": 2,
  "sources": [
    {
      "provider_id": "social-web-master-rss",
      "name": "Weather Alerts RSS/Atom Feed",
      "source_type": "RSS_FEED",
      "status": "HEALTHY",
      "config": { "feed_url": "https://mausam.imd.gov.in/rss/alerts.xml" },
      "metrics": { "records_fetched": 45, "records_accepted": 45, "records_rejected": 0 }
    }
  ]
}
```

---

### GET `/api/v1/connectors/social-web/status`
`[AUTH: ALL]`

Retrieve real-time telemetry metrics: `records_fetched`, `records_accepted`, `records_rejected`, latency, and individual provider health statuses.

---

### GET `/api/v1/connectors/social-web/sources`
`[AUTH: ALL]`

List all registered social & web sources with their configuration metadata (sensitive keys masked) and performance counters.

---

### POST `/api/v1/connectors/social-web/test`
`[AUTH: ANALYST, ADMIN, GOVERNMENT]`

Live smoke-test and validate a permitted public feed, webpage, JSON endpoint, or authorized social media API without persisting records or leaking credentials.

**Request:**
```json
{
  "source_type": "RSS_FEED",
  "url": "https://mausam.imd.gov.in/rss/alerts.xml"
}
```

**Response 200:**
```json
{
  "status": "HEALTHY",
  "source_type": "RSS_FEED",
  "tested_url": "https://mausam.imd.gov.in/rss/alerts.xml",
  "success": true,
  "records_found": 8,
  "sample_records": [
    {
      "external_id": "alert-101",
      "text": "Heavy rainfall warning for coastal districts",
      "observed_at": "2026-10-01T12:00:00Z"
    }
  ],
  "latency_ms": 115.4,
  "error_message": null
}
```

If credentials or URL are missing/unconfigured:
```json
{
  "status": "NOT_CONFIGURED",
  "source_type": "SOCIAL_API",
  "tested_url": null,
  "success": false,
  "records_found": 0,
  "error_message": "Missing base_url or authorized API credentials"
}
```

---

## Error Reference

| HTTP Code | Error Code | Description |
|---|---|---|
| 400 | BAD_REQUEST | Malformed request |
| 401 | UNAUTHORIZED | Missing or invalid token |
| 403 | FORBIDDEN | Insufficient role |
| 404 | NOT_FOUND | Resource not found |
| 409 | CONFLICT | Duplicate resource |
| 413 | FILE_TOO_LARGE | Upload exceeds limit |
| 415 | UNSUPPORTED_MEDIA_TYPE | Invalid file type |
| 422 | VALIDATION_ERROR | Request body validation failed |
| 429 | RATE_LIMIT_EXCEEDED | Too many requests |
| 500 | INTERNAL_ERROR | Server error |
| 503 | SERVICE_UNAVAILABLE | Dependency unavailable |
