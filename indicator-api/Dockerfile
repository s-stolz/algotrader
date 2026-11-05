FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
COPY libs ./libs
COPY indicator-api ./indicator-api
RUN python scripts/python_environment.py install indicator-api

WORKDIR /app
COPY indicator-api /app

EXPOSE 8010

CMD ["python", "main.py"]
