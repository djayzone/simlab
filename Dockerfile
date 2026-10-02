FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    SIM_STATIC_ROOT=/app \
    SIM_DB_PATH=/data/sim.db

COPY . /app

RUN useradd --system --uid 10001 simlab \
    && mkdir -p /data \
    && chown -R simlab:simlab /app /data

USER simlab

EXPOSE 8080

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)" || exit 1

CMD ["python", "server.py"]
