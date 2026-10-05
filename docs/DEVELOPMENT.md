# SkyPulse Local Development Guide

This guide provides step-by-step instructions to set up, run, and test SkyPulse locally on your development machine.

---

## 1. Prerequisites

Ensure you have the following tools installed:
- **Node.js**: `v18.0.0` or higher (`node -v`)
- **npm**: `v9.0.0` or higher (`npm -v`)
- **Python**: `3.11.x` (`python --version`)
- **Git**: (`git --version`)
- **Docker & Docker Compose** (optional for running full infrastructure locally)

---

## 2. Quick Setup

### 2.1 Clone the Repository
```bash
git clone https://github.com/alokkumar-gh/SkyPulse.git
cd SkyPulse
```

### 2.2 Backend Setup (Python / FastAPI)
```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment configuration
cp .env.example .env

# Run database migrations / initialize SQLite local database
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend API documentation is available at `http://localhost:8000/docs`.

### 2.3 Frontend Setup (React / TypeScript / Vite)
```bash
cd frontend

# Install npm dependencies
npm install

# Configure environment overrides
cp .env.example .env.local

# Start Vite local development server
npm run dev
```
The frontend is available at `http://localhost:3000/`.

---

## 3. Environment Configurations

### Frontend (`frontend/.env.local`)
```ini
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/events
VITE_GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
VITE_DEMO_MODE=true
```

### Backend (`backend/.env`)
```ini
APP_NAME=SkyPulse
APP_ENV=development
DEBUG=true
PORT=8000
SECRET_KEY=skypulse-dev-secret-key-32-chars-long
DATABASE_URL=sqlite+aiosqlite:///./skypulse.db
GROQ_ENABLED=true
AI_PROVIDER=auto
```

---

## 4. Running Tests

### Frontend Unit & Component Tests
```bash
cd frontend
npm test
```

### Frontend Production Build Test
```bash
cd frontend
npm run build
```

### Backend Tests
```bash
cd backend
pytest tests/
```
