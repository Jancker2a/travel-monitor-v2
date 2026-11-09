# ==============================================================================
# Travel Monitor 2.0 Multi-Stage Dockerfile
# Stage 1: Build React TypeScript Frontend
# Stage 2: Production Python FastAPI + Chromium Web Scraper Runtime
# ==============================================================================

# ----------------- Stage 1: Frontend Build -----------------
FROM node:20-alpine AS frontend-builder
WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ----------------- Stage 2: Production App -----------------
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Install system dependencies for Playwright & build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt && \
    playwright install chromium

# Copy Backend, Scripts, Site, and Database / Chunks
COPY backend /app/backend
COPY scripts /app/scripts
COPY site /app/site
COPY travel_monitor_v2.db* /app/

# Unpack database if chunks are present
RUN if [ -f /app/travel_monitor_v2.db.gz.aa ]; then \
        echo "Decompressing database chunks into /app/travel_monitor_v2.db..."; \
        cat /app/travel_monitor_v2.db.gz.* | gunzip > /app/travel_monitor_v2.db && \
        rm -f /app/travel_monitor_v2.db.gz.*; \
    fi

# Copy Built Frontend Assets from Stage 1 into /app/frontend/dist
COPY --from=frontend-builder /build/dist /app/frontend/dist

EXPOSE 8080

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

