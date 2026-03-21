FROM python:3.12-slim

WORKDIR /workspace/broker-service

# Install system dependencies if needed
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY broker-service/requirements.txt /workspace/broker-service/requirements.txt
COPY libs/algotrader_logger /workspace/libs/algotrader_logger
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
# Copy application code
COPY broker-service /app

# Expose the port the app runs on
EXPOSE 8050

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050", "--reload"]
