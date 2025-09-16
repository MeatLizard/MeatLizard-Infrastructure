"""add_user_registration_and_tier_system

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        guid_type = postgresql.UUID(as_uuid=True)
        json_type = postgresql.JSONB(astext_type=sa.Text())
    else:
        guid_type = sa.String(32)
        json_type = sa.Text()

    # Add new columns to users table for registration system
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_verification_token', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('password_reset_token', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('password_reset_expires', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('login_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('discord_linked_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('discord_username', sa.String(length=100), nullable=True))
    
    # Create user_tiers table
    op.create_table('user_tiers',
        sa.Column('id', guid_type, nullable=False),
        sa.Column('user_id', guid_type, nullable=False),
        sa.Column('tier', sa.Enum('guest', 'free', 'vip', 'paid', 'business', name='usertier'), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('auto_renew', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('payment_method_id', sa.String(length=100), nullable=True),
        sa.Column('subscription_id', sa.String(length=100), nullable=True),
        sa.Column('metadata', json_type, nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create rate_limits table
    op.create_table('rate_limits',
        sa.Column('id', guid_type, nullable=False),
        sa.Column('user_id', guid_type, nullable=False),
        sa.Column('endpoint', sa.String(length=100), nullable=False),
        sa.Column('requests_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.Column('window_end', sa.DateTime(), nullable=False),
        sa.Column('tier', sa.Enum('guest', 'free', 'vip', 'paid', 'business', name='usertier'), nullable=False),
        sa.Column('limit_exceeded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('metadata', json_type, nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create user_usage_stats table
    op.create_table('user_usage_stats',
        sa.Column('id', guid_type, nullable=False),
        sa.Column('user_id', guid_type, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('messages_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ai_responses_received', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sessions_created', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('premium_features_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('api_calls_made', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tier_at_time', sa.Enum('guest', 'free', 'vip', 'paid', 'business', name='usertier'), nullable=False),
        sa.Column('metadata', json_type, nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date', name='unique_user_date_stats')
    )
    
    # Create tier_configurations table
    op.create_table('tier_configurations',
        sa.Column('tier', sa.Enum('guest', 'free', 'vip', 'paid', 'business', name='usertier'), nullable=False),
        sa.Column('display_name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_monthly', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('price_yearly', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('messages_per_hour', sa.Integer(), nullable=False),
        sa.Column('messages_per_day', sa.Integer(), nullable=False),
        sa.Column('messages_per_month', sa.Integer(), nullable=False),
        sa.Column('max_concurrent_sessions', sa.Integer(), nullable=False),
        sa.Column('max_message_length', sa.Integer(), nullable=False),
        sa.Column('priority_queue_access', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('advanced_features', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('api_access', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('transcript_retention_days', sa.Integer(), nullable=False),
        sa.Column('support_level', sa.String(length=20), nullable=False),
        sa.Column('features', json_type, nullable=False, server_default='{}'),
        sa.Column('restrictions', json_type, nullable=False, server_default='{}'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('tier')
    )
    
    # Create payment_transactions table
    op.create_table('payment_transactions',
        sa.Column('id', guid_type, nullable=False),
        sa.Column('user_id', guid_type, nullable=False),
        sa.Column('transaction_id', sa.String(length=100), nullable=False),
        sa.Column('payment_provider', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('tier_purchased', sa.Enum('guest', 'free', 'vip', 'paid', 'business', name='usertier'), nullable=False),
        sa.Column('billing_period', sa.String(length=20), nullable=False),
        sa.Column('status', sa.Enum('pending', 'completed', 'failed', 'refunded', 'cancelled', name='paymentstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', json_type, nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id', name='unique_transaction_id')
    )
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', guid_type, nullable=False),
        sa.Column('user_id', guid_type, nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('old_values', json_type, nullable=True),
        sa.Column('new_values', json_type, nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('metadata', json_type, nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add unique constraint for email
    with op.batch_alter_table('users') as batch_op:
        batch_op.create_unique_constraint('unique_user_email', ['email'])
    
    # Create indexes for performance
    op.create_index('idx_users_email', 'users', ['email'], unique=False)
    op.create_index('idx_users_email_verified', 'users', ['email_verified'], unique=False)
    op.create_index('idx_users_last_login', 'users', ['last_login'], unique=False)
    op.create_index('idx_users_discord_username', 'users', ['discord_username'], unique=False)
    
    op.create_index('idx_user_tiers_user_id', 'user_tiers', ['user_id'], unique=False)
    op.create_index('idx_user_tiers_tier', 'user_tiers', ['tier'], unique=False)
    op.create_index('idx_user_tiers_active', 'user_tiers', ['is_active'], unique=False)
    op.create_index('idx_user_tiers_expires', 'user_tiers', ['expires_at'], unique=False)
    
    op.create_index('idx_rate_limits_user_endpoint', 'rate_limits', ['user_id', 'endpoint'], unique=False)
    op.create_index('idx_rate_limits_window', 'rate_limits', ['window_start', 'window_end'], unique=False)
    op.create_index('idx_rate_limits_tier', 'rate_limits', ['tier'], unique=False)
    
    op.create_index('idx_usage_stats_user_date', 'user_usage_stats', ['user_id', 'date'], unique=False)
    op.create_index('idx_usage_stats_date', 'user_usage_stats', ['date'], unique=False)
    op.create_index('idx_usage_stats_tier', 'user_usage_stats', ['tier_at_time'], unique=False)
    
    op.create_index('idx_payment_transactions_user', 'payment_transactions', ['user_id'], unique=False)
    op.create_index('idx_payment_transactions_status', 'payment_transactions', ['status'], unique=False)
    op.create_index('idx_payment_transactions_created', 'payment_transactions', ['created_at'], unique=False)
    
    op.create_index('idx_audit_logs_user', 'audit_logs', ['user_id'], unique=False)
    op.create_index('idx_audit_logs_action', 'audit_logs', ['action'], unique=False)
    op.create_index('idx_audit_logs_timestamp', 'audit_logs', ['timestamp'], unique=False)
    op.create_index('idx_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'], unique=False)
    
    # Insert default tier configurations
    op.execute("""
        INSERT INTO tier_configurations (
            tier, display_name, description, price_monthly, price_yearly,
            messages_per_hour, messages_per_day, messages_per_month,
            max_concurrent_sessions, max_message_length, priority_queue_access,
            advanced_features, api_access, transcript_retention_days,
            support_level, features, restrictions, updated_at
        ) VALUES 
        ('guest', 'Guest', 'Limited access for unregistered users', NULL, NULL, 5, 20, 100, 1, 500, false, false, false, 7, 'none', '{}', '{"registration_required": false}', CURRENT_TIMESTAMP),
        ('free', 'Free', 'Basic access for registered users', 0.00, 0.00, 20, 100, 1000, 2, 1000, false, false, false, 30, 'community', '{"basic_chat": true}', '{"ads_enabled": true}', CURRENT_TIMESTAMP),
        ('vip', 'VIP', 'Enhanced access with priority support', 9.99, 99.99, 100, 500, 5000, 5, 2000, true, true, false, 90, 'priority', '{"advanced_chat": true, "custom_prompts": true}', '{}', CURRENT_TIMESTAMP),
        ('paid', 'Pro', 'Professional tier with API access', 19.99, 199.99, 500, 2000, 20000, 10, 4000, true, true, true, 365, 'premium', '{"api_access": true, "bulk_operations": true}', '{}', CURRENT_TIMESTAMP),
        ('business', 'Business', 'Enterprise tier with unlimited access', 99.99, 999.99, 9999, 50000, 500000, 50, 8000, true, true, true, 365, 'enterprise', '{"unlimited_features": true, "dedicated_support": true}', '{}', CURRENT_TIMESTAMP)
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_audit_logs_resource', table_name='audit_logs')
    op.drop_index('idx_audit_logs_timestamp', table_name='audit_logs')
    op.drop_index('idx_audit_logs_action', table_name='audit_logs')
    op.drop_index('idx_audit_logs_user', table_name='audit_logs')
    
    op.drop_index('idx_payment_transactions_created', table_name='payment_transactions')
    op.drop_index('idx_payment_transactions_status', table_name='payment_transactions')
    op.drop_index('idx_payment_transactions_user', table_name='payment_transactions')
    
    op.drop_index('idx_usage_stats_tier', table_name='user_usage_stats')
    op.drop_index('idx_usage_stats_date', table_name='user_usage_stats')
    op.drop_index('idx_usage_stats_user_date', table_name='user_usage_stats')
    
    op.drop_index('idx_rate_limits_tier', table_name='rate_limits')
    op.drop_index('idx_rate_limits_window', table_name='rate_limits')
    op.drop_index('idx_rate_limits_user_endpoint', table_name='rate_limits')
    
    op.drop_index('idx_user_tiers_expires', table_name='user_tiers')
    op.drop_index('idx_user_tiers_active', table_name='user_tiers')
    op.drop_index('idx_user_tiers_tier', table_name='user_tiers')
    op.drop_index('idx_user_tiers_user_id', table_name='user_tiers')
    
    op.drop_index('idx_users_discord_username', table_name='users')
    op.drop_index('idx_users_last_login', table_name='users')
    op.drop_index('idx_users_email_verified', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    
    # Drop unique constraint
    op.drop_constraint('unique_user_email', 'users', type_='unique')
    
    # Drop tables
    op.drop_table('audit_logs')
    op.drop_table('payment_transactions')
    op.drop_table('tier_configurations')
    op.drop_table('user_usage_stats')
    op.drop_table('rate_limits')
    
    # Drop columns from users table
    op.drop_column('users', 'discord_username')
    op.drop_column('users', 'discord_linked_at')
    op.drop_column('users', 'login_count')
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'password_reset_expires')
    op.drop_column('users', 'password_reset_token')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'email')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS paymentstatus')
    op.execute('DROP TYPE IF EXISTS usertier')