FROM python:3.12-slim

RUN apt-get update && apt-get install -y gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
COPY libs ./libs
COPY realtime-service ./realtime-service
RUN python scripts/python_environment.py install realtime-service

WORKDIR /app
COPY realtime-service /app

EXPOSE 8765 8080

CMD ["python", "-u", "main.py"]
