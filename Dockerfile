# --- Stage 1: Build frontend ---
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python runtime ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py demo.py release_funds.py ./
COPY agents/ ./agents/
COPY contracts/ ./contracts/
COPY core/ ./core/
COPY db/ ./db/
COPY marketplace/ ./marketplace/
COPY messaging/ ./messaging/
COPY tools/ ./tools/
COPY utils/ ./utils/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Create writable directories (volumes override these at runtime)
RUN mkdir -p agreements delivery logs keys

EXPOSE 8000

CMD ["python", "server.py"]
