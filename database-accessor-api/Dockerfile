FROM python:3.12-alpine

RUN apk add --no-cache curl

WORKDIR /workspace
COPY constraints-shared.txt ./
COPY scripts/python_environment.py ./scripts/python_environment.py
COPY libs ./libs
COPY database-accessor-api ./database-accessor-api
RUN python scripts/python_environment.py install database-accessor-api

WORKDIR /app
COPY database-accessor-api /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
