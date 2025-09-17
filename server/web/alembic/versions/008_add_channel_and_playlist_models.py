"""add_channel_and_playlist_models

Revision ID: 008
Revises: 007
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create channels table
    op.create_table('channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('visibility', sa.Enum('public', 'unlisted', 'private', name='videovisibility'), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('banner_s3_key', sa.String(length=500), nullable=True),
        sa.Column('avatar_s3_key', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_channels_category'), 'channels', ['category'], unique=False)
    op.create_index(op.f('ix_channels_created_at'), 'channels', ['created_at'], unique=False)
    op.create_index(op.f('ix_channels_creator_id'), 'channels', ['creator_id'], unique=False)
    op.create_index(op.f('ix_channels_slug'), 'channels', ['slug'], unique=True)
    op.create_index(op.f('ix_channels_visibility'), 'channels', ['visibility'], unique=False)

    # Create video_playlists table
    op.create_table('video_playlists',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('visibility', sa.Enum('public', 'unlisted', 'private', name='videovisibility'), nullable=False),
        sa.Column('auto_advance', sa.Boolean(), nullable=False),
        sa.Column('shuffle_enabled', sa.Boolean(), nullable=False),
        sa.Column('thumbnail_s3_key', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_video_playlists_channel_id'), 'video_playlists', ['channel_id'], unique=False)
    op.create_index(op.f('ix_video_playlists_created_at'), 'video_playlists', ['created_at'], unique=False)
    op.create_index(op.f('ix_video_playlists_creator_id'), 'video_playlists', ['creator_id'], unique=False)
    op.create_index(op.f('ix_video_playlists_visibility'), 'video_playlists', ['visibility'], unique=False)

    # Create video_playlist_items table
    op.create_table('video_playlist_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('playlist_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['playlist_id'], ['video_playlists.id'], ),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('playlist_id', 'position', name='uq_playlist_position')
    )
    op.create_index(op.f('ix_video_playlist_items_playlist_id'), 'video_playlist_items', ['playlist_id'], unique=False)
    op.create_index(op.f('ix_video_playlist_items_video_id'), 'video_playlist_items', ['video_id'], unique=False)

    # Add channel_id and category to videos table
    op.add_column('videos', sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('videos', sa.Column('category', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_videos_category'), 'videos', ['category'], unique=False)
    op.create_index(op.f('ix_videos_channel_id'), 'videos', ['channel_id'], unique=False)
    op.create_foreign_key(None, 'videos', 'channels', ['channel_id'], ['id'])


def downgrade() -> None:
    # Remove foreign key and columns from videos table
    op.drop_constraint(None, 'videos', type_='foreignkey')
    op.drop_index(op.f('ix_videos_channel_id'), table_name='videos')
    op.drop_index(op.f('ix_videos_category'), table_name='videos')
    op.drop_column('videos', 'category')
    op.drop_column('videos', 'channel_id')

    # Drop video_playlist_items table
    op.drop_index(op.f('ix_video_playlist_items_video_id'), table_name='video_playlist_items')
    op.drop_index(op.f('ix_video_playlist_items_playlist_id'), table_name='video_playlist_items')
    op.drop_table('video_playlist_items')

    # Drop video_playlists table
    op.drop_index(op.f('ix_video_playlists_visibility'), table_name='video_playlists')
    op.drop_index(op.f('ix_video_playlists_creator_id'), table_name='video_playlists')
    op.drop_index(op.f('ix_video_playlists_created_at'), table_name='video_playlists')
    op.drop_index(op.f('ix_video_playlists_channel_id'), table_name='video_playlists')
    op.drop_table('video_playlists')

    # Drop channels table
    op.drop_index(op.f('ix_channels_visibility'), table_name='channels')
    op.drop_index(op.f('ix_channels_slug'), table_name='channels')
    op.drop_index(op.f('ix_channels_creator_id'), table_name='channels')
    op.drop_index(op.f('ix_channels_created_at'), table_name='channels')
    op.drop_index(op.f('ix_channels_category'), table_name='channels')
    op.drop_table('channels')