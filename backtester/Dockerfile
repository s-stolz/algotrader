FROM python:3.10

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

COPY wait-for-it.sh ./wait-for-it.sh
RUN chmod +x ./wait-for-it.sh

# Copy and set the entrypoint script
COPY ./entrypoint-backtester.sh /entrypoint-backtester.sh
RUN chmod +x /entrypoint-backtester.sh
ENTRYPOINT ["/entrypoint-backtester.sh"]