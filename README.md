# SkyPulse — National Weather Big Data Analytics Platform

> Real-time national weather intelligence combining heterogeneous weather signals, AI analysis, geospatial intelligence, and Big Data processing for India.

---

## Problem

India faces frequent, severe weather events — floods, cyclones, heatwaves, dust storms — that impact millions of citizens. Traditional forecasting systems are slow to relay ground-truth conditions. Critical information exists scattered across social media, citizen reports, government sensors, and public APIs, but no unified platform correlates and verifies this intelligence in real time.

## Solution

SkyPulse is a **national weather intelligence platform** that ingests heterogeneous weather signals from multiple authorized sources, applies AI/ML for extraction, classification, deduplication, and verification, and delivers a real-time operational dashboard for analysts, administrators, government users, and the public.

SkyPulse is **not** a weather forecasting app. It is a **weather evidence intelligence system**.

---

## Core Capabilities

| Capability | Description |
|---|---|
| Multi-source ingestion | Weather APIs, public datasets, authorized feeds, citizen reports |
| Real-time streaming | Kafka-backed stream processing with sub-5-second event delivery |
| AI classification | NLP + image analysis for automatic weather event categorization |
| Evidence-based verification | Multi-signal verification with explainable scores |
| Duplicate detection | Semantic + spatial + temporal clustering into canonical events |
| Geospatial intelligence | PostGIS-powered location extraction, mapping, and spatial queries |
| Real-time dashboard | Live India map, event heatmap, state/district analytics |
| Admin Panel | Connector health, moderation, audit, user management |
| Demo mode | Fully seeded synthetic data pipeline for demonstration |

---

## Signature Innovation — Dynamic Weather Evidence Graph (DWEG)

SkyPulse introduces the **Dynamic Weather Evidence Graph**, a live knowledge graph that models weather events as interconnected nodes linked by spatial propagation, temporal evolution, and cross-source evidence chains.

Unlike simple event lists, DWEG tracks **how a weather event evolves**, which sources corroborate it, and what propagation path it is following. It produces an **Event Confidence Field** — a spatial heatmap showing where a weather event is most likely occurring based on converging evidence — and an **Event Propagation Timeline** showing movement and intensification.

**What makes DWEG distinctive in SkyPulse's implementation:**
- Combines citizen observations + official sensors + historical patterns in a single graph
- Uses spatial relationship edges (adjacency, upstream/downstream) not just point proximity
- Tracks evidence chain provenance for full auditability
- Generates automated propagation alerts when a localized event shows expansion signals

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, MapLibre GL JS, Recharts, Zustand, Socket.io-client |
| Backend API | FastAPI (Python 3.11), Pydantic v2 |
| Stream broker | Apache Kafka (Redpanda for prototype) |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Cache | Redis 7 |
| Search | OpenSearch 2.x |
| Object storage | MinIO (S3-compatible) |
| Graph store | Neo4j 5 (DWEG layer) |
| AI/ML | Python, Hugging Face Transformers, sentence-transformers, OpenCV, spaCy |
| LLM integration | OpenAI API / Ollama (local fallback) |
| Containerization | Docker, Docker Compose |
| Monitoring | Prometheus, Grafana |
| Reverse proxy | Nginx |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                          │
│  Weather APIs | Public Datasets | Citizen Reports | Feeds    │
└───────────────────────────┬──────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                 CONNECTOR LAYER (Python workers)             │
└───────────────────────────┬──────────────────────────────────┘
                            ↓
                    ┌───────────────┐
                    │     Kafka     │  (Redpanda)
                    └───────┬───────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│              AI PROCESSING PIPELINE                          │
│  NLP Extraction → Classification → Geolocation              │
│  Duplicate Detection → Verification → DWEG Update           │
└───────────────────────────┬──────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                       STORAGE                                │
│  PostgreSQL+PostGIS | Redis | MinIO | OpenSearch | Neo4j     │
└───────────────────────────┬──────────────────────────────────┘
                            ↓
                    ┌───────────────┐
                    │  FastAPI +    │
                    │  WebSocket    │
                    └───────┬───────┘
                            ↓
                    ┌───────────────┐
                    │  React        │
                    │  Dashboard    │
                    └───────────────┘
```

---

## Repository Structure

```
skypulse/
├── README.md
├── docker-compose.yml
├── docker-compose.demo.yml
├── .env.example
├── docs/
│   ├── PRD.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── AI_ML.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_SPECIFICATION.md
│   ├── UI_UX.md
│   └── IMPLEMENTATION_PLAN.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── db/
│   ├── connectors/
│   ├── ai/
│   ├── workers/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── store/
│   │   ├── hooks/
│   │   └── utils/
│   ├── public/
│   └── package.json
├── infra/
│   ├── nginx/
│   ├── prometheus/
│   └── grafana/
├── scripts/
│   ├── seed_demo.py
│   ├── migrate.py
│   └── generate_stream.py
└── tests/
    ├── integration/
    └── e2e/
