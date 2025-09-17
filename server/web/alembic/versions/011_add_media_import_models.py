"""add_media_import_models

Revision ID: 011_add_media_import_models
Revises: 010_add_content_moderation_tables
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_add_media_import_models'
down_revision = '010_add_content_moderation_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create import_status enum
    import_status_enum = postgresql.ENUM('queued', 'downloading', 'processing', 'completed', 'failed', name='importstatus')
    import_status_enum.create(op.get_bind())
    
    # Create import_jobs table
    op.create_table('import_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_url', sa.String(length=2000), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('import_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('requested_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('queued', 'downloading', 'processing', 'completed', 'failed', name='importstatus'), nullable=False),
        sa.Column('progress_percent', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('original_title', sa.String(length=500), nullable=True),
        sa.Column('original_description', sa.Text(), nullable=True),
        sa.Column('original_uploader', sa.String(length=200), nullable=True),
        sa.Column('original_upload_date', sa.DateTime(), nullable=True),
        sa.Column('original_duration', sa.Integer(), nullable=True),
        sa.Column('original_view_count', sa.Integer(), nullable=True),
        sa.Column('original_like_count', sa.Integer(), nullable=True),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('downloaded_file_path', sa.String(length=1000), nullable=True),
        sa.Column('discord_channel_id', sa.String(length=50), nullable=True),
        sa.Column('discord_message_id', sa.String(length=50), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_import_jobs_created_at'), 'import_jobs', ['created_at'], unique=False)
    op.create_index(op.f('ix_import_jobs_platform'), 'import_jobs', ['platform'], unique=False)
    op.create_index(op.f('ix_import_jobs_requested_by'), 'import_jobs', ['requested_by'], unique=False)
    op.create_index(op.f('ix_import_jobs_status'), 'import_jobs', ['status'], unique=False)
    
    # Create import_presets table
    op.create_table('import_presets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_import_presets_created_at'), 'import_presets', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_index(op.f('ix_import_presets_created_at'), table_name='import_presets')
    op.drop_table('import_presets')
    
    op.drop_index(op.f('ix_import_jobs_status'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_requested_by'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_platform'), table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_created_at'), table_name='import_jobs')
    op.drop_table('import_jobs')
    
    # Drop enum
    import_status_enum = postgresql.ENUM('queued', 'downloading', 'processing', 'completed', 'failed', name='importstatus')
    import_status_enum.drop(op.get_bind())