# syntax=docker/dockerfile:1.20
FROM python:3.15.2-alpine

RUN apk add --no-cache curl

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
# Dependency metadata changes invalidate this layer; source-only changes do not.
COPY --parents libs/*/pyproject.toml database-accessor-api/pyproject.toml database-accessor-api/constraints*.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install database-accessor-api --third-party-only

COPY libs ./libs
COPY database-accessor-api ./database-accessor-api
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install database-accessor-api

WORKDIR /app
COPY database-accessor-api /app

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
