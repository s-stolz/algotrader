# syntax=docker/dockerfile:1.20
FROM python:3.15.2-slim

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
# Dependency metadata changes invalidate this layer; source-only changes do not.
COPY --parents libs/*/pyproject.toml backtester/pyproject.toml backtester/constraints*.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install backtester --third-party-only

COPY libs ./libs
COPY backtester ./backtester
RUN --mount=type=cache,target=/root/.cache/pip \
    python scripts/python_environment.py install backtester

WORKDIR /app
COPY backtester /app

EXPOSE 8020

# Run the service
CMD ["python", "main.py"]
