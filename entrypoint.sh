#!/bin/bash
set -e

# Run initial ingestion
membank ingest --sessions-dir "${MEMBANK_SESSIONS_DIR:-/data/sessions}" || true

# Start cron daemon
cron

# Keep container alive and tail the cron log
touch /var/log/membank-cron.log
exec tail -f /var/log/membank-cron.log
