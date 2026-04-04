FROM python:3.11-slim
WORKDIR /workspace/webserver

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY webserver/requirements.txt ./
COPY libs/algotrader_logger /workspace/libs/algotrader_logger
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
# Copy application code
COPY webserver /app

EXPOSE 8765 8080

CMD ["python", "-u", "main.py"]
