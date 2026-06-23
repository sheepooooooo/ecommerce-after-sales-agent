FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY data/policies ./data/policies
COPY README.md ./

RUN mkdir -p /app/data/indexes /app/logs

EXPOSE 8011

CMD ["sh", "-c", "python scripts/bootstrap_runtime.py && python -m uvicorn app.api_server:app --host 0.0.0.0 --port 8011"]
