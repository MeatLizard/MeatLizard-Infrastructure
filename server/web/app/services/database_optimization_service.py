"""
Database Optimization Service

Provides database performance optimization including indexing strategies,
query optimization, connection pooling, and performance monitoring.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import time
import json

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text, inspect, MetaData, Table, Index
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import sqlalchemy as sa

from server.web.app.config import settings
from server.web.app.services.base_service import BaseService
from server.web.app.services.redis_client import RedisClient, get_redis_client

logger = logging.getLogger(__name__)


@dataclass
class QueryPerformanceMetric:
    """Query performance measurement"""
    query_hash: str
    query_text: str
    execution_time_ms: float
    rows_examined: int
    rows_returned: int
    timestamp: datetime
    table_names: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'query_hash': self.query_hash,
            'query_text': self.query_text,
            'execution_time_ms': self.execution_time_ms,
            'rows_examined': self.rows_examined,
            'rows_returned': self.rows_returned,
            'timestamp': self.timestamp.isoformat(),
            'table_names': self.table_names
        }


@dataclass
class IndexRecommendation:
    """Database index recommendation"""
    table_name: str
    columns: List[str]
    index_type: str  # btree, gin, gist, hash
    reason: str
    estimated_benefit: float  # 0.0 to 1.0
    query_patterns: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'table_name': self.table_name,
            'columns': self.columns,
            'index_type': self.index_type,
            'reason': self.reason,
            'estimated_benefit': self.estimated_benefit,
            'query_patterns': self.query_patterns
        }


@dataclass
class DatabaseStats:
    """Database performance statistics"""
    total_size_mb: float
    table_count: int
    index_count: int
    active_connections: int
    slow_queries_count: int
    cache_hit_ratio: float
    avg_query_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_size_mb': self.total_size_mb,
            'table_count': self.table_count,
            'index_count': self.index_count,
            'active_connections': self.active_connections,
            'slow_queries_count': self.slow_queries_count,
            'cache_hit_ratio': self.cache_hit_ratio,
            'avg_query_time_ms': self.avg_query_time_ms
        }


class DatabaseOptimizationService(BaseService):
    """Service for database performance optimization and monitoring"""
    
    def __init__(self, db: AsyncSession, redis_client: RedisClient = None):
        self.db = db
        self.redis = redis_client
        self._query_metrics: List[QueryPerformanceMetric] = []
        self._monitoring_active = False
        
        # Performance thresholds
        self.thresholds = {
            'slow_query_ms': 1000,      # Queries slower than 1 second
            'cache_hit_ratio_min': 0.9,  # Minimum cache hit ratio
            'connection_limit': 80,      # Max connection usage percentage
            'table_scan_rows': 10000,    # Large table scan threshold
        }
        
        # Video platform specific optimization patterns
        self.video_query_patterns = {
            'video_search': {
                'tables': ['videos'],
                'common_filters': ['title', 'tags', 'category', 'visibility', 'status'],
                'common_sorts': ['created_at', 'title']
            },
            'user_videos': {
                'tables': ['videos'],
                'common_filters': ['creator_id', 'visibility', 'status'],
                'common_sorts': ['created_at', 'updated_at']
            },
            'video_analytics': {
                'tables': ['view_sessions', 'video_likes', 'video_comments'],
                'common_filters': ['video_id', 'started_at', 'created_at'],
                'common_sorts': ['started_at', 'created_at']
            },
            'trending_videos': {
                'tables': ['videos', 'view_sessions', 'video_likes'],
                'common_filters': ['visibility', 'started_at', 'created_at'],
                'common_sorts': ['view_count', 'like_count']
            }
        }
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance"""
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis
    
    async def analyze_query_performance(self, query: str, params: Dict[str, Any] = None) -> QueryPerformanceMetric:
        """
        Analyze performance of a specific query
        
        Args:
            query: SQL query to analyze
            params: Query parameters
            
        Returns:
            Query performance metrics
        """
        try:
            # Generate query hash for tracking
            query_hash = str(hash(query))[:16]
            
            # Execute EXPLAIN ANALYZE
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            
            start_time = time.time()
            result = await self.db.execute(text(explain_query), params or {})
            execution_time = (time.time() - start_time) * 1000
            
            explain_result = result.fetchone()[0]
            plan = explain_result[0]['Plan']
            
            # Extract performance metrics
            rows_examined = self._extract_rows_examined(plan)
            rows_returned = plan.get('Actual Rows', 0)
            table_names = self._extract_table_names(plan)
            
            metric = QueryPerformanceMetric(
                query_hash=query_hash,
                query_text=query[:500],  # Truncate for storage
                execution_time_ms=execution_time,
                rows_examined=rows_examined,
                rows_returned=rows_returned,
                timestamp=datetime.utcnow(),
                table_names=table_names
            )
            
            # Store metric
            self._query_metrics.append(metric)
            
            # Store in Redis for persistence
            redis = await self._get_redis()
            metric_key = f"db:query_metric:{query_hash}:{int(time.time())}"
            await redis.set(metric_key, metric.to_dict(), expire=86400)
            
            return metric
            
        except Exception as e:
            logger.error(f"Failed to analyze query performance: {e}")
            # Return basic metric on error
            return QueryPerformanceMetric(
                query_hash=str(hash(query))[:16],
                query_text=query[:500],
                execution_time_ms=0.0,
                rows_examined=0,
                rows_returned=0,
                timestamp=datetime.utcnow(),
                table_names=[]
            )
    
    def _extract_rows_examined(self, plan: Dict[str, Any]) -> int:
        """Extract total rows examined from query plan"""
        rows = plan.get('Actual Rows', 0)
        
        # Add rows from child plans
        if 'Plans' in plan:
            for child_plan in plan['Plans']:
                rows += self._extract_rows_examined(child_plan)
        
        return rows
    
    def _extract_table_names(self, plan: Dict[str, Any]) -> List[str]:
        """Extract table names from query plan"""
        tables = []
        
        if 'Relation Name' in plan:
            tables.append(plan['Relation Name'])
        
        # Extract from child plans
        if 'Plans' in plan:
            for child_plan in plan['Plans']:
                tables.extend(self._extract_table_names(child_plan))
        
        return list(set(tables))  # Remove duplicates
    
    async def get_database_statistics(self) -> DatabaseStats:
        """
        Get comprehensive database performance statistics
        
        Returns:
            Database statistics
        """
        try:
            stats_queries = {
                'database_size': """
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                           pg_database_size(current_database()) as size_bytes
                """,
                'table_count': """
                    SELECT COUNT(*) as count 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """,
                'index_count': """
                    SELECT COUNT(*) as count 
                    FROM pg_indexes 
                    WHERE schemaname = 'public'
                """,
                'active_connections': """
                    SELECT COUNT(*) as count 
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """,
                'cache_stats': """
                    SELECT 
                        sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as cache_hit_ratio
                    FROM pg_statio_user_tables
                """
            }
            
            results = {}
            for stat_name, query in stats_queries.items():
                result = await self.db.execute(text(query))
                results[stat_name] = result.fetchone()
            
            # Calculate slow queries from recent metrics
            recent_metrics = [
                m for m in self._query_metrics
                if m.timestamp > datetime.utcnow() - timedelta(hours=1)
            ]
            slow_queries = len([
                m for m in recent_metrics
                if m.execution_time_ms > self.thresholds['slow_query_ms']
            ])
            
            avg_query_time = (
                sum(m.execution_time_ms for m in recent_metrics) / len(recent_metrics)
                if recent_metrics else 0.0
            )
            
            return DatabaseStats(
                total_size_mb=results['database_size']['size_bytes'] / (1024 * 1024),
                table_count=results['table_count']['count'],
                index_count=results['index_count']['count'],
                active_connections=results['active_connections']['count'],
                slow_queries_count=slow_queries,
                cache_hit_ratio=float(results['cache_stats']['cache_hit_ratio'] or 0.0),
                avg_query_time_ms=avg_query_time
            )
            
        except Exception as e:
            logger.error(f"Failed to get database statistics: {e}")
            return DatabaseStats(
                total_size_mb=0.0,
                table_count=0,
                index_count=0,
                active_connections=0,
                slow_queries_count=0,
                cache_hit_ratio=0.0,
                avg_query_time_ms=0.0
            )
    
    async def analyze_video_query_patterns(self) -> List[IndexRecommendation]:
        """
        Analyze video-specific query patterns and recommend indexes
        
        Returns:
            List of index recommendations
        """
        recommendations = []
        
        try:
            # Analyze common video queries
            video_queries = [
                # Video search queries
                {
                    'query': """
                        SELECT * FROM videos 
                        WHERE visibility = 'public' 
                        AND status = 'ready' 
                        AND title ILIKE %s 
                        ORDER BY created_at DESC
                    """,
                    'pattern': 'video_search'
                },
                # User videos
                {
                    'query': """
                        SELECT * FROM videos 
                        WHERE creator_id = %s 
                        AND visibility IN ('public', 'unlisted') 
                        ORDER BY created_at DESC
                    """,
                    'pattern': 'user_videos'
                },
                # Video analytics
                {
                    'query': """
                        SELECT COUNT(*) FROM view_sessions 
                        WHERE video_id = %s 
                        AND started_at >= %s
                    """,
                    'pattern': 'video_analytics'
                },
                # Trending videos
                {
                    'query': """
                        SELECT v.*, COUNT(vs.id) as view_count 
                        FROM videos v 
                        LEFT JOIN view_sessions vs ON v.id = vs.video_id 
                        WHERE v.visibility = 'public' 
                        AND vs.started_at >= %s 
                        GROUP BY v.id 
                        ORDER BY view_count DESC
                    """,
                    'pattern': 'trending_videos'
                }
            ]
            
            # Analyze each query pattern
            for query_info in video_queries:
                # Check if indexes exist for common filter combinations
                pattern = self.video_query_patterns[query_info['pattern']]
                
                for table in pattern['tables']:
                    # Check for composite indexes on common filter columns
                    if len(pattern['common_filters']) > 1:
                        recommendations.append(IndexRecommendation(
                            table_name=table,
                            columns=pattern['common_filters'][:3],  # Limit to 3 columns
                            index_type='btree',
                            reason=f"Composite index for {query_info['pattern']} queries",
                            estimated_benefit=0.8,
                            query_patterns=[query_info['pattern']]
                        ))
                    
                    # Check for sort optimization indexes
                    for sort_col in pattern['common_sorts']:
                        if sort_col not in pattern['common_filters']:
                            recommendations.append(IndexRecommendation(
                                table_name=table,
                                columns=[sort_col],
                                index_type='btree',
                                reason=f"Sort optimization for {query_info['pattern']} queries",
                                estimated_benefit=0.6,
                                query_patterns=[query_info['pattern']]
                            ))
            
            # Video-specific recommendations
            video_specific_recommendations = [
                # JSONB index for tags search
                IndexRecommendation(
                    table_name='videos',
                    columns=['tags'],
                    index_type='gin',
                    reason='GIN index for JSONB tags search and filtering',
                    estimated_benefit=0.9,
                    query_patterns=['video_search', 'tag_filtering']
                ),
                # Composite index for video listing
                IndexRecommendation(
                    table_name='videos',
                    columns=['visibility', 'status', 'created_at'],
                    index_type='btree',
                    reason='Composite index for public video listing with date sorting',
                    estimated_benefit=0.85,
                    query_patterns=['video_search', 'public_listing']
                ),
                # Index for user video management
                IndexRecommendation(
                    table_name='videos',
                    columns=['creator_id', 'status', 'updated_at'],
                    index_type='btree',
                    reason='Composite index for user video management queries',
                    estimated_benefit=0.8,
                    query_patterns=['user_videos', 'video_management']
                ),
                # Analytics optimization
                IndexRecommendation(
                    table_name='view_sessions',
                    columns=['video_id', 'started_at'],
                    index_type='btree',
                    reason='Composite index for video analytics and trending calculations',
                    estimated_benefit=0.9,
                    query_patterns=['video_analytics', 'trending_videos']
                ),
                # Comment threading optimization
                IndexRecommendation(
                    table_name='video_comments',
                    columns=['video_id', 'parent_comment_id', 'created_at'],
                    index_type='btree',
                    reason='Composite index for threaded comment queries',
                    estimated_benefit=0.7,
                    query_patterns=['comment_threading']
                )
            ]
            
            recommendations.extend(video_specific_recommendations)
            
            # Remove duplicates and sort by estimated benefit
            unique_recommendations = []
            seen = set()
            for rec in recommendations:
                key = (rec.table_name, tuple(rec.columns), rec.index_type)
                if key not in seen:
                    seen.add(key)
                    unique_recommendations.append(rec)
            
            unique_recommendations.sort(key=lambda x: x.estimated_benefit, reverse=True)
            
            return unique_recommendations
            
        except Exception as e:
            logger.error(f"Failed to analyze video query patterns: {e}")
            return []
    
    async def check_existing_indexes(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check existing database indexes
        
        Returns:
            Dictionary of table names and their indexes
        """
        try:
            query = """
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes 
                WHERE schemaname = 'public'
                ORDER BY tablename, indexname
            """
            
            result = await self.db.execute(text(query))
            rows = result.fetchall()
            
            indexes_by_table = {}
            for row in rows:
                table_name = row.tablename
                if table_name not in indexes_by_table:
                    indexes_by_table[table_name] = []
                
                indexes_by_table[table_name].append({
                    'name': row.indexname,
                    'definition': row.indexdef,
                    'schema': row.schemaname
                })
            
            return indexes_by_table
            
        except Exception as e:
            logger.error(f"Failed to check existing indexes: {e}")
            return {}
    
    async def create_recommended_indexes(self, recommendations: List[IndexRecommendation]) -> Dict[str, Any]:
        """
        Create recommended database indexes
        
        Args:
            recommendations: List of index recommendations to implement
            
        Returns:
            Results of index creation
        """
        results = {
            'created': [],
            'failed': [],
            'skipped': []
        }
        
        try:
            # Check existing indexes first
            existing_indexes = await self.check_existing_indexes()
            
            for rec in recommendations:
                try:
                    # Check if similar index already exists
                    table_indexes = existing_indexes.get(rec.table_name, [])
                    index_exists = any(
                        all(col in idx['definition'].lower() for col in rec.columns)
                        for idx in table_indexes
                    )
                    
                    if index_exists:
                        results['skipped'].append({
                            'table': rec.table_name,
                            'columns': rec.columns,
                            'reason': 'Similar index already exists'
                        })
                        continue
                    
                    # Generate index name
                    index_name = f"idx_{rec.table_name}_{'_'.join(rec.columns)}"
                    
                    # Build CREATE INDEX statement
                    if rec.index_type == 'gin':
                        # GIN index for JSONB columns
                        create_sql = f"""
                            CREATE INDEX CONCURRENTLY {index_name} 
                            ON {rec.table_name} 
                            USING gin ({rec.columns[0]})
                        """
                    else:
                        # B-tree index (default)
                        columns_str = ', '.join(rec.columns)
                        create_sql = f"""
                            CREATE INDEX CONCURRENTLY {index_name} 
                            ON {rec.table_name} ({columns_str})
                        """
                    
                    # Execute index creation
                    await self.db.execute(text(create_sql))
                    await self.db.commit()
                    
                    results['created'].append({
                        'table': rec.table_name,
                        'columns': rec.columns,
                        'index_name': index_name,
                        'type': rec.index_type,
                        'reason': rec.reason
                    })
                    
                    logger.info(f"Created index {index_name} on {rec.table_name}")
                    
                except Exception as e:
                    await self.db.rollback()
                    results['failed'].append({
                        'table': rec.table_name,
                        'columns': rec.columns,
                        'error': str(e)
                    })
                    logger.error(f"Failed to create index on {rec.table_name}: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to create recommended indexes: {e}")
            return results
    
    async def optimize_database_settings(self) -> Dict[str, Any]:
        """
        Analyze and recommend database configuration optimizations
        
        Returns:
            Database optimization recommendations
        """
        try:
            # Get current database settings
            settings_query = """
                SELECT name, setting, unit, short_desc 
                FROM pg_settings 
                WHERE name IN (
                    'shared_buffers',
                    'effective_cache_size',
                    'maintenance_work_mem',
                    'checkpoint_completion_target',
                    'wal_buffers',
                    'default_statistics_target',
                    'random_page_cost',
                    'effective_io_concurrency'
                )
            """
            
            result = await self.db.execute(text(settings_query))
            current_settings = {row.name: row.setting for row in result.fetchall()}
            
            # Get system information
            system_info_query = """
                SELECT 
                    (SELECT setting FROM pg_settings WHERE name = 'max_connections') as max_connections,
                    (SELECT count(*) FROM pg_stat_activity) as current_connections,
                    pg_size_pretty(pg_database_size(current_database())) as db_size
            """
            
            result = await self.db.execute(text(system_info_query))
            system_info = result.fetchone()
            
            recommendations = []
            
            # Analyze shared_buffers
            shared_buffers_mb = int(current_settings.get('shared_buffers', '128')) // 128  # Convert from 8KB blocks
            if shared_buffers_mb < 256:
                recommendations.append({
                    'setting': 'shared_buffers',
                    'current_value': f"{shared_buffers_mb}MB",
                    'recommended_value': '512MB',
                    'reason': 'Increase shared buffers for better caching',
                    'priority': 'high'
                })
            
            # Analyze connection usage
            connection_usage = int(system_info.current_connections) / int(system_info.max_connections)
            if connection_usage > 0.8:
                recommendations.append({
                    'setting': 'max_connections',
                    'current_value': system_info.max_connections,
                    'recommended_value': str(int(system_info.max_connections) * 1.5),
                    'reason': 'High connection usage detected',
                    'priority': 'medium'
                })
            
            # Video platform specific recommendations
            video_recommendations = [
                {
                    'setting': 'effective_cache_size',
                    'recommended_value': '2GB',
                    'reason': 'Optimize for video metadata and analytics queries',
                    'priority': 'medium'
                },
                {
                    'setting': 'maintenance_work_mem',
                    'recommended_value': '256MB',
                    'reason': 'Improve index creation and maintenance performance',
                    'priority': 'low'
                },
                {
                    'setting': 'random_page_cost',
                    'recommended_value': '1.1',
                    'reason': 'Optimize for SSD storage (assuming SSD deployment)',
                    'priority': 'low'
                }
            ]
            
            recommendations.extend(video_recommendations)
            
            return {
                'current_settings': current_settings,
                'system_info': {
                    'max_connections': system_info.max_connections,
                    'current_connections': system_info.current_connections,
                    'connection_usage_percent': round(connection_usage * 100, 1),
                    'database_size': system_info.db_size
                },
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Failed to optimize database settings: {e}")
            return {'error': str(e)}
    
    async def analyze_slow_queries(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Analyze slow queries from recent metrics
        
        Args:
            hours: Hours of history to analyze
            
        Returns:
            List of slow query analysis
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Filter slow queries from metrics
            slow_queries = [
                m for m in self._query_metrics
                if (m.timestamp > cutoff_time and 
                    m.execution_time_ms > self.thresholds['slow_query_ms'])
            ]
            
            # Group by query hash and analyze
            query_groups = {}
            for metric in slow_queries:
                if metric.query_hash not in query_groups:
                    query_groups[metric.query_hash] = []
                query_groups[metric.query_hash].append(metric)
            
            analysis = []
            for query_hash, metrics in query_groups.items():
                avg_time = sum(m.execution_time_ms for m in metrics) / len(metrics)
                max_time = max(m.execution_time_ms for m in metrics)
                total_executions = len(metrics)
                
                # Get representative query text
                sample_metric = metrics[0]
                
                analysis.append({
                    'query_hash': query_hash,
                    'query_text': sample_metric.query_text,
                    'execution_count': total_executions,
                    'avg_execution_time_ms': round(avg_time, 2),
                    'max_execution_time_ms': round(max_time, 2),
                    'total_time_ms': round(sum(m.execution_time_ms for m in metrics), 2),
                    'avg_rows_examined': round(sum(m.rows_examined for m in metrics) / len(metrics)),
                    'tables_involved': list(set(
                        table for m in metrics for table in m.table_names
                    )),
                    'optimization_suggestions': self._get_query_optimization_suggestions(sample_metric)
                })
            
            # Sort by total time impact
            analysis.sort(key=lambda x: x['total_time_ms'], reverse=True)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze slow queries: {e}")
            return []
    
    def _get_query_optimization_suggestions(self, metric: QueryPerformanceMetric) -> List[str]:
        """Get optimization suggestions for a specific query"""
        suggestions = []
        
        # High row examination suggests missing indexes
        if metric.rows_examined > self.thresholds['table_scan_rows']:
            suggestions.append("Consider adding indexes on frequently filtered columns")
        
        # Low selectivity suggests inefficient filtering
        if metric.rows_examined > 0 and metric.rows_returned / metric.rows_examined < 0.1:
            suggestions.append("Query has low selectivity - review WHERE conditions")
        
        # Video-specific suggestions
        if 'videos' in metric.table_names:
            if 'title' in metric.query_text.lower() and 'ilike' in metric.query_text.lower():
                suggestions.append("Consider full-text search index for title searches")
            
            if 'tags' in metric.query_text.lower():
                suggestions.append("Ensure GIN index exists on JSONB tags column")
        
        if 'view_sessions' in metric.table_names:
            if 'started_at' in metric.query_text.lower():
                suggestions.append("Ensure index exists on started_at for time-based queries")
        
        return suggestions
    
    async def get_table_statistics(self) -> Dict[str, Any]:
        """
        Get detailed statistics for video platform tables
        
        Returns:
            Table statistics and recommendations
        """
        try:
            # Video platform tables to analyze
            tables = ['videos', 'view_sessions', 'video_comments', 'video_likes', 'transcoding_jobs']
            
            table_stats = {}
            
            for table in tables:
                # Get table size and row count
                size_query = f"""
                    SELECT 
                        pg_size_pretty(pg_total_relation_size('{table}')) as total_size,
                        pg_total_relation_size('{table}') as total_size_bytes,
                        (SELECT reltuples::bigint FROM pg_class WHERE relname = '{table}') as estimated_rows
                """
                
                result = await self.db.execute(text(size_query))
                size_info = result.fetchone()
                
                # Get index usage statistics
                index_usage_query = f"""
                    SELECT 
                        indexrelname as index_name,
                        idx_tup_read,
                        idx_tup_fetch
                    FROM pg_stat_user_indexes 
                    WHERE relname = '{table}'
                """
                
                result = await self.db.execute(text(index_usage_query))
                index_usage = result.fetchall()
                
                table_stats[table] = {
                    'total_size': size_info.total_size,
                    'total_size_bytes': size_info.total_size_bytes,
                    'estimated_rows': size_info.estimated_rows,
                    'indexes': [
                        {
                            'name': idx.index_name,
                            'tuples_read': idx.idx_tup_read,
                            'tuples_fetched': idx.idx_tup_fetch
                        }
                        for idx in index_usage
                    ]
                }
            
            return table_stats
            
        except Exception as e:
            logger.error(f"Failed to get table statistics: {e}")
            return {}
    
    async def get_optimization_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive database optimization report
        
        Returns:
            Complete optimization report
        """
        try:
            # Gather all optimization data
            db_stats = await self.get_database_statistics()
            index_recommendations = await self.analyze_video_query_patterns()
            slow_queries = await self.analyze_slow_queries()
            table_stats = await self.get_table_statistics()
            db_settings = await self.optimize_database_settings()
            
            # Calculate optimization score
            optimization_score = self._calculate_optimization_score(db_stats, slow_queries)
            
            return {
                'generated_at': datetime.utcnow().isoformat(),
                'optimization_score': optimization_score,
                'database_statistics': db_stats.to_dict(),
                'performance_summary': {
                    'slow_queries_count': len(slow_queries),
                    'avg_query_time_ms': db_stats.avg_query_time_ms,
                    'cache_hit_ratio': db_stats.cache_hit_ratio,
                    'active_connections': db_stats.active_connections
                },
                'index_recommendations': [rec.to_dict() for rec in index_recommendations[:10]],
                'slow_query_analysis': slow_queries[:5],
                'table_statistics': table_stats,
                'configuration_recommendations': db_settings.get('recommendations', []),
                'action_items': self._generate_action_items(
                    db_stats, index_recommendations, slow_queries
                )
            }
            
        except Exception as e:
            logger.error(f"Failed to generate optimization report: {e}")
            return {'error': str(e)}
    
    def _calculate_optimization_score(self, db_stats: DatabaseStats, slow_queries: List[Dict[str, Any]]) -> float:
        """Calculate overall database optimization score (0-100)"""
        try:
            score = 100.0
            
            # Penalize slow queries
            if slow_queries:
                slow_query_penalty = min(len(slow_queries) * 5, 30)
                score -= slow_query_penalty
            
            # Penalize low cache hit ratio
            if db_stats.cache_hit_ratio < self.thresholds['cache_hit_ratio_min']:
                cache_penalty = (self.thresholds['cache_hit_ratio_min'] - db_stats.cache_hit_ratio) * 50
                score -= cache_penalty
            
            # Penalize high average query time
            if db_stats.avg_query_time_ms > 100:
                query_time_penalty = min((db_stats.avg_query_time_ms - 100) / 10, 20)
                score -= query_time_penalty
            
            return max(0.0, round(score, 1))
            
        except Exception:
            return 0.0
    
    def _generate_action_items(
        self, 
        db_stats: DatabaseStats, 
        index_recommendations: List[IndexRecommendation],
        slow_queries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate prioritized action items for optimization"""
        action_items = []
        
        # High priority items
        if slow_queries:
            action_items.append({
                'priority': 'high',
                'category': 'performance',
                'title': 'Address Slow Queries',
                'description': f'{len(slow_queries)} slow queries detected',
                'action': 'Review and optimize the slowest queries first'
            })
        
        if db_stats.cache_hit_ratio < self.thresholds['cache_hit_ratio_min']:
            action_items.append({
                'priority': 'high',
                'category': 'configuration',
                'title': 'Improve Cache Hit Ratio',
                'description': f'Cache hit ratio is {db_stats.cache_hit_ratio:.2%}',
                'action': 'Increase shared_buffers and effective_cache_size'
            })
        
        # Medium priority items
        if index_recommendations:
            top_recommendations = [r for r in index_recommendations if r.estimated_benefit > 0.7]
            if top_recommendations:
                action_items.append({
                    'priority': 'medium',
                    'category': 'indexing',
                    'title': 'Create High-Impact Indexes',
                    'description': f'{len(top_recommendations)} high-impact index recommendations',
                    'action': 'Implement recommended indexes during maintenance window'
                })
        
        # Low priority items
        if db_stats.avg_query_time_ms > 50:
            action_items.append({
                'priority': 'low',
                'category': 'monitoring',
                'title': 'Monitor Query Performance',
                'description': f'Average query time is {db_stats.avg_query_time_ms:.1f}ms',
                'action': 'Set up continuous query performance monitoring'
            })
        
        return action_items


# Dependency for FastAPI
async def get_database_optimization_service(db: AsyncSession) -> DatabaseOptimizationService:
    """Get database optimization service instance"""
    return DatabaseOptimizationService(db)