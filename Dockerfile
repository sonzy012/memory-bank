FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends cron git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .

RUN echo "*/30 * * * * /usr/local/bin/membank ingest --sessions-dir /data/sessions >> /var/log/membank-cron.log 2>&1" \
    | crontab -

ENV MEMBANK_DB_PATH=/data/db/membank.db
ENV MEMBANK_SESSIONS_DIR=/data/sessions

EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
    CMD membank --help || exit 1

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