```

---

## Local Setup

### Prerequisites

- Docker 24+ and Docker Compose v2
- Node.js 20+ and npm 10+
- Python 3.11+
- Git

### Quick Start (Demo Mode)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/skypulse.git
cd skypulse

# 2. Copy environment variables
cp .env.example .env

# 3. Start all services in demo mode
docker compose -f docker-compose.demo.yml up -d

# 4. Seed demo data
docker compose exec backend python scripts/seed_demo.py

# 5. Access the platform
# Dashboard:   http://localhost:3000
# API docs:    http://localhost:8000/docs
# Grafana:     http://localhost:3001
# MinIO:       http://localhost:9001
```

### Full Development Setup

```bash
# Start infrastructure services only
docker compose up -d postgres redis kafka minio opensearch neo4j

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev  # Starts on http://localhost:3000

# Start AI workers
python -m workers.ai_pipeline
```

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://skypulse:password@localhost:5432/skypulse

# Redis
REDIS_URL=redis://localhost:6379/0

# Kafka / Redpanda
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_RAW=skypulse.raw
KAFKA_TOPIC_PROCESSED=skypulse.processed
KAFKA_TOPIC_EVENTS=skypulse.events

# MinIO / S3
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_MEDIA=skypulse-media

# OpenSearch
OPENSEARCH_URL=http://localhost:9200

# Neo4j (DWEG)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# AI / LLM
OPENAI_API_KEY=sk-...           # Optional; system falls back to Ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_PROVIDER=ollama             # openai | ollama | disabled
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Auth
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Weather APIs (all optional; demo mode works without them)
OPENWEATHERMAP_API_KEY=
IMD_API_KEY=
WEATHERAPI_KEY=

# App
APP_ENV=development             # development | production | demo
DEMO_MODE=true
LOG_LEVEL=INFO
```

---

## Running the Project

| Command | Description |
|---|---|
| `docker compose -f docker-compose.demo.yml up` | Full demo stack |
| `docker compose up -d` | Infrastructure only |
| `uvicorn app.main:app --reload` | Backend dev server |
| `npm run dev` | Frontend dev server |
| `python scripts/seed_demo.py` | Seed demo data |
| `python scripts/generate_stream.py` | Stream synthetic events |
| `alembic upgrade head` | Run DB migrations |
| `pytest` | Run backend tests |
| `npm run test` | Run frontend tests |

---

## Demo Mode

When `DEMO_MODE=true` or using `docker-compose.demo.yml`:

- A synthetic event generator produces weather reports every 5–30 seconds across India
- Reports span all supported event types with realistic geo-coordinates
- Demo sources are tagged `source_type=DEMO` and visually marked in the UI
- The full ingestion → AI → verification → dashboard pipeline operates normally
- All AI, deduplication, and DWEG features work on synthetic data
- No external API keys are required

---

## Testing

```bash
# Backend unit tests
cd backend && pytest tests/unit/ -v

# Backend integration tests (requires running infrastructure)
pytest tests/integration/ -v

# Frontend tests
cd frontend && npm run test

# E2E tests (requires full stack)
cd tests/e2e && npm run test:e2e
```

---

## Deployment Overview

SkyPulse is containerized. For production:

1. Set `APP_ENV=production` and `DEMO_MODE=false`
2. Replace MinIO with AWS S3 or GCS
3. Replace Redpanda with managed Kafka (Confluent Cloud / MSK)
4. Replace self-hosted PostgreSQL with a managed instance (RDS / Cloud SQL)
5. Use a managed Neo4j instance (Aura) for DWEG
6. Configure Nginx for TLS termination
7. Set up Prometheus + Grafana alerting

See `docs/IMPLEMENTATION_PLAN.md` Phase 12 for full deployment steps.

---

## Documentation

| File | Purpose |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Product requirements |
| [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) | Technical architecture |
| [docs/AI_ML.md](docs/AI_ML.md) | AI/ML pipeline design |
| [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | Complete database schema |
| [docs/API_SPECIFICATION.md](docs/API_SPECIFICATION.md) | REST API contracts |
| [docs/UI_UX.md](docs/UI_UX.md) | Frontend design specification |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Phased implementation plan |

---

*SkyPulse — Turning weather signals into national intelligence.*
