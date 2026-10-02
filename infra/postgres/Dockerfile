FROM postgis/postgis:16-3.4

LABEL maintainer="SkyPulse Platform Team"
LABEL description="PostgreSQL 16 with PostGIS 3.4 and pgvector extensions for SkyPulse"

# Install pgvector from PostgreSQL official repository (already configured in postgis base)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
