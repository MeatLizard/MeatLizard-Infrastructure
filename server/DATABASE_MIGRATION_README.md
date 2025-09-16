# Database Migration: Enhanced Models for Discord Integration

## Overview

This migration enhances the existing database schema to support the full AI Chat Discord System functionality. It extends the existing User and Session models and adds new models for comprehensive chat management, metrics, and system administration.

## Migration Details

**Migration ID:** 001  
**File:** `web/alembic/versions/001_enhance_database_models_for_discord_integration.py`  
**Requirements Addressed:** 6.1, 6.4, 5.2

## Schema Changes

### Enhanced Existing Models

#### Users Table

**Extended fields:**

- `is_active` (Boolean) - Track user active status
- `preferences` (JSONB) - Store user preferences and settings

#### Sessions Table

**Extended fields:**

- `parameters` (JSONB) - Store LLM generation parameters
- `ended_at` (DateTime) - Track session end time
- `is_active` (Boolean) - Track session active status

### New Models

#### Messages Table

Stores all chat messages with encryption support:

- `id` (UUID) - Primary key
- `session_id` (UUID) - Foreign key to sessions
- `request_id` (UUID) - Unique request identifier
- `role` (Enum) - Message role: user, assistant, system
- `content` (Text) - Message content
- `encrypted_content` (LargeBinary) - Encrypted message content
- `timestamp` (DateTime) - Message timestamp
- `metadata` (JSONB) - Additional message metadata

#### Transcripts Table

Manages session transcripts and S3 storage:

- `id` (UUID) - Primary key
- `session_id` (UUID) - Foreign key to sessions
- `s3_key` (String) - S3 storage key
- `format` (Enum) - Transcript format: json, csv
- `created_at` (DateTime) - Creation timestamp
- `file_size_bytes` (Integer) - File size
- `message_count` (Integer) - Number of messages

#### Metrics Table

Stores performance and system metrics:

- `id` (UUID) - Primary key
- `client_bot_id` (String) - Client bot identifier
- `timestamp` (DateTime) - Metric timestamp
- `metric_type` (String) - Type of metric
- `metric_data` (JSONB) - Metric data payload

#### SystemConfig Table

Manages system configuration settings:

- `key` (String) - Configuration key (primary key)
- `value` (JSONB) - Configuration value
- `updated_at` (DateTime) - Last update timestamp
- `updated_by` (UUID) - User who updated (foreign key)

#### BackupLog Table

Tracks backup operations:

- `id` (UUID) - Primary key
- `backup_type` (String) - Type of backup
- `status` (Enum) - Backup status: started, in_progress, completed, failed
- `started_at` (DateTime) - Backup start time
- `completed_at` (DateTime) - Backup completion time
- `file_path` (String) - Backup file path
- `file_size_bytes` (BigInteger) - Backup file size
- `error_message` (Text) - Error message if failed

## Indexes for Performance

The migration creates comprehensive indexes for optimal query performance:

### User Indexes

- `idx_users_discord_id` - Discord ID lookups
- `idx_users_active` - Active user filtering

### Session Indexes

- `idx_sessions_owner` - Sessions by user
- `idx_sessions_origin` - Sessions by platform
- `idx_sessions_active` - Active session filtering
- `idx_sessions_created_at` - Time-based queries
- `idx_sessions_discord_channel` - Discord channel lookups

### Message Indexes

- `idx_messages_session` - Messages by session
- `idx_messages_timestamp` - Time-based message queries
- `idx_messages_role` - Messages by role
- `idx_messages_request_id` - Request ID lookups

### Transcript Indexes

- `idx_transcripts_session` - Transcripts by session
- `idx_transcripts_created_at` - Time-based transcript queries
- `idx_transcripts_format` - Transcripts by format

### Metrics Indexes

- `idx_metrics_timestamp` - Time-based metrics queries
- `idx_metrics_type` - Metrics by type
- `idx_metrics_client_bot` - Metrics by client bot

### Backup Log Indexes

- `idx_backup_logs_type` - Backups by type
- `idx_backup_logs_status` - Backups by status
- `idx_backup_logs_started_at` - Time-based backup queries

## Constraints and Relationships

### Foreign Key Constraints

- `sessions.owner_user_id` → `users.id`
- `messages.session_id` → `sessions.id`
- `transcripts.session_id` → `sessions.id`
- `system_configs.updated_by` → `users.id`

### Unique Constraints

- `users.discord_id` - Unique Discord user mapping
- `sessions.discord_channel_id` - Unique Discord channel mapping
- `messages.request_id` - Unique request tracking

### Cascade Relationships

- Session deletion cascades to messages and transcripts
- Maintains referential integrity

## Enums

### SessionOrigin

- `website` - Web interface sessions
- `discord` - Discord bot sessions

### MessageRole

- `user` - User messages
- `assistant` - AI assistant responses
- `system` - System messages

### TranscriptFormat

- `json` - JSON format transcripts
- `csv` - CSV format transcripts

### BackupStatus

- `started` - Backup initiated
- `in_progress` - Backup in progress
- `completed` - Backup completed successfully
- `failed` - Backup failed

## Running the Migration

### Prerequisites

1. PostgreSQL database running
2. Database connection configured in environment variables
3. Alembic installed and configured

### Migration Commands

```bash
# Navigate to server directory
cd server

# Run the migration
alembic upgrade head

# Verify migration
alembic current

# If needed, rollback
alembic downgrade base
```

### Environment Variables Required

```bash
DATABASE_URL=postgresql://username:password@host:port/database
```

## Validation

The migration includes comprehensive validation:

1. **Syntax Validation** - All Python files compile without errors
2. **Schema Validation** - All tables, indexes, and constraints are properly defined
3. **Relationship Validation** - Foreign key relationships are correctly established
4. **Data Type Validation** - All column types are appropriate for their use cases

## Post-Migration Steps

After running the migration:

1. **Verify Schema** - Check that all tables and indexes were created
2. **Test Relationships** - Verify foreign key constraints work correctly
3. **Performance Testing** - Confirm indexes improve query performance
4. **Data Integrity** - Test that constraints prevent invalid data

## Rollback Plan

The migration includes a complete downgrade function that:

1. Drops all indexes in reverse order
2. Drops all tables in dependency order
3. Drops all custom enum types
4. Restores the database to its previous state

## Files Modified/Created

### Modified Files

- `server/web/app/models.py` - Enhanced SQLAlchemy models
- `shared_lib/models.py` - Added new Pydantic models
- `server/alembic.ini` - Fixed alembic configuration

### Created Files

- `server/web/alembic/versions/001_enhance_database_models_for_discord_integration.py` - Migration script
- `server/test_migration.py` - Test script for model validation
- `server/validate_migration.py` - Validation script
- `server/DATABASE_MIGRATION_README.md` - This documentation

## Security Considerations

1. **Encrypted Content** - Messages support encrypted storage via `encrypted_content` field
2. **Audit Trail** - System configs track who made changes and when
3. **Data Integrity** - Foreign key constraints prevent orphaned records
4. **Access Control** - User active status allows for account management

## Performance Considerations

1. **Comprehensive Indexing** - All frequently queried columns are indexed
2. **JSONB Usage** - Efficient storage and querying of structured data
3. **Proper Data Types** - Optimized column types for storage efficiency
4. **Cascade Deletes** - Efficient cleanup of related records

This migration provides a robust foundation for the AI Chat Discord System with proper data modeling, performance optimization, and security considerations.
