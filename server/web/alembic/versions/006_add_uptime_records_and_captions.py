"""add_uptime_records_and_captions

Revision ID: 006
Revises: fde764e7cab6
Create Date: 2025-09-16 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from web.app.models import GUID

# revision identifiers, used by Alembic.
revision = '006'
down_revision = 'fde764e7cab6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('uptime_records',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('is_online', sa.Boolean(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_uptime_records_service_name'), 'uptime_records', ['service_name'], unique=False)
    op.create_index(op.f('ix_uptime_records_timestamp'), 'uptime_records', ['timestamp'], unique=False)
    op.add_column('media_files', sa.Column('captions', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('media_files', 'captions')
    op.drop_index(op.f('ix_uptime_records_timestamp'), table_name='uptime_records')
    op.drop_index(op.f('ix_uptime_records_service_name'), table_name='uptime_records')
    op.drop_table('uptime_records')