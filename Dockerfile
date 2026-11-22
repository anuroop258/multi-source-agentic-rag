# Multi-stage build: compile the React UI, then package it with FastAPI.
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/app/data \
    CHROMA_DIR=/app/data/chroma \
    SQLITE_PATH=/app/data/conversations.sqlite3
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && pip install -r requirements.txt
COPY . .
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
RUN mkdir -p /app/data/uploads /app/data/chroma
EXPOSE 10000
CMD ["sh", "-c", "uvicorn rag_app.server:app --host 0.0.0.0 --port ${PORT:-10000}"]
