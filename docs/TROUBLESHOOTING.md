# SkyPulse Troubleshooting & FAQ Guide

This guide covers common issues, debugging steps, and resolutions encountered during local development, containerization, and production deployment.

---

## 1. Common Issues & Solutions

### 1.1 Google Maps API Key Restrictions Error
- **Symptom**: Browser alert or console error: `This API project is not authorized to use this API` or map tiles fail to load.
- **Cause**: The Google Maps JavaScript API key has application restrictions (e.g. Android only) or lacks `Maps JavaScript API` service enablement.
- **Solution**:
  1. Open [Google Cloud Console](https://console.cloud.google.com/).
  2. Navigate to **APIs & Services > Credentials**.
  3. Select your API key and ensure **Maps JavaScript API** is checked under API restrictions.
  4. For local development, allow `http://localhost:*` under Application restrictions (HTTP referrers) or set to None during development.

### 1.2 Frontend Shows 0 Events or Blank State
- **Symptom**: Dashboard or LiveMap renders empty tables or says "No current telemetry".
- **Cause**: The backend API is not running or unreachable, and demo mode is turned off.
- **Solution**:
  - Set `VITE_DEMO_MODE=true` in `frontend/.env.local`.
  - Check backend status at `http://localhost:8000/api/v1/admin/health`.

### 1.3 Groq / LLM Intelligence Unavailable
- **Symptom**: AI narrative outputs default to rule-based fallback summaries.
- **Cause**: `GROQ_API_KEY` is not set or rate limit exceeded.
- **Solution**:
  - SkyPulse includes a deterministic fallback provider (`backend/ai/fallback_provider.py`) that instantly synthesizes structured meteorological findings when Groq is unavailable.
  - To enable full Groq LLM inference, obtain a free API key at [console.groq.com](https://console.groq.com) and set `GROQ_API_KEY=gsk_...` in `backend/.env`.

### 1.4 WebSocket Connection Drops (`ws://` / `wss://`)
- **Symptom**: Topbar indicates `DISCONNECTED` or WebSocket reconnects repeatedly.
- **Cause**: Reverse proxy not forwarding `Upgrade` headers or mixed content HTTPS/WS mismatch.
- **Solution**:
  - Ensure HTTPS sites connect to `wss://` (secure WebSocket).
  - Check Nginx configuration includes:
    ```nginx
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    ```

### 1.5 Database Migration / SQLite Lock
- **Symptom**: `OperationalError: database is locked` during concurrent backend writes.
- **Solution**:
  - In local development, ensure WAL mode is active.
  - For multi-worker concurrent production workloads, use PostgreSQL (`DATABASE_URL=postgresql+asyncpg://...`).

---

## 2. Diagnostic Commands

```bash
# Check Python backend logs
uvicorn app.main:app --log-level debug

# Verify open ports
netstat -ano | findstr :8000
netstat -ano | findstr :3000

# Test backend health directly
curl -v http://localhost:8000/api/v1/admin/health
```
