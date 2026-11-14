# syntax=docker/dockerfile:1.20
FROM python:3.15.2-slim

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
# Dependency metadata changes invalidate this layer; source-only changes do not.
COPY --parents libs/*/pyproject.toml ingestion-service/pyproject.toml ingestion-service/constraints*.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install ingestion-service --third-party-only

COPY libs ./libs
COPY ingestion-service ./ingestion-service
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install ingestion-service

WORKDIR /app
COPY ingestion-service /app

# Run the service
CMD ["python", "main.py"]
