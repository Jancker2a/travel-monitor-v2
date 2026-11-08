#!/usr/bin/env bash
# ==============================================================================
# Travel Monitor 2.0 — All-in-One Turnkey Launcher
# Launches interactive Frontend, FastAPI Backend, and Database on Port 8000
# ==============================================================================

set -e
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "=================================================================="
echo "🚀 Starting Travel Monitor 2.0 (Dual-Engine Platform)"
echo "=================================================================="

# 1. Activate Python Environment
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
else
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_ROOT/.venv"
    source "$PROJECT_ROOT/.venv/bin/activate"
    pip install -q -r "$PROJECT_ROOT/backend/requirements.txt"
fi

# 2. Check Database initialization
if [ ! -f "$PROJECT_ROOT/travel_monitor_v2.db" ]; then
    echo "⚡ Initializing database and importing 43K+ historical offers..."
    python "$PROJECT_ROOT/scripts/migrate_v1_sqlite.py"
fi

# 3. Check Frontend Production Build
if [ ! -d "$PROJECT_ROOT/frontend/dist" ]; then
    echo "📦 Building React SPA frontend with Vite & Tailwind..."
    (cd "$PROJECT_ROOT/frontend" && npm install --silent && npm run build)
fi

echo ""
echo "✅ Travel Monitor 2.0 is READY!"
echo "   🌐 Web Application:   http://localhost:8000"
echo "   📖 API Documentation: http://localhost:8000/docs"
echo "   🩺 Health Probe:      http://localhost:8000/healthz"
echo "=================================================================="
echo "Press Ctrl+C to stop the platform."
echo ""

cd "$PROJECT_ROOT/backend"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
