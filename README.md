# ✈️ Travel Monitor 2.0

Next-Generation Intelligent Travel Price Monitor, Universal Meta-Search, and Price Prediction Platform.

---

## 🌟 Key Features
- **Universal Live Search:** Search across any destination, departure dates, duration (6-15 nights), passenger compositions (adults + children), and airports.
- **The Dual-Engine Data Architecture:**
  - **Trunk Engine:** Automated background monitoring of TOP-500 hotels across core destinations, maintaining dense, continuous price history.
  - **On-Demand Engine:** Real-time fast query builder and live scrape gateway for custom user requests.
- **Deterministic Cohort Signatures (`cohort_hash`):** Normalizes chaotic searches into structured time-series packages.
- **Hopper Self-Learning Engine:** Predictive Buy/Wait signals calibrated against real historical price trajectories.
- **Deal Score & Market DNA:** Identifies true discounts vs deceptive marketing baselines.

---

## 🏗️ Architecture Stack
- **Backend:** Python 3.11, FastAPI (async/await)
- **Database:** PostgreSQL 16 (or Supabase in production) with SQLAlchemy 2.0 & asyncpg
- **Caching:** Redis 7 / Upstash
- **Scraping:** Fast asynchronous HTTP gateway & headless Playwright fallback
- **Containerization:** Docker Compose

---

## 🚀 Quick Start (Local Development)

### 1. Using Docker Compose (Recommended)
```bash
docker compose up -d
```
FastAPI interactive Swagger documentation will be available at:
👉 `http://localhost:8000/docs`

Healthcheck:
👉 `http://localhost:8000/healthz`

### 2. Without Docker (Local Virtual Environment)
```bash
# Setup venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Run migrations / tests
PYTHONPATH=backend python3 -m unittest discover -s backend/tests

# Run server with SQLite (for fast local dev without Postgres)
DATABASE_URL="sqlite+aiosqlite:///travel_monitor_v2.db" uvicorn app.main:app --reload --port 8000
```

---

## 📦 Data Migration from v1
To import all 4 months of historical price data (20,000+ offers) from `travel-price-monitor` v1 into v2:

```bash
source .venv/bin/activate
PYTHONPATH=backend python3 scripts/migrate_v1_sqlite.py
```

---

## 🧪 Testing
```bash
source .venv/bin/activate
PYTHONPATH=backend python3 -m unittest discover -s backend/tests
```

