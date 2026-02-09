# syntax=docker/dockerfile:1.7

# SmartMoney Bot - Production Dockerfile
# Python 3.13 Slim

FROM python:3.13-slim AS builder

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Working directory
WORKDIR /app

# Install build dependencies (only in builder)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (cache layer optimization)
COPY requirements.txt .

# Install Python dependencies with BuildKit cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# --------------------------

FROM python:3.13-slim AS runtime

# Metadata
LABEL maintainer="SmartMoney Brasil"
LABEL version="1.0.0"
LABEL description="Crypto Trading Alerts Bot for Brazilian Community"

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone to BRT
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy installed dependencies from builder
COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/

# Create non-root user
RUN useradd -r -s /bin/false -u 1001 smartmoney && \
    mkdir -p /app/data /app/logs && \
    chown -R smartmoney:smartmoney /app

# Switch to non-root user
USER smartmoney

# Healthcheck is defined in docker-compose.yml (single source of truth)

# Run bot (production mode - sem --dry-run)
CMD ["python", "-u", "src/main.py"]
