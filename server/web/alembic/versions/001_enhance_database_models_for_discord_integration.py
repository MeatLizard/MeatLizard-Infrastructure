"""enhance_database_models_for_discord_integration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table with enhanced fields
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('discord_id', sa.BigInteger(), nullable=True),
        sa.Column('display_label', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('discord_id')
    )
    
    # Create sessions table with enhanced fields
    op.create_table('sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('origin', sa.Enum('website', 'discord', name='sessionorigin'), nullable=False),
        sa.Column('discord_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('discord_channel_id')
    )
    
    # Create messages table
    op.create_table('messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('role', sa.Enum('user', 'assistant', 'system', name='messagerole'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('encrypted_content', sa.LargeBinary(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id')
    )
    
    # Create transcripts table
    op.create_table('transcripts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('s3_key', sa.String(length=500), nullable=True),
        sa.Column('format', sa.Enum('json', 'csv', name='transcriptformat'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create metrics table
    op.create_table('metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_bot_id', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('metric_type', sa.String(length=50), nullable=False),
        sa.Column('metric_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create system_configs table
    op.create_table('system_configs',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('key')
    )
    
    # Create backup_logs table
    op.create_table('backup_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('backup_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('started', 'in_progress', 'completed', 'failed', name='backupstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance optimization
    
    # User indexes
    op.create_index('idx_users_discord_id', 'users', ['discord_id'], unique=False)
    op.create_index('idx_users_active', 'users', ['is_active'], unique=False)
    
    # Session indexes
    op.create_index('idx_sessions_owner', 'sessions', ['owner_user_id'], unique=False)
    op.create_index('idx_sessions_origin', 'sessions', ['origin'], unique=False)
    op.create_index('idx_sessions_active', 'sessions', ['is_active'], unique=False)
    op.create_index('idx_sessions_created_at', 'sessions', ['created_at'], unique=False)
    op.create_index('idx_sessions_discord_channel', 'sessions', ['discord_channel_id'], unique=False)
    
    # Message indexes
    op.create_index('idx_messages_session', 'messages', ['session_id'], unique=False)
    op.create_index('idx_messages_timestamp', 'messages', ['timestamp'], unique=False)
    op.create_index('idx_messages_role', 'messages', ['role'], unique=False)
    op.create_index('idx_messages_request_id', 'messages', ['request_id'], unique=False)
    
    # Transcript indexes
    op.create_index('idx_transcripts_session', 'transcripts', ['session_id'], unique=False)
    op.create_index('idx_transcripts_created_at', 'transcripts', ['created_at'], unique=False)
    op.create_index('idx_transcripts_format', 'transcripts', ['format'], unique=False)
    
    # Metrics indexes
    op.create_index('idx_metrics_timestamp', 'metrics', ['timestamp'], unique=False)
    op.create_index('idx_metrics_type', 'metrics', ['metric_type'], unique=False)
    op.create_index('idx_metrics_client_bot', 'metrics', ['client_bot_id'], unique=False)
    
    # Backup log indexes
    op.create_index('idx_backup_logs_type', 'backup_logs', ['backup_type'], unique=False)
    op.create_index('idx_backup_logs_status', 'backup_logs', ['status'], unique=False)
    op.create_index('idx_backup_logs_started_at', 'backup_logs', ['started_at'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_backup_logs_started_at', table_name='backup_logs')
    op.drop_index('idx_backup_logs_status', table_name='backup_logs')
    op.drop_index('idx_backup_logs_type', table_name='backup_logs')
    op.drop_index('idx_metrics_client_bot', table_name='metrics')
    op.drop_index('idx_metrics_type', table_name='metrics')
    op.drop_index('idx_metrics_timestamp', table_name='metrics')
    op.drop_index('idx_transcripts_format', table_name='transcripts')
    op.drop_index('idx_transcripts_created_at', table_name='transcripts')
    op.drop_index('idx_transcripts_session', table_name='transcripts')
    op.drop_index('idx_messages_request_id', table_name='messages')
    op.drop_index('idx_messages_role', table_name='messages')
    op.drop_index('idx_messages_timestamp', table_name='messages')
    op.drop_index('idx_messages_session', table_name='messages')
    op.drop_index('idx_sessions_discord_channel', table_name='sessions')
    op.drop_index('idx_sessions_created_at', table_name='sessions')
    op.drop_index('idx_sessions_active', table_name='sessions')
    op.drop_index('idx_sessions_origin', table_name='sessions')
    op.drop_index('idx_sessions_owner', table_name='sessions')
    op.drop_index('idx_users_active', table_name='users')
    op.drop_index('idx_users_discord_id', table_name='users')
    
    # Drop tables
    op.drop_table('backup_logs')
    op.drop_table('system_configs')
    op.drop_table('metrics')
    op.drop_table('transcripts')
    op.drop_table('messages')
    op.drop_table('sessions')
    op.drop_table('users')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS backupstatus')
    op.execute('DROP TYPE IF EXISTS transcriptformat')
    op.execute('DROP TYPE IF EXISTS messagerole')
    op.execute('DROP TYPE IF EXISTS sessionorigin')