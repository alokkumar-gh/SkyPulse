-- SkyPulse Extension Initialization Script
-- Executed on fresh PostgreSQL database initialization

\echo 'Installing required SkyPulse PostgreSQL extensions...'

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verify extensions
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN
        RAISE EXCEPTION 'CRITICAL: postgis extension is missing!';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'CRITICAL: vector extension is missing!';
    END IF;
    RAISE NOTICE 'SUCCESS: postgis and vector extensions verified.';
END $$;
