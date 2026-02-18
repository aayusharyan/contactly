# Multi-stage Docker container for a contact synchronization service.
# Syncs Google and iCloud contacts with a PBX database for caller ID name lookup.
# Uses Python 3.11 slim base image for minimal footprint.
# Includes health checks to verify sync operations are running successfully.

FROM python:3.11-slim

LABEL maintainer="Aayush Sinha <hello@yush.dev>"
LABEL description="Contactly - Syncs Google and iCloud contacts with PBX database for caller ID name lookup"
LABEL version="1.1.0"

WORKDIR /app

# Install system-level dependencies required for MySQL client and Python compilation.
# gcc: Required to compile certain Python packages
# default-libmysqlclient-dev: MySQL client library for database connectivity
# pkg-config: Helper tool to compile applications and libraries
# Clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY docker/entrypoint.sh /app/entrypoint.sh

# Create data directory for SQLite database persistence and make entrypoint executable.
RUN mkdir -p /app/data && chmod +x /app/entrypoint.sh

# Configure Python to output logs immediately and set SQLite database path.
# PYTHONUNBUFFERED ensures logs are visible in real-time for Docker logs
ENV PYTHONUNBUFFERED=1 \
    LOCAL_DB_PATH=sqlite:////app/data/contacts_sync.db

# Verify that at least one sync has succeeded in the last 12 hours.
# Checks SyncState table for recent successful sync operations.
# Runs every hour with a 10-second timeout and 30-second startup grace period.
HEALTHCHECK --interval=1h --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from src.internal_db.schema import SyncState; from src.internal_db import get_session; \
    from datetime import datetime, timedelta; \
    with get_session() as s: \
        states = s.query(SyncState).all(); \
        recent = any(st.last_success_at and (datetime.utcnow() - st.last_success_at) < timedelta(hours=12) for st in states); \
        exit(0 if recent else 1)" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["python", "-m", "src.cli.scheduler"]
