# SmartMoney Bot - Production Dockerfile
# Python 3.13 Slim

FROM python:3.13-slim

# Metadata
LABEL maintainer="SmartMoney Brasil"
LABEL version="2.0.0"
LABEL description="Crypto Trading Alerts Bot for Brazilian Community"

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Working directory
WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone to BRT
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy requirements first (cache layer optimization)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/

# Create non-root user
RUN useradd -r -s /bin/false -u 1001 smartmoney && \
    mkdir -p /app/data /app/logs && \
    chown -R smartmoney:smartmoney /app

# Switch to non-root user
USER smartmoney

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run bot (production mode - sem --dry-run)
CMD ["python", "-u", "src/main.py"]
