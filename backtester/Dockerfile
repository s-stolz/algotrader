FROM python:3.12-slim

WORKDIR /workspace/backtester

# Upgrade pip to latest version
RUN pip install --upgrade pip

# Install dependencies
COPY backtester/requirements.txt /workspace/backtester/requirements.txt
COPY libs/db_accessor_client /workspace/libs/db_accessor_client
COPY libs/indicator_engine /workspace/libs/indicator_engine
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app

# Copy application code
COPY backtester /app

EXPOSE 8020

# Run the service
CMD ["python", "main.py"]
