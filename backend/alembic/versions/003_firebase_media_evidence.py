"""add firebase media evidence and cloud storage fields

Revision ID: 003
Revises: 002
Create Date: 2026-10-02 17:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002_ingestion_run_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new cloud storage, evidence provenance, and lifecycle columns to media table
    with op.batch_alter_table('media', schema=None) as batch_op:
        batch_op.add_column(sa.Column('citizen_id', postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column('evidence_id', postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column('storage_provider', sa.String(length=30), nullable=False, server_default='FIREBASE'))
        batch_op.add_column(sa.Column('storage_path', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('safe_filename', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('content_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('upload_status', sa.String(length=30), nullable=False, server_default='UPLOADED'))
        batch_op.add_column(sa.Column('thumbnail_path', sa.String(length=500), nullable=True))

        # Indexes
        batch_op.create_index('idx_media_citizen_id', ['citizen_id'])
        batch_op.create_index('idx_media_content_hash', ['content_hash'])
        batch_op.create_index('idx_media_upload_status', ['upload_status'])
        batch_op.create_index('idx_media_storage_provider', ['storage_provider'])


def downgrade() -> None:
    with op.batch_alter_table('media', schema=None) as batch_op:
        batch_op.drop_index('idx_media_storage_provider')
        batch_op.drop_index('idx_media_upload_status')
        batch_op.drop_index('idx_media_content_hash')
        batch_op.drop_index('idx_media_citizen_id')

        batch_op.drop_column('thumbnail_path')
        batch_op.drop_column('upload_status')
        batch_op.drop_column('content_hash')
        batch_op.drop_column('safe_filename')
        batch_op.drop_column('storage_path')
        batch_op.drop_column('storage_provider')
        batch_op.drop_column('evidence_id')
        batch_op.drop_column('event_id')
        batch_op.drop_column('citizen_id')
