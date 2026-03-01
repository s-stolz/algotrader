FROM python:3.12-slim

WORKDIR /workspace/ingestion-service

# Upgrade pip
RUN pip install --upgrade pip

# Install dependencies
COPY ingestion-service /workspace/ingestion-service
COPY libs/db_accessor_client /workspace/libs/db_accessor_client
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

# Copy application code
COPY ingestion-service /app

# Run the service
CMD ["python", "main.py"]
