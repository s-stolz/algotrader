# syntax=docker/dockerfile:1.20
FROM python:3.15.2-slim

RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
# Dependency metadata changes invalidate this layer; source-only changes do not.
COPY --parents libs/*/pyproject.toml indicator-api/pyproject.toml indicator-api/constraints*.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install indicator-api --third-party-only

COPY libs ./libs
COPY indicator-api ./indicator-api
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install indicator-api

WORKDIR /app
COPY indicator-api /app

EXPOSE 8080

CMD ["python", "main.py"]
