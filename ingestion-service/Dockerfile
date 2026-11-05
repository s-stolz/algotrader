FROM python:3.12-slim

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
COPY libs ./libs
COPY ingestion-service ./ingestion-service
RUN python scripts/python_environment.py install ingestion-service

WORKDIR /app
COPY ingestion-service /app

# Run the service
CMD ["python", "main.py"]
