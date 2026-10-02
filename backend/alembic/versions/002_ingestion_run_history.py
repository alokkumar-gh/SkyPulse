"""002_ingestion_run_history

Revision ID: 002_ingestion_run_history
Revises: 001_initial_schema
Create Date: 2026-10-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_ingestion_run_history'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table: ingestion_runs
    op.create_table(
        'ingestion_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('run_id', sa.String(64), nullable=False, unique=True),
        sa.Column('connector_id', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('source_family', sa.String(50), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_ms', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        
        # 10-Stage Pipeline Telemetry Counters
        sa.Column('records_fetched', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('weather_relevant', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('india_valid', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('unknown_location', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('quarantined', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('duplicates', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('accepted', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('classified', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('verified', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('failed', sa.Integer(), nullable=False, server_default=sa.text('0')),
        
        # Error diagnostics
        sa.Column('error_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('errors_json', sa.JSON(), nullable=True),
        sa.Column('payload_archive_key', sa.String(255), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_index('idx_ingestion_runs_run_id', 'ingestion_runs', ['run_id'], unique=True)
    op.create_index('idx_ingestion_runs_conn_started', 'ingestion_runs', ['connector_id', 'started_at'])
    op.create_index('idx_ingestion_runs_family_started', 'ingestion_runs', ['source_family', 'started_at'])
    op.create_index('idx_ingestion_runs_status', 'ingestion_runs', ['status'])
    op.create_index('idx_ingestion_runs_started', 'ingestion_runs', ['started_at'])

    # 2. Table: ingestion_payload_archives
    op.create_table(
        'ingestion_payload_archives',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('run_id', sa.String(64), nullable=False),
        sa.Column('connector_id', sa.String(100), nullable=False),
        sa.Column('storage_provider', sa.String(30), nullable=False, server_default='MINIO'),
        sa.Column('object_key', sa.String(500), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )

    op.create_index('idx_payload_archive_run', 'ingestion_payload_archives', ['run_id'])
    op.create_index('idx_payload_archive_connector', 'ingestion_payload_archives', ['connector_id'])


def downgrade() -> None:
    op.drop_table('ingestion_payload_archives')
    op.drop_table('ingestion_runs')
