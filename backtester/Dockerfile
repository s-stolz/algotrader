FROM python:3.12-slim

WORKDIR /app

# Upgrade pip to latest version
RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["watchmedo", "auto-restart", "--directory=/app", "--pattern=*.py", "--recursive", "--", "python", "main.py"]