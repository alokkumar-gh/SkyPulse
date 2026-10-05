# SkyPulse Data Sources & Ingestion Catalog

This document details all implemented data sources, telemetry feeds, and ingestion connectors integrated into SkyPulse.

---

## 1. Data Source Inventory

| Source Name | Category | Primary Telemetry / Data | Polling Frequency | Connector Class | Operational Status |
|---|---|---|---|---|---|
| **Open-Meteo Mesonet Mesh** | Weather Telemetry | Surface Temp, Humidity, Rain (mm), Wind Speed, Pressure, Weather Codes | Continuous / Hourly (3600s) | `OpenMeteoConnector` | **Production (Live)** |
| **Google News Weather Feeds** | News Media RSS | Headlines, Weather Hazard Articles, Severe Alert Reports | Every 15 minutes (900s) | `NewsWebsiteConnector` | **Production (Live)** |
| **Mastodon Weather Network** | Decentralized Social Web | Citizen posts, local weather updates, hashtag feeds (`#mumbairains`, `#delhiweather`, etc.) | Every 10 minutes (600s) | `SocialWebConnector` | **Production (Live)** |
| **Data.gov.in (Open Government Data)** | Official IMD Datasets | District rainfall bulletins, weather station aggregates | Every 10 minutes (configurable via `DATA_GOV_API_KEY`) | `DataGovConnector` | **Production (Ready)** |
| **IMD SACHET / Cap Feeds** | Early Warning Feeds | Cyclone, Flood, Heatwave CAP-format warning alerts | Every 5 minutes (300s) | `IndianApiConnector` | **Production (Integrated)** |
| **Citizen Weather Reports** | Crowdsourced Ground Truth | Field observations, localized rain/waterlogging reports, uploaded media | Event-driven / Webhook | `ReportService` / `SubmitReport.tsx` | **Production (Live)** |
| **National Mesonet Array** | Synthetic Supplement Layer | 240+ Observation Points & 75+ Nationwide Hazard Events | Deterministic Seeded PRNG (`Mulberry32`) | `demoDataLayer.ts` | **Local Demo Mode** |

---

## 2. Ingestion Connectors Detail

### 2.1 Open-Meteo Connector (`backend/connectors/openmeteo_connector.py`)
- **API Endpoint**: `https://api.open-meteo.com/v1/forecast`
- **Coverage**: Coordinates across major metropolitan centres and state capitals in India.
- **Fields Collected**:
  - `temperature_2m` (°C)
  - `relative_humidity_2m` (%)
  - `precipitation` (mm)
  - `wind_speed_10m` (km/h)
  - `wind_gusts_10m` (km/h)
  - `surface_pressure` (hPa)
  - `weather_code` (WMO meteorological code)
- **Error Handling**: Exponential backoff retry with cached observation fallbacks.

### 2.2 Google News Weather Connector (`backend/connectors/news_website_connector.py`)
- **RSS Feed URL**: `https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en`
- **Queries Tracked**:
  - `weather India`
  - `heavy rain India flood`
  - `heatwave India temperature`
  - `cyclone alert IMD`
  - `thunderstorm lightning alert`
- **Processing**: Regex-based location extraction, keyword entity tagging, and deduplication.

### 2.3 Social Web Connector (`backend/connectors/social_web_connector.py`)
- **API Endpoint**: Mastodon Public Search API (`https://mastodon.social/api/v2/search`)
- **Hashtags Ingested**: `#mumbairains`, `#delhirains`, `#bengalururains`, `#chennairains`, `#hyderabadrains`, `#assamfloods`, `#keralarains`.
- **Sanitization**: Automatic stripping of personal identifiers, URLs, and metadata tags before indexing.

### 2.4 Data.gov.in IMD Connector (`backend/connectors/data_gov_connector.py`)
- **API Endpoint**: `https://api.data.gov.in/resource/{resource_id}`
- **Format**: JSON / XML structured government records.
- **Authentication**: `api-key` header (configured via `DATA_GOV_API_KEY`).

---

## 3. Data Integrity & Provenance Rules

1. **No Data Fabrication in Production**: Live backend databases never inject synthetic records.
2. **Deterministic Offline Demo Mode**: When `VITE_DEMO_MODE=true` is set, the frontend supplements backend feeds with 240+ observation points and 75+ nationwide hazard events for demonstration and local development without modifying the production database.
3. **Multi-Source Corroboration**: An event requires two or more independent signal sources or physical sensor corroboration to achieve `VERIFIED` status.
