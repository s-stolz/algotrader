FROM python:3.12-slim

RUN apt-get update && apt-get install -y gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
COPY libs ./libs
COPY broker-service ./broker-service
RUN python scripts/python_environment.py install broker-service

WORKDIR /app
COPY broker-service /app

EXPOSE 8050

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8050", "--reload"]
