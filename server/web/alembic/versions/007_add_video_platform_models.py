"""add_video_platform_models

Revision ID: 007
Revises: 006
Create Date: 2025-01-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Create video status enum
    video_status_enum = postgresql.ENUM(
        'uploading', 'processing', 'transcoding', 'ready', 'failed', 'deleted',
        name='videostatus'
    )
    video_status_enum.create(op.get_bind())
    
    # Create video visibility enum
    video_visibility_enum = postgresql.ENUM(
        'public', 'unlisted', 'private',
        name='videovisibility'
    )
    video_visibility_enum.create(op.get_bind())
    
    # Create transcoding status enum
    transcoding_status_enum = postgresql.ENUM(
        'queued', 'processing', 'completed', 'failed',
        name='transcodingstatus'
    )
    transcoding_status_enum.create(op.get_bind())
    
    # Create videos table
    op.create_table('videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('original_s3_key', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('source_resolution', sa.String(length=20), nullable=True),
        sa.Column('source_framerate', sa.Integer(), nullable=True),
        sa.Column('source_codec', sa.String(length=50), nullable=True),
        sa.Column('source_bitrate', sa.Integer(), nullable=True),
        sa.Column('status', video_status_enum, nullable=False),
        sa.Column('visibility', video_visibility_enum, nullable=False),
        sa.Column('thumbnail_s3_key', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for videos table
    op.create_index(op.f('ix_videos_creator_id'), 'videos', ['creator_id'], unique=False)
    op.create_index(op.f('ix_videos_status'), 'videos', ['status'], unique=False)
    op.create_index(op.f('ix_videos_visibility'), 'videos', ['visibility'], unique=False)
    op.create_index(op.f('ix_videos_created_at'), 'videos', ['created_at'], unique=False)
    
    # Create transcoding_jobs table
    op.create_table('transcoding_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quality_preset', sa.String(length=20), nullable=False),
        sa.Column('target_resolution', sa.String(length=20), nullable=False),
        sa.Column('target_framerate', sa.Integer(), nullable=False),
        sa.Column('target_bitrate', sa.Integer(), nullable=False),
        sa.Column('status', transcoding_status_enum, nullable=False),
        sa.Column('progress_percent', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('output_s3_key', sa.String(length=500), nullable=True),
        sa.Column('hls_manifest_s3_key', sa.String(length=500), nullable=True),
        sa.Column('output_file_size', sa.BigInteger(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for transcoding_jobs table
    op.create_index(op.f('ix_transcoding_jobs_video_id'), 'transcoding_jobs', ['video_id'], unique=False)
    op.create_index(op.f('ix_transcoding_jobs_status'), 'transcoding_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_transcoding_jobs_created_at'), 'transcoding_jobs', ['created_at'], unique=False)
    
    # Create view_sessions table
    op.create_table('view_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_token', sa.String(length=100), nullable=False),
        sa.Column('ip_address_hash', sa.String(length=64), nullable=True),
        sa.Column('user_agent_hash', sa.String(length=64), nullable=True),
        sa.Column('current_position_seconds', sa.Integer(), nullable=False),
        sa.Column('total_watch_time_seconds', sa.Integer(), nullable=False),
        sa.Column('completion_percentage', sa.Integer(), nullable=False),
        sa.Column('qualities_used', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('quality_switches', sa.Integer(), nullable=False),
        sa.Column('buffering_events', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for view_sessions table
    op.create_index(op.f('ix_view_sessions_video_id'), 'view_sessions', ['video_id'], unique=False)
    op.create_index(op.f('ix_view_sessions_user_id'), 'view_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_view_sessions_session_token'), 'view_sessions', ['session_token'], unique=True)
    op.create_index(op.f('ix_view_sessions_started_at'), 'view_sessions', ['started_at'], unique=False)
    
    # Create video_comments table
    op.create_table('video_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parent_comment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['parent_comment_id'], ['video_comments.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for video_comments table
    op.create_index(op.f('ix_video_comments_video_id'), 'video_comments', ['video_id'], unique=False)
    op.create_index(op.f('ix_video_comments_user_id'), 'video_comments', ['user_id'], unique=False)
    op.create_index(op.f('ix_video_comments_parent_comment_id'), 'video_comments', ['parent_comment_id'], unique=False)
    op.create_index(op.f('ix_video_comments_created_at'), 'video_comments', ['created_at'], unique=False)
    
    # Create video_likes table
    op.create_table('video_likes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_like', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id', 'user_id', name='uq_video_user_like')
    )
    
    # Create indexes for video_likes table
    op.create_index(op.f('ix_video_likes_video_id'), 'video_likes', ['video_id'], unique=False)
    op.create_index(op.f('ix_video_likes_user_id'), 'video_likes', ['user_id'], unique=False)
    op.create_index(op.f('ix_video_likes_created_at'), 'video_likes', ['created_at'], unique=False)


def downgrade():
    # Drop tables in reverse order
    op.drop_index(op.f('ix_video_likes_created_at'), table_name='video_likes')
    op.drop_index(op.f('ix_video_likes_user_id'), table_name='video_likes')
    op.drop_index(op.f('ix_video_likes_video_id'), table_name='video_likes')
    op.drop_table('video_likes')
    
    op.drop_index(op.f('ix_video_comments_created_at'), table_name='video_comments')
    op.drop_index(op.f('ix_video_comments_parent_comment_id'), table_name='video_comments')
    op.drop_index(op.f('ix_video_comments_user_id'), table_name='video_comments')
    op.drop_index(op.f('ix_video_comments_video_id'), table_name='video_comments')
    op.drop_table('video_comments')
    
    op.drop_index(op.f('ix_view_sessions_started_at'), table_name='view_sessions')
    op.drop_index(op.f('ix_view_sessions_session_token'), table_name='view_sessions')
    op.drop_index(op.f('ix_view_sessions_user_id'), table_name='view_sessions')
    op.drop_index(op.f('ix_view_sessions_video_id'), table_name='view_sessions')
    op.drop_table('view_sessions')
    
    op.drop_index(op.f('ix_transcoding_jobs_created_at'), table_name='transcoding_jobs')
    op.drop_index(op.f('ix_transcoding_jobs_status'), table_name='transcoding_jobs')
    op.drop_index(op.f('ix_transcoding_jobs_video_id'), table_name='transcoding_jobs')
    op.drop_table('transcoding_jobs')
    
    op.drop_index(op.f('ix_videos_created_at'), table_name='videos')
    op.drop_index(op.f('ix_videos_visibility'), table_name='videos')
    op.drop_index(op.f('ix_videos_status'), table_name='videos')
    op.drop_index(op.f('ix_videos_creator_id'), table_name='videos')
    op.drop_table('videos')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS transcodingstatus')
    op.execute('DROP TYPE IF EXISTS videovisibility')
    op.execute('DROP TYPE IF EXISTS videostatus')