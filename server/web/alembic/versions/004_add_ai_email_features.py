"""add_ai_email_features

Revision ID: 004
Revises: 003
Create Date: 2024-01-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create email_prompt_templates table
    op.create_table('email_prompt_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('chain_of_thought', sa.Text(), nullable=True),
        sa.Column('variables', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('tier_access', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='["business"]'),
        sa.Column('automation_ready', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create scheduled_emails table
    op.create_table('scheduled_emails',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('recipient_name', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('variables', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('generated_content_text', sa.Text(), nullable=True),
        sa.Column('generated_content_html', sa.Text(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(), nullable=False),
        sa.Column('optimal_send_time', sa.DateTime(), nullable=True),
        sa.Column('time_zone', sa.String(length=50), nullable=True),
        sa.Column('status', sa.Enum('draft', 'scheduled', 'generating', 'ready', 'sent', 'failed', 'cancelled', name='scheduledemailstatus'), nullable=False, server_default='draft'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['email_account_id'], ['email_accounts.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['email_prompt_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create email_workflows table
    op.create_table('email_workflows',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('workflow_type', sa.Enum('chain_of_thought', 'behavioral_trigger', 'recurring_campaign', 'ab_test', name='emailworkflowtype'), nullable=False),
        sa.Column('steps', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('trigger_conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('schedule_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('execution_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_executed', sa.DateTime(), nullable=True),
        sa.Column('next_execution', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create email_ab_tests table
    op.create_table('email_ab_tests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('test_name', sa.String(length=100), nullable=False),
        sa.Column('hypothesis', sa.Text(), nullable=False),
        sa.Column('variant_a_template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variant_b_template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('traffic_split', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('success_metric', sa.String(length=50), nullable=False),
        sa.Column('confidence_level', sa.Float(), nullable=False, server_default='0.95'),
        sa.Column('minimum_sample_size', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('status', sa.Enum('draft', 'running', 'completed', 'stopped', name='abtestatus'), nullable=False, server_default='draft'),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('winner_variant', sa.String(length=1), nullable=True),
        sa.Column('statistical_significance', sa.Float(), nullable=True),
        sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['variant_a_template_id'], ['email_prompt_templates.id'], ),
        sa.ForeignKeyConstraint(['variant_b_template_id'], ['email_prompt_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create email_generation_logs table
    op.create_table('email_generation_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('scheduled_email_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prompt_used', sa.Text(), nullable=False),
        sa.Column('variables_used', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('generated_content', sa.Text(), nullable=True),
        sa.Column('generation_time_ms', sa.Integer(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('status', sa.Enum('success', 'failed', 'timeout', 'rejected', name='generationstatus'), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('model_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['email_prompt_templates.id'], ),
        sa.ForeignKeyConstraint(['scheduled_email_id'], ['scheduled_emails.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create email_personalization_rules table
    op.create_table('email_personalization_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_name', sa.String(length=100), nullable=False),
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('actions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_email_prompt_templates_category', 'email_prompt_templates', ['category'], unique=False)
    op.create_index('idx_email_prompt_templates_tier_access', 'email_prompt_templates', ['tier_access'], unique=False)
    op.create_index('idx_email_prompt_templates_active', 'email_prompt_templates', ['is_active'], unique=False)
    op.create_index('idx_email_prompt_templates_usage', 'email_prompt_templates', ['usage_count'], unique=False)
    
    op.create_index('idx_scheduled_emails_user', 'scheduled_emails', ['user_id'], unique=False)
    op.create_index('idx_scheduled_emails_status', 'scheduled_emails', ['status'], unique=False)
    op.create_index('idx_scheduled_emails_scheduled_for', 'scheduled_emails', ['scheduled_for'], unique=False)
    op.create_index('idx_scheduled_emails_optimal_time', 'scheduled_emails', ['optimal_send_time'], unique=False)
    op.create_index('idx_scheduled_emails_priority', 'scheduled_emails', ['priority'], unique=False)
    
    op.create_index('idx_email_workflows_user', 'email_workflows', ['user_id'], unique=False)
    op.create_index('idx_email_workflows_type', 'email_workflows', ['workflow_type'], unique=False)
    op.create_index('idx_email_workflows_active', 'email_workflows', ['is_active'], unique=False)
    op.create_index('idx_email_workflows_next_execution', 'email_workflows', ['next_execution'], unique=False)
    
    op.create_index('idx_email_ab_tests_user', 'email_ab_tests', ['user_id'], unique=False)
    op.create_index('idx_email_ab_tests_status', 'email_ab_tests', ['status'], unique=False)
    op.create_index('idx_email_ab_tests_dates', 'email_ab_tests', ['start_date', 'end_date'], unique=False)
    
    op.create_index('idx_email_generation_logs_user', 'email_generation_logs', ['user_id'], unique=False)
    op.create_index('idx_email_generation_logs_template', 'email_generation_logs', ['template_id'], unique=False)
    op.create_index('idx_email_generation_logs_status', 'email_generation_logs', ['status'], unique=False)
    op.create_index('idx_email_generation_logs_created', 'email_generation_logs', ['created_at'], unique=False)
    
    op.create_index('idx_email_personalization_rules_user', 'email_personalization_rules', ['user_id'], unique=False)
    op.create_index('idx_email_personalization_rules_active', 'email_personalization_rules', ['is_active'], unique=False)
    op.create_index('idx_email_personalization_rules_priority', 'email_personalization_rules', ['priority'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_email_personalization_rules_priority', table_name='email_personalization_rules')
    op.drop_index('idx_email_personalization_rules_active', table_name='email_personalization_rules')
    op.drop_index('idx_email_personalization_rules_user', table_name='email_personalization_rules')
    
    op.drop_index('idx_email_generation_logs_created', table_name='email_generation_logs')
    op.drop_index('idx_email_generation_logs_status', table_name='email_generation_logs')
    op.drop_index('idx_email_generation_logs_template', table_name='email_generation_logs')
    op.drop_index('idx_email_generation_logs_user', table_name='email_generation_logs')
    
    op.drop_index('idx_email_ab_tests_dates', table_name='email_ab_tests')
    op.drop_index('idx_email_ab_tests_status', table_name='email_ab_tests')
    op.drop_index('idx_email_ab_tests_user', table_name='email_ab_tests')
    
    op.drop_index('idx_email_workflows_next_execution', table_name='email_workflows')
    op.drop_index('idx_email_workflows_active', table_name='email_workflows')
    op.drop_index('idx_email_workflows_type', table_name='email_workflows')
    op.drop_index('idx_email_workflows_user', table_name='email_workflows')
    
    op.drop_index('idx_scheduled_emails_priority', table_name='scheduled_emails')
    op.drop_index('idx_scheduled_emails_optimal_time', table_name='scheduled_emails')
    op.drop_index('idx_scheduled_emails_scheduled_for', table_name='scheduled_emails')
    op.drop_index('idx_scheduled_emails_status', table_name='scheduled_emails')
    op.drop_index('idx_scheduled_emails_user', table_name='scheduled_emails')
    
    op.drop_index('idx_email_prompt_templates_usage', table_name='email_prompt_templates')
    op.drop_index('idx_email_prompt_templates_active', table_name='email_prompt_templates')
    op.drop_index('idx_email_prompt_templates_tier_access', table_name='email_prompt_templates')
    op.drop_index('idx_email_prompt_templates_category', table_name='email_prompt_templates')
    
    # Drop tables
    op.drop_table('email_personalization_rules')
    op.drop_table('email_generation_logs')
    op.drop_table('email_ab_tests')
    op.drop_table('email_workflows')
    op.drop_table('scheduled_emails')
    op.drop_table('email_prompt_templates')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS generationstatus')
    op.execute('DROP TYPE IF EXISTS abtestatus')
    op.execute('DROP TYPE IF EXISTS emailworkflowtype')
    op.execute('DROP TYPE IF EXISTS scheduledemailstatus')