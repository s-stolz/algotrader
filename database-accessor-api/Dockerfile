FROM python:3.11-alpine

RUN apk update && apk upgrade --no-cache && apk add --no-cache curl

WORKDIR /workspace/database-accessor-api

COPY database-accessor-api/requirements.txt /workspace/database-accessor-api/requirements.txt
COPY libs/algotrader_logger /workspace/libs/algotrader_logger
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY database-accessor-api /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
