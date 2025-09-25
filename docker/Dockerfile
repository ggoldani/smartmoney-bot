FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates git tzdata \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src /app/src
COPY .env.example /app/.env.example
ENV PYTHONUNBUFFERED=1
CMD ["python", "src/main.py", "--dry-run"]
