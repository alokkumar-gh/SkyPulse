"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-30

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # 2. Table: users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('phone_number', sa.String(20), nullable=True),
        sa.Column('phone_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('role', sa.String(20), nullable=False, server_default='CITIZEN'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('PUBLIC','CITIZEN','ANALYST','ADMIN','GOVERNMENT')", name='check_user_role'),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])

    # 3. Table: sources
    op.create_table(
        'sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_type', sa.String(30), nullable=False),
        sa.Column('connector_class', sa.String(100), nullable=False),
        sa.Column('config', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('trust_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint("source_type IN ('WEATHER_API','PUBLIC_DATASET','RSS_FEED','CITIZEN','GOVERNMENT_API','DEMO')", name='check_source_type'),
        sa.CheckConstraint('trust_score BETWEEN 0.0 AND 1.0', name='check_source_trust_score'),
    )
    op.create_index('idx_sources_type', 'sources', ['source_type'])
    op.create_index('idx_sources_active', 'sources', ['is_active'])

    # 4. Table: source_reputation_history
    op.create_table(
        'source_reputation_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('old_score', sa.Float(), nullable=False),
        sa.Column('new_score', sa.Float(), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('triggering_event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint("outcome IN ('VERIFIED','LIKELY','UNVERIFIED','CONTRADICTED','REQUIRES_REVIEW')", name='check_rep_outcome'),
    )
    op.create_index('idx_src_rep_source', 'source_reputation_history', ['source_id'])
    op.create_index('idx_src_rep_recorded', 'source_reputation_history', ['recorded_at'])

    # 5. Table: connector_health
    op.create_table(
        'connector_health',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sources.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='UNKNOWN'),
        sa.Column('records_ingested_last_hour', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_check_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.CheckConstraint("status IN ('HEALTHY','DEGRADED','DOWN','UNKNOWN')", name='check_connector_health_status'),
    )

    # 6. Table: locations
    op.create_table(
        'locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('level', sa.String(10), nullable=False),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('district', sa.String(100), nullable=True),
        sa.Column('country', sa.String(10), nullable=False, server_default='IN'),
        sa.Column('boundary', Geometry('MULTIPOLYGON', srid=4326), nullable=True),
        sa.Column('centroid', Geometry('POINT', srid=4326), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('adjacent_location_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint("level IN ('CITY','DISTRICT','STATE','COUNTRY')", name='check_location_level'),
    )
    op.create_index('idx_loc_level', 'locations', ['level'])
    op.create_index('idx_loc_state', 'locations', ['state'])
    op.create_index('idx_loc_name', 'locations', ['name'])

    # 7. Table: weather_events
    op.create_table(
        'weather_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('category', sa.String(30), nullable=False),
        sa.Column('sub_category', sa.String(50), nullable=True),
        sa.Column('severity', sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('verification_status', sa.String(20), nullable=False, server_default='UNVERIFIED'),
        sa.Column('centroid_point', Geometry('POINT', srid=4326), nullable=True),
        sa.Column('centroid_lat', sa.Float(), nullable=True),
        sa.Column('centroid_lon', sa.Float(), nullable=True),
        sa.Column('primary_state', sa.String(100), nullable=True),
        sa.Column('primary_district', sa.String(100), nullable=True),
        sa.Column('primary_city', sa.String(100), nullable=True),
        sa.Column('first_reported_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evidence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_anomalous', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('anomaly_z_score', sa.Float(), nullable=True),
        sa.Column('is_demo', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('dweg_node_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint("category IN ('RAINFALL','THUNDERSTORM','FLOODING','HEATWAVE','FOG','DUST_STORM','STRONG_WINDS','UNKNOWN','SNOWFALL','HAILSTORM','CYCLONE','SMOG')", name='check_event_category'),
        sa.CheckConstraint('severity BETWEEN 1 AND 4', name='check_event_severity'),
        sa.CheckConstraint('confidence_score BETWEEN 0.0 AND 1.0', name='check_event_confidence'),
        sa.CheckConstraint("verification_status IN ('VERIFIED','LIKELY','UNVERIFIED','CONTRADICTED','REQUIRES_REVIEW')", name='check_event_status'),
    )
    op.create_index('idx_we_category', 'weather_events', ['category'])
    op.create_index('idx_we_status', 'weather_events', ['verification_status'])
    op.create_index('idx_we_state', 'weather_events', ['primary_state'])
    op.create_index('idx_we_district', 'weather_events', ['primary_district'])
    op.create_index('idx_we_first_reported', 'weather_events', ['first_reported_at'])
    op.create_index('idx_we_severity', 'weather_events', ['severity'])

    # 8. Table: weather_reports (Partitioned by RANGE ingested_at)
    op.execute("""
    CREATE TABLE weather_reports (
        id UUID NOT NULL DEFAULT uuid_generate_v4(),
        ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        source_id UUID NOT NULL REFERENCES sources(id),
        submitted_by UUID REFERENCES users(id),
        raw_content TEXT,
        normalized_text TEXT,
        primary_category VARCHAR(30) CHECK (primary_category IN (
            'RAINFALL','THUNDERSTORM','FLOODING','HEATWAVE','FOG','DUST_STORM','STRONG_WINDS','UNKNOWN',
            'SNOWFALL','HAILSTORM','CYCLONE','SMOG'
        )),
        sub_category VARCHAR(50),
        severity SMALLINT CHECK (severity BETWEEN 1 AND 4),
        classification_confidence FLOAT CHECK (classification_confidence BETWEEN 0.0 AND 1.0),
        classification_method VARCHAR(50),
        location_point GEOMETRY(Point, 4326),
        location_raw TEXT,
        location_lat DOUBLE PRECISION,
        location_lon DOUBLE PRECISION,
        location_city VARCHAR(100),
        location_district VARCHAR(100),
        location_state VARCHAR(100),
        location_confidence VARCHAR(10) CHECK (location_confidence IS NULL OR location_confidence IN ('HIGH','MEDIUM','LOW')),
        event_time TIMESTAMPTZ,
        is_duplicate BOOLEAN NOT NULL DEFAULT FALSE,
        canonical_event_id UUID,
        status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PROCESSING','PROCESSED','FAILED','FLAGGED')),
        is_demo BOOLEAN NOT NULL DEFAULT FALSE,
        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
        ai_extraction JSONB,
        metadata JSONB NOT NULL DEFAULT '{}',
        text_embedding vector(384),
        PRIMARY KEY (id, ingested_at)
    ) PARTITION BY RANGE (ingested_at);
    """)

    # Initial Monthly Partitions
    op.execute("""
    CREATE TABLE weather_reports_2026_09 PARTITION OF weather_reports
        FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');
    CREATE TABLE weather_reports_2026_10 PARTITION OF weather_reports
        FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');
    CREATE TABLE weather_reports_2026_11 PARTITION OF weather_reports
        FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');
    CREATE TABLE weather_reports_default PARTITION OF weather_reports DEFAULT;
    """)

    op.create_index('idx_wr_source', 'weather_reports', ['source_id'])
    op.create_index('idx_wr_canonical', 'weather_reports', ['canonical_event_id'])
    op.create_index('idx_wr_category', 'weather_reports', ['primary_category'])
    op.create_index('idx_wr_state', 'weather_reports', ['location_state'])
    op.create_index('idx_wr_district', 'weather_reports', ['location_district'])
    op.create_index('idx_wr_event_time', 'weather_reports', ['event_time'])
    op.create_index('idx_wr_status', 'weather_reports', ['status'])

    # 9. Table: event_evidence
    op.create_table(
        'event_evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('canonical_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('weather_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('weather_report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('corroboration_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('corroboration_type', sa.String(20), nullable=False, server_default='PRIMARY'),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint('corroboration_score BETWEEN 0.0 AND 1.0', name='check_corroboration_score'),
        sa.CheckConstraint("corroboration_type IN ('PRIMARY','CORROBORATING','CONTRADICTING')", name='check_corroboration_type'),
        sa.UniqueConstraint('canonical_event_id', 'weather_report_id', name='uq_event_report_evidence'),
    )
    op.create_index('idx_ee_event', 'event_evidence', ['canonical_event_id'])
    op.create_index('idx_ee_report', 'event_evidence', ['weather_report_id'])

    # 10. Table: media
    op.create_table(
        'media',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('weather_report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('media_type', sa.String(10), nullable=False, server_default='IMAGE'),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('storage_bucket', sa.String(100), nullable=False, server_default='skypulse-media'),
        sa.Column('original_filename', sa.String(255), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('phash', sa.String(64), nullable=True),
        sa.Column('image_analysis', postgresql.JSONB(), nullable=True),
        sa.Column('faces_detected', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_blurry', sa.Boolean(), nullable=True),
        sa.Column('is_processed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint("media_type IN ('IMAGE','VIDEO','AUDIO')", name='check_media_type'),
    )
    op.create_index('idx_media_report', 'media', ['weather_report_id'])
    op.create_index('idx_media_phash', 'media', ['phash'])
    op.create_index('idx_media_type', 'media', ['media_type'])

    # 11. Table: verification_results
    op.create_table(
        'verification_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('canonical_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('weather_events.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='UNVERIFIED'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('explanation_text', sa.Text(), nullable=False),
        sa.Column('evidence_items', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('signal_scores', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('method', sa.String(20), nullable=False, server_default='AI'),
        sa.Column('is_manual_override', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('manual_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint("status IN ('VERIFIED','LIKELY','UNVERIFIED','CONTRADICTED','REQUIRES_REVIEW')", name='check_vr_status'),
        sa.CheckConstraint('confidence_score BETWEEN 0.0 AND 1.0', name='check_vr_confidence'),
        sa.CheckConstraint("method IN ('AI','MANUAL','AI_CONFIRMED')", name='check_vr_method'),
    )
    op.create_index('idx_vr_event', 'verification_results', ['canonical_event_id'])
    op.create_index('idx_vr_status', 'verification_results', ['status'])

    # 12. Table: verification_evidence
    op.create_table(
        'verification_evidence',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('verification_result_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('verification_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evidence_type', sa.String(30), nullable=False),
        sa.Column('source_name', sa.String(200), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('weight_contribution', sa.Float(), nullable=True),
        sa.Column('raw_data', postgresql.JSONB(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint("evidence_type IN ('OFFICIAL_API','NEARBY_REPORT','SOURCE_TRUST','IMAGE_ANALYSIS','TEMPORAL_CONSISTENCY','HISTORICAL_BASELINE','ANALYST_NOTE')", name='check_ve_evidence_type'),
    )
    op.create_index('idx_ve_result', 'verification_evidence', ['verification_result_id'])

    # 13. Table: duplicate_clusters
    op.create_table(
        'duplicate_clusters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('canonical_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('weather_events.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('member_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('similarity_threshold', sa.Float(), nullable=False, server_default='0.75'),
        sa.Column('was_split', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('was_merged', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('merge_reason', sa.Text(), nullable=True),
        sa.Column('merged_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    # 14. Table: notifications
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('NEW_HIGH_SEVERITY_EVENT','REPORT_VERIFIED','REPORT_REJECTED','DWEG_PROPAGATION_ALERT','CONNECTOR_DOWN','QUEUE_DEPTH_ALERT','ASSIGNED_FOR_REVIEW','SYSTEM_HEALTH')", name='check_notif_type'),
    )
    op.create_index('idx_notif_user', 'notifications', ['user_id'])
    op.create_index('idx_notif_created', 'notifications', ['created_at'])

    # 15. Table: audit_logs (Partitioned by RANGE created_at)
    op.execute("""
    CREATE TABLE audit_logs (
        id BIGSERIAL NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        action_type VARCHAR(50) NOT NULL CHECK (action_type IN (
            'CREATE','UPDATE','DELETE','LOGIN','LOGOUT','VERIFY','REJECT','MERGE_CLUSTER',
            'SPLIT_CLUSTER','CONNECTOR_ENABLE','CONNECTOR_DISABLE','ROLE_CHANGE','EXPORT'
        )),
        entity_type VARCHAR(50) NOT NULL,
        entity_id UUID,
        old_value JSONB,
        new_value JSONB,
        ip_address INET,
        user_agent TEXT,
        PRIMARY KEY (id, created_at)
    ) PARTITION BY RANGE (created_at);
    """)

    # Initial Quarterly Partition for audit_logs
    op.execute("""
    CREATE TABLE audit_logs_2026_q3 PARTITION OF audit_logs
        FOR VALUES FROM ('2026-07-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');
    CREATE TABLE audit_logs_2026_q4 PARTITION OF audit_logs
        FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
    CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;
    """)

    op.create_index('idx_audit_user', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_entity', 'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_created', 'audit_logs', ['created_at'])
    op.create_index('idx_audit_action', 'audit_logs', ['action_type'])


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS audit_logs CASCADE')
    op.drop_table('notifications')
    op.drop_table('duplicate_clusters')
    op.drop_table('verification_evidence')
    op.drop_table('verification_results')
    op.drop_table('media')
    op.drop_table('event_evidence')
    op.execute('DROP TABLE IF EXISTS weather_reports CASCADE')
    op.drop_table('weather_events')
    op.drop_table('locations')
    op.drop_table('connector_health')
    op.drop_table('source_reputation_history')
    op.drop_table('sources')
    op.drop_table('users')
