-- Video Platform Database Initialization
-- Create extensions and optimizations for video platform

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create indexes for video platform performance
-- These will be applied after tables are created by Alembic

-- Function to create video platform indexes
CREATE OR REPLACE FUNCTION create_video_platform_indexes()
RETURNS void AS $$
BEGIN
    -- Video table indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'videos') THEN
        -- Performance indexes for video queries
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_creator_status 
            ON videos(creator_id, status) WHERE status != 'deleted';
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_visibility_created 
            ON videos(visibility, created_at DESC) WHERE visibility = 'public';
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_duration 
            ON videos(duration_seconds) WHERE duration_seconds IS NOT NULL;
        
        -- Full-text search index for video content
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_search 
            ON videos USING gin(to_tsvector('english', title || ' ' || COALESCE(description, '') || ' ' || array_to_string(tags, ' ')));
        
        -- Composite index for analytics queries
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_analytics 
            ON videos(created_at, status, visibility) WHERE status = 'completed';
    END IF;

    -- Transcoding jobs indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'transcoding_jobs') THEN
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transcoding_jobs_video_status 
            ON transcoding_jobs(video_id, status);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transcoding_jobs_status_created 
            ON transcoding_jobs(status, created_at) WHERE status IN ('queued', 'processing');
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transcoding_jobs_quality 
            ON transcoding_jobs(quality_preset, status);
    END IF;

    -- View sessions indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'view_sessions') THEN
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_view_sessions_video_user 
            ON view_sessions(video_id, user_id);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_view_sessions_started 
            ON view_sessions(started_at DESC);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_view_sessions_completion 
            ON view_sessions(completion_percentage) WHERE completion_percentage > 0.8;
    END IF;

    -- Video comments indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'video_comments') THEN
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_video_comments_video_created 
            ON video_comments(video_id, created_at DESC);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_video_comments_user 
            ON video_comments(user_id, created_at DESC);
    END IF;

    -- Video likes indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'video_likes') THEN
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_video_likes_video_type 
            ON video_likes(video_id, like_type);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_video_likes_user_video 
            ON video_likes(user_id, video_id);
    END IF;

    -- Import jobs indexes
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'import_jobs') THEN
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_import_jobs_status_created 
            ON import_jobs(status, created_at DESC);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_import_jobs_platform 
            ON import_jobs(platform, status);
        
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_import_jobs_requested_by 
            ON import_jobs(requested_by, created_at DESC);
    END IF;

    RAISE NOTICE 'Video platform indexes created successfully';
END;
$$ LANGUAGE plpgsql;

-- Create a function to update video statistics
CREATE OR REPLACE FUNCTION update_video_statistics()
RETURNS void AS $$
BEGIN
    -- Update table statistics for better query planning
    ANALYZE videos;
    ANALYZE transcoding_jobs;
    ANALYZE view_sessions;
    ANALYZE video_comments;
    ANALYZE video_likes;
    ANALYZE import_jobs;
    
    RAISE NOTICE 'Video platform statistics updated';
END;
$$ LANGUAGE plpgsql;

-- Create maintenance functions
CREATE OR REPLACE FUNCTION cleanup_old_view_sessions(days_old INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Clean up old view sessions to prevent table bloat
    DELETE FROM view_sessions 
    WHERE started_at < NOW() - INTERVAL '1 day' * days_old
    AND ended_at IS NOT NULL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    RAISE NOTICE 'Cleaned up % old view sessions', deleted_count;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create a function to get video platform health metrics
CREATE OR REPLACE FUNCTION get_video_platform_health()
RETURNS TABLE(
    metric_name TEXT,
    metric_value NUMERIC,
    metric_unit TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'total_videos'::TEXT, COUNT(*)::NUMERIC, 'count'::TEXT FROM videos
    UNION ALL
    SELECT 'active_transcoding_jobs'::TEXT, COUNT(*)::NUMERIC, 'count'::TEXT 
    FROM transcoding_jobs WHERE status IN ('queued', 'processing')
    UNION ALL
    SELECT 'completed_videos'::TEXT, COUNT(*)::NUMERIC, 'count'::TEXT 
    FROM videos WHERE status = 'completed'
    UNION ALL
    SELECT 'total_view_sessions'::TEXT, COUNT(*)::NUMERIC, 'count'::TEXT FROM view_sessions
    UNION ALL
    SELECT 'active_import_jobs'::TEXT, COUNT(*)::NUMERIC, 'count'::TEXT 
    FROM import_jobs WHERE status IN ('queued', 'processing')
    UNION ALL
    SELECT 'database_size'::TEXT, 
           pg_database_size(current_database())::NUMERIC / 1024 / 1024, 'MB'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION create_video_platform_indexes() TO PUBLIC;
GRANT EXECUTE ON FUNCTION update_video_statistics() TO PUBLIC;
GRANT EXECUTE ON FUNCTION cleanup_old_view_sessions(INTEGER) TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_video_platform_health() TO PUBLIC;