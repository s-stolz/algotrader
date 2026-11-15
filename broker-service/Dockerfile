# syntax=docker/dockerfile:1.20
FROM python:3.15.2-slim

RUN apt-get update && apt-get install -y gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
# Dependency metadata changes invalidate this layer; source-only changes do not.
COPY --parents libs/*/pyproject.toml broker-service/pyproject.toml broker-service/constraints*.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install broker-service --third-party-only

COPY libs ./libs
COPY broker-service ./broker-service
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install broker-service

WORKDIR /app
COPY broker-service /app

EXPOSE 8050

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050", "--reload"]
