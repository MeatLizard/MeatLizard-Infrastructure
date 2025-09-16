"""add_email_system_tables

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create email_accounts table
    op.create_table('email_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email_address', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('quota_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('used_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('last_activity', sa.DateTime(), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email_address', name='unique_email_address')
    )
    
    # Create email_aliases table
    op.create_table('email_aliases',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alias_address', sa.String(length=255), nullable=False),
        sa.Column('destination_address', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alias_address', name='unique_alias_address')
    )
    
    # Create email_folders table
    op.create_table('email_folders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('folder_name', sa.String(length=100), nullable=False),
        sa.Column('folder_type', sa.Enum('inbox', 'sent', 'drafts', 'trash', 'spam', 'custom', name='emailfoldertype'), nullable=False, server_default='custom'),
        sa.Column('parent_folder_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unread_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['email_account_id'], ['email_accounts.id'], ),
        sa.ForeignKeyConstraint(['parent_folder_id'], ['email_folders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create email_messages table
    op.create_table('email_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=True),
        sa.Column('from_address', sa.String(length=255), nullable=False),
        sa.Column('to_addresses', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('cc_addresses', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('bcc_addresses', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('attachments', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_starred', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_draft', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('headers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['email_account_id'], ['email_accounts.id'], ),
        sa.ForeignKeyConstraint(['folder_id'], ['email_folders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create email_contacts table
    op.create_table('email_contacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email_address', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('organization', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create email_templates table
    op.create_table('email_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_name', sa.String(length=100), nullable=False),
        sa.Column('subject_template', sa.String(length=255), nullable=True),
        sa.Column('body_template', sa.Text(), nullable=False),
        sa.Column('is_html', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_email_accounts_user', 'email_accounts', ['user_id'], unique=False)
    op.create_index('idx_email_accounts_active', 'email_accounts', ['is_active'], unique=False)
    op.create_index('idx_email_accounts_last_login', 'email_accounts', ['last_login'], unique=False)
    
    op.create_index('idx_email_aliases_user', 'email_aliases', ['user_id'], unique=False)
    op.create_index('idx_email_aliases_active', 'email_aliases', ['is_active'], unique=False)
    op.create_index('idx_email_aliases_destination', 'email_aliases', ['destination_address'], unique=False)
    
    op.create_index('idx_email_folders_account', 'email_folders', ['email_account_id'], unique=False)
    op.create_index('idx_email_folders_type', 'email_folders', ['folder_type'], unique=False)
    op.create_index('idx_email_folders_parent', 'email_folders', ['parent_folder_id'], unique=False)
    
    op.create_index('idx_email_messages_account', 'email_messages', ['email_account_id'], unique=False)
    op.create_index('idx_email_messages_folder', 'email_messages', ['folder_id'], unique=False)
    op.create_index('idx_email_messages_received', 'email_messages', ['received_at'], unique=False)
    op.create_index('idx_email_messages_read', 'email_messages', ['is_read'], unique=False)
    op.create_index('idx_email_messages_thread', 'email_messages', ['thread_id'], unique=False)
    op.create_index('idx_email_messages_from', 'email_messages', ['from_address'], unique=False)
    
    op.create_index('idx_email_contacts_user', 'email_contacts', ['user_id'], unique=False)
    op.create_index('idx_email_contacts_email', 'email_contacts', ['email_address'], unique=False)
    op.create_index('idx_email_contacts_name', 'email_contacts', ['display_name'], unique=False)
    
    op.create_index('idx_email_templates_user', 'email_templates', ['user_id'], unique=False)
    op.create_index('idx_email_templates_default', 'email_templates', ['is_default'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_email_templates_default', table_name='email_templates')
    op.drop_index('idx_email_templates_user', table_name='email_templates')
    
    op.drop_index('idx_email_contacts_name', table_name='email_contacts')
    op.drop_index('idx_email_contacts_email', table_name='email_contacts')
    op.drop_index('idx_email_contacts_user', table_name='email_contacts')
    
    op.drop_index('idx_email_messages_from', table_name='email_messages')
    op.drop_index('idx_email_messages_thread', table_name='email_messages')
    op.drop_index('idx_email_messages_read', table_name='email_messages')
    op.drop_index('idx_email_messages_received', table_name='email_messages')
    op.drop_index('idx_email_messages_folder', table_name='email_messages')
    op.drop_index('idx_email_messages_account', table_name='email_messages')
    
    op.drop_index('idx_email_folders_parent', table_name='email_folders')
    op.drop_index('idx_email_folders_type', table_name='email_folders')
    op.drop_index('idx_email_folders_account', table_name='email_folders')
    
    op.drop_index('idx_email_aliases_destination', table_name='email_aliases')
    op.drop_index('idx_email_aliases_active', table_name='email_aliases')
    op.drop_index('idx_email_aliases_user', table_name='email_aliases')
    
    op.drop_index('idx_email_accounts_last_login', table_name='email_accounts')
    op.drop_index('idx_email_accounts_active', table_name='email_accounts')
    op.drop_index('idx_email_accounts_user', table_name='email_accounts')
    
    # Drop tables
    op.drop_table('email_templates')
    op.drop_table('email_contacts')
    op.drop_table('email_messages')
    op.drop_table('email_folders')
    op.drop_table('email_aliases')
    op.drop_table('email_accounts')
    
    # Drop enum
    op.execute('DROP TYPE IF EXISTS emailfoldertype')