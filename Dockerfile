# syntax=docker/dockerfile:1

# ---- Stage 1: build the Next.js static export ----
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: backend + static assets ----
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Layout under /app mirrors the repo root: backend/, frontend/out/ (built frontend), db/ (bind mount).
WORKDIR /app/backend
COPY backend/ ./
RUN uv sync --frozen

COPY --from=frontend-build /frontend/out /app/frontend/out

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
