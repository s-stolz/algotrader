# syntax=docker/dockerfile:1.20
FROM python:3.15.2-slim

RUN apt-get update && apt-get install -y gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
# Dependency metadata changes invalidate this layer; source-only changes do not.
COPY --parents libs/*/pyproject.toml realtime-service/pyproject.toml realtime-service/constraints*.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install realtime-service --third-party-only

COPY libs ./libs
COPY realtime-service ./realtime-service
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install realtime-service

WORKDIR /app
COPY realtime-service /app

EXPOSE 8765 8080

CMD ["python", "-u", "main.py"]
