FROM python:3.12-slim

WORKDIR /workspace/indicator-api

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Upgrade pip to latest version
RUN pip install --upgrade pip

COPY indicator-api/requirements.txt /workspace/indicator-api/requirements.txt
COPY libs/algotrader_logger /workspace/libs/algotrader_logger
COPY libs/db_accessor_client /workspace/libs/db_accessor_client
COPY libs/indicator_engine /workspace/libs/indicator_engine

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY indicator-api /app

EXPOSE 8010

CMD ["python", "main.py"]
