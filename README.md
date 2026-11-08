# ✈️ Travel Monitor 2.0

Next-Generation Intelligent Travel Price Monitor, Universal Meta-Search, and Price Prediction Platform.

---

## 🌟 Key Features
- **Interactive Web SPA:** Modern React 18 + Vite + Tailwind CSS meta-search application with destination pills, date filters, traveler configurator, and airport selectors.
- **The Dual-Engine Data Architecture:**
  - **Instant Cache Engine:** Sub-100ms response time against a pre-indexed historical database (43,651+ price snapshots across 1,115 hotels).
  - **On-Demand Live Engine:** Real-time parametric query builder and live scrape gateway for custom user requests.
- **Hopper Self-Learning Radar & Deal Score:**
  - Real-time deal badges (`SUPER_DEAL`, `GOOD_DEAL`, `FAIR_PRICE`, `OVERPRICED`).
  - Actionable recommendations (`BUY NOW`, `WAIT`) with calibrated confidence scores.
  - SVG price sparklines rendered inline on every hotel card.
- **Hotel Passport & Historical Charts:**
  - Complete price fluctuation graphs powered by Plotly.js.
  - Tooltips displaying trip dates, price per night per person, and departure airport.
  - All-time statistics (historical min, median, max).
- **Smart Watchlist & Price Alerts:**
  - One-click price tracking with custom target price ($P_{\text{target}}$).
  - Background scheduler automatically detecting price drops $\ge 50$ PLN or target hits.
  - Automated Telegram push notifications.

---

## 🏗️ Architecture Stack
- **Frontend:** React 18, Vite, TypeScript, Tailwind CSS, Lucide Icons, Plotly.js 2.35.2
- **Backend:** Python 3.9+, FastAPI (async/await), Pydantic v2
- **Database & ORM:** PostgreSQL 16 / SQLite with SQLAlchemy 2.0, asyncpg, and aiosqlite
- **Background Worker:** Async lifespan scheduler for Watchlist evaluation & alerts
- **Scraping Engine:** Asynchronous HTTP client with browser headers and RDFa schema parser

---

## 🚀 Quick Start (1-Click Launcher)

To run the complete platform (Frontend, Backend API, and Database):
```bash
./start.sh
```

Then open:
- 🌐 **Web Application:** `http://localhost:8000`
- 📖 **Interactive API Docs (Swagger):** `http://localhost:8000/docs`
- 🩺 **Health Check:** `http://localhost:8000/healthz`

---

## 🐳 Docker Compose
```bash
docker compose up -d
```

---

## 🧪 Testing

Run complete backend test suite:
```bash
source .venv/bin/activate
pytest
# 10 passed in 0.17s
```

Run frontend build verification:
```bash
cd frontend
npm run build
# ✓ built in 767ms
```
