# ============================================================
# base stage — system dependencies only (shared by builder & production)
# ============================================================
FROM python:3.13-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

WORKDIR /app

# Runtime system libs: libpq (psycopg), curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random

# ============================================================
# builder stage — compile dependencies (includes build tools)
# ============================================================
FROM base AS builder

# Build tools needed to compile C extensions (psycopg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first (cached layer — only rebuilds when lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Copy the application source
COPY app app
COPY scripts scripts
COPY run.py mcp_servers.json rag_providers.json ./

# Install the project itself
RUN uv sync --locked --no-dev

# ============================================================
# production stage — minimal runtime image
# ============================================================
FROM base AS production

ARG APP_ENV=production
ENV APP_ENV=${APP_ENV}

# Copy the virtual environment from builder (includes all installed packages)
ENV VIRTUAL_ENV=/app/.venv
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

ENV PYTHONPATH=/app

# Copy application files from builder
COPY --from=builder /app/app /app/app
COPY --from=builder /app/scripts /app/scripts
COPY --from=builder /app/run.py /app/run.py
COPY --from=builder /app/mcp_servers.json /app/mcp_servers.json
COPY --from=builder /app/rag_providers.json /app/rag_providers.json
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Make entrypoint script executable
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Create runtime directories
RUN mkdir -p /app/logs /app/app/core/skills/prompts/_auto

EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]