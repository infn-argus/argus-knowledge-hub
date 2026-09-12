FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/infn-argus/argus-knowledge-hub"
LABEL org.opencontainers.image.description="ARGUS Knowledge Hub — REST API (assets, tickets, documentation)"
LABEL org.opencontainers.image.licenses="INFN"


WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY alembic alembic
COPY alembic.ini .
COPY scripts scripts

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
