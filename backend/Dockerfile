# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy dependency manifests only (for layer caching)
COPY pyproject.toml poetry.lock* ./

# Export dependencies to requirements.txt (no dev deps in runtime image)
RUN poetry export --without dev --without-hashes -f requirements.txt -o requirements.txt

# Install into an isolated prefix so we can copy cleanly to runtime stage
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application source (overridden at runtime by bind mount in docker-compose)
COPY . .

EXPOSE 8000

# Production-safe CMD — no --reload. Dev hot-reload is injected via docker-compose command: override.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
