"""add_multi_service_platform_models

Revision ID: 005
Revises: 004
Create Date: 2024-01-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update tier_configurations table with multi-service platform features
    op.add_column('tier_configurations', sa.Column('url_shortener_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tier_configurations', sa.Column('max_short_urls', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('tier_configurations', sa.Column('custom_vanity_slugs', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tier_configurations', sa.Column('pastebin_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tier_configurations', sa.Column('max_pastes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('tier_configurations', sa.Column('max_paste_ttl_days', sa.Integer(), nullable=False, server_default='30'))
    op.add_column('tier_configurations', sa.Column('private_pastes', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tier_configurations', sa.Column('media_upload_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tier_configurations', sa.Column('media_storage_quota_gb', sa.Integer(), nullable=False, server_default='0'))
    
    # Create enum types
    # op.execute("CREATE TYPE pasteprivacylevel AS ENUM ('public', 'private', 'password')")
    # op.execute("CREATE TYPE mediaprocessingstatus AS ENUM ('pending', 'processing', 'completed', 'failed')")
    
    # Create short_urls table
    op.create_table('short_urls',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('target_url', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_custom_slug', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('max_clicks', sa.Integer(), nullable=True),
        sa.Column('current_clicks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    
    # Create short_url_access_logs table
    op.create_table('short_url_access_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('short_url_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('referrer', sa.Text(), nullable=True),
        sa.Column('country_code', sa.String(length=2), nullable=True),
        sa.Column('accessed_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['short_url_id'], ['short_urls.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create pastes table
    op.create_table('pastes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('paste_id', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=50), nullable=True),
        sa.Column('privacy_level', sa.Enum('public', 'private', 'password', name='pasteprivacylevel'), nullable=False, server_default='public'),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('max_views', sa.Integer(), nullable=True),
        sa.Column('current_views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('paste_id')
    )
    
    # Create paste_access_logs table
    op.create_table('paste_access_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('paste_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('accessed_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['paste_id'], ['pastes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create media_files table
    op.create_table('media_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('media_id', sa.String(length=10), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('thumbnail_path', sa.Text(), nullable=True),
        sa.Column('hls_playlist_path', sa.Text(), nullable=True),
        sa.Column('privacy_level', sa.Enum('public', 'private', 'password', name='pasteprivacylevel'), nullable=False, server_default='public'),
        sa.Column('processing_status', sa.Enum('pending', 'processing', 'completed', 'failed', name='mediaprocessingstatus'), nullable=False, server_default='pending'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('media_id')
    )
    
    # Create playlists table
    op.create_table('playlists',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create playlist_items table
    op.create_table('playlist_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('playlist_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('media_file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id'], ),
        sa.ForeignKeyConstraint(['media_file_id'], ['media_files.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create media_comments table
    op.create_table('media_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('media_file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['media_file_id'], ['media_files.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create media_likes table
    op.create_table('media_likes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('media_file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_like', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['media_file_id'], ['media_files.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('media_file_id', 'user_id', name='unique_media_user_like')
    )
    
    # Create user_storage_usage table
    op.create_table('user_storage_usage',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('used_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('quota_bytes', sa.BigInteger(), nullable=False),
        sa.Column('last_calculated', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    # Create indexes for performance
    
    # Short URLs indexes
    op.create_index('idx_short_urls_user', 'short_urls', ['user_id'], unique=False)
    op.create_index('idx_short_urls_slug', 'short_urls', ['slug'], unique=False)
    op.create_index('idx_short_urls_active', 'short_urls', ['is_active'], unique=False)
    op.create_index('idx_short_urls_expires', 'short_urls', ['expires_at'], unique=False)
    op.create_index('idx_short_urls_created', 'short_urls', ['created_at'], unique=False)
    
    # Short URL access logs indexes
    op.create_index('idx_short_url_access_logs_url', 'short_url_access_logs', ['short_url_id'], unique=False)
    op.create_index('idx_short_url_access_logs_accessed', 'short_url_access_logs', ['accessed_at'], unique=False)
    op.create_index('idx_short_url_access_logs_ip', 'short_url_access_logs', ['ip_hash'], unique=False)
    
    # Pastes indexes
    op.create_index('idx_pastes_user', 'pastes', ['user_id'], unique=False)
    op.create_index('idx_pastes_paste_id', 'pastes', ['paste_id'], unique=False)
    op.create_index('idx_pastes_active', 'pastes', ['is_active'], unique=False)
    op.create_index('idx_pastes_privacy', 'pastes', ['privacy_level'], unique=False)
    op.create_index('idx_pastes_expires', 'pastes', ['expires_at'], unique=False)
    op.create_index('idx_pastes_created', 'pastes', ['created_at'], unique=False)
    
    # Paste access logs indexes
    op.create_index('idx_paste_access_logs_paste', 'paste_access_logs', ['paste_id'], unique=False)
    op.create_index('idx_paste_access_logs_accessed', 'paste_access_logs', ['accessed_at'], unique=False)
    
    # Media files indexes
    op.create_index('idx_media_files_user', 'media_files', ['user_id'], unique=False)
    op.create_index('idx_media_files_media_id', 'media_files', ['media_id'], unique=False)
    op.create_index('idx_media_files_active', 'media_files', ['is_active'], unique=False)
    op.create_index('idx_media_files_privacy', 'media_files', ['privacy_level'], unique=False)
    op.create_index('idx_media_files_status', 'media_files', ['processing_status'], unique=False)
    op.create_index('idx_media_files_created', 'media_files', ['created_at'], unique=False)
    op.create_index('idx_media_files_mime_type', 'media_files', ['mime_type'], unique=False)
    
    # Playlists indexes
    op.create_index('idx_playlists_user', 'playlists', ['user_id'], unique=False)
    op.create_index('idx_playlists_public', 'playlists', ['is_public'], unique=False)
    op.create_index('idx_playlists_created', 'playlists', ['created_at'], unique=False)
    
    # Playlist items indexes
    op.create_index('idx_playlist_items_playlist', 'playlist_items', ['playlist_id'], unique=False)
    op.create_index('idx_playlist_items_media', 'playlist_items', ['media_file_id'], unique=False)
    op.create_index('idx_playlist_items_position', 'playlist_items', ['position'], unique=False)
    
    # Media comments indexes
    op.create_index('idx_media_comments_media', 'media_comments', ['media_file_id'], unique=False)
    op.create_index('idx_media_comments_user', 'media_comments', ['user_id'], unique=False)
    op.create_index('idx_media_comments_approved', 'media_comments', ['is_approved'], unique=False)
    op.create_index('idx_media_comments_created', 'media_comments', ['created_at'], unique=False)
    
    # Media likes indexes
    op.create_index('idx_media_likes_media', 'media_likes', ['media_file_id'], unique=False)
    op.create_index('idx_media_likes_user', 'media_likes', ['user_id'], unique=False)
    op.create_index('idx_media_likes_created', 'media_likes', ['created_at'], unique=False)
    
    # User storage usage indexes
    op.create_index('idx_user_storage_usage_user', 'user_storage_usage', ['user_id'], unique=False)
    op.create_index('idx_user_storage_usage_calculated', 'user_storage_usage', ['last_calculated'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_user_storage_usage_calculated', table_name='user_storage_usage')
    op.drop_index('idx_user_storage_usage_user', table_name='user_storage_usage')
    
    op.drop_index('idx_media_likes_created', table_name='media_likes')
    op.drop_index('idx_media_likes_user', table_name='media_likes')
    op.drop_index('idx_media_likes_media', table_name='media_likes')
    
    op.drop_index('idx_media_comments_created', table_name='media_comments')
    op.drop_index('idx_media_comments_approved', table_name='media_comments')
    op.drop_index('idx_media_comments_user', table_name='media_comments')
    op.drop_index('idx_media_comments_media', table_name='media_comments')
    
    op.drop_index('idx_playlist_items_position', table_name='playlist_items')
    op.drop_index('idx_playlist_items_media', table_name='playlist_items')
    op.drop_index('idx_playlist_items_playlist', table_name='playlist_items')
    
    op.drop_index('idx_playlists_created', table_name='playlists')
    op.drop_index('idx_playlists_public', table_name='playlists')
    op.drop_index('idx_playlists_user', table_name='playlists')
    
    op.drop_index('idx_media_files_mime_type', table_name='media_files')
    op.drop_index('idx_media_files_created', table_name='media_files')
    op.drop_index('idx_media_files_status', table_name='media_files')
    op.drop_index('idx_media_files_privacy', table_name='media_files')
    op.drop_index('idx_media_files_active', table_name='media_files')
    op.drop_index('idx_media_files_media_id', table_name='media_files')
    op.drop_index('idx_media_files_user', table_name='media_files')
    
    op.drop_index('idx_paste_access_logs_accessed', table_name='paste_access_logs')
    op.drop_index('idx_paste_access_logs_paste', table_name='paste_access_logs')
    
    op.drop_index('idx_pastes_created', table_name='pastes')
    op.drop_index('idx_pastes_expires', table_name='pastes')
    op.drop_index('idx_pastes_privacy', table_name='pastes')
    op.drop_index('idx_pastes_active', table_name='pastes')
    op.drop_index('idx_pastes_paste_id', table_name='pastes')
    op.drop_index('idx_pastes_user', table_name='pastes')
    
    op.drop_index('idx_short_url_access_logs_ip', table_name='short_url_access_logs')
    op.drop_index('idx_short_url_access_logs_accessed', table_name='short_url_access_logs')
    op.drop_index('idx_short_url_access_logs_url', table_name='short_url_access_logs')
    
    op.drop_index('idx_short_urls_created', table_name='short_urls')
    op.drop_index('idx_short_urls_expires', table_name='short_urls')
    op.drop_index('idx_short_urls_active', table_name='short_urls')
    op.drop_index('idx_short_urls_slug', table_name='short_urls')
    op.drop_index('idx_short_urls_user', table_name='short_urls')
    
    # Drop tables
    op.drop_table('user_storage_usage')
    op.drop_table('media_likes')
    op.drop_table('media_comments')
    op.drop_table('playlist_items')
    op.drop_table('playlists')
    op.drop_table('media_files')
    op.drop_table('paste_access_logs')
    op.drop_table('pastes')
    op.drop_table('short_url_access_logs')
    op.drop_table('short_urls')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS mediaprocessingstatus')
    op.execute('DROP TYPE IF EXISTS pasteprivacylevel')
    
    # Remove columns from tier_configurations
    op.drop_column('tier_configurations', 'media_storage_quota_gb')
    op.drop_column('tier_configurations', 'media_upload_enabled')
    op.drop_column('tier_configurations', 'private_pastes')
    op.drop_column('tier_configurations', 'max_paste_ttl_days')
    op.drop_column('tier_configurations', 'max_pastes')
    op.drop_column('tier_configurations', 'pastebin_enabled')
    op.drop_column('tier_configurations', 'custom_vanity_slugs')
    op.drop_column('tier_configurations', 'max_short_urls')
    op.drop_column('tier_configurations', 'url_shortener_enabled')