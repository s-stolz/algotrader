FROM python:3.15.2-slim

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
COPY libs ./libs
COPY backtester ./backtester
RUN python scripts/python_environment.py install backtester

WORKDIR /app
COPY backtester /app

EXPOSE 8020

# Run the service
CMD ["python", "main.py"]
