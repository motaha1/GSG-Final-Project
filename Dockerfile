# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY backend ./backend
COPY static ./static
COPY templates ./templates

# Create data dir for SQLite
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

CMD ["python", "-m", "hypercorn", "backend.main:app", "--bind", "0.0.0.0:8000"]

