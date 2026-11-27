FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEBHOOK_PORT=8080 \
    WEBHOOK_DB=/data/history.db

RUN useradd --system --uid 10001 --no-create-home webhook \
    && mkdir /data \
    && chown webhook:webhook /data

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py store.py history.py schema.sql schema_pg.sql ./

USER webhook
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4)"]

CMD ["python", "app.py"]
