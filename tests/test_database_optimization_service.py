"""
Tests for Database Optimization Service

Tests database performance monitoring, index recommendations,
and query optimization functionality.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from server.web.app.services.database_optimization_service import (
    DatabaseOptimizationService,
    QueryPerformanceMetric,
    IndexRecommendation,
    DatabaseStats
)


@pytest.fixture
def mock_db_session():
    """Mock database session for testing"""
    return AsyncMock()


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    redis_client = AsyncMock()
    redis_client.is_connected = True
    return redis_client


@pytest.fixture
def optimization_service(mock_db_session, mock_redis_client):
    """Database optimization service instance for testing"""
    service = DatabaseOptimizationService(mock_db_session, mock_redis_client)
    return service


@pytest.fixture
def sample_query_metric():
    """Sample query performance metric"""
    return QueryPerformanceMetric(
        query_hash='abc123',
        query_text='SELECT * FROM videos WHERE visibility = %s',
        execution_time_ms=150.0,
        rows_examined=1000,
        rows_returned=50,
        timestamp=datetime.utcnow(),
        table_names=['videos']
    )


class TestDatabaseOptimizationService:
    """Test cases for DatabaseOptimizationService"""
    
    @pytest.mark.asyncio
    async def test_analyze_query_performance(self, optimization_service, mock_db_session, mock_redis_client):
        """Test query performance analysis"""
        # Setup
        query = "SELECT * FROM videos WHERE visibility = 'public'"
        
        # Mock EXPLAIN ANALYZE result
        mock_result = MagicMock()
        mock_result.fetchone.return_value = [[{
            'Plan': {
                'Actual Rows': 50,
                'Plans': [{
                    'Actual Rows': 1000,
                    'Relation Name': 'videos'
                }]
            }
        }]]
        mock_db_session.execute.return_value = mock_result
        mock_redis_client.set.return_value = True
        
        # Execute
        metric = await optimization_service.analyze_query_performance(query)
        
        # Verify
        assert metric.query_text == query
        assert metric.rows_returned == 50
        assert metric.table_names == ['videos']
        assert len(optimization_service._query_metrics) == 1
        mock_redis_client.set.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_database_statistics(self, optimization_service, mock_db_session):
        """Test getting database statistics"""
        # Setup mock results for different queries
        mock_results = {
            'database_size': MagicMock(size_bytes=1024*1024*1024),  # 1GB
            'table_count': MagicMock(count=10),
            'index_count': MagicMock(count=25),
            'active_connections': MagicMock(count=5),
            'cache_stats': MagicMock(cache_hit_ratio=0.95)
        }
        
        def mock_execute(query):
            result = MagicMock()
            query_text = str(query)
            if 'pg_database_size' in query_text:
                result.fetchone.return_value = mock_results['database_size']
            elif 'information_schema.tables' in query_text:
                result.fetchone.return_value = mock_results['table_count']
            elif 'pg_indexes' in query_text:
                result.fetchone.return_value = mock_results['index_count']
            elif 'pg_stat_activity' in query_text:
                result.fetchone.return_value = mock_results['active_connections']
            elif 'pg_statio_user_tables' in query_text:
                result.fetchone.return_value = mock_results['cache_stats']
            return result
        
        mock_db_session.execute.side_effect = mock_execute
        
        # Execute
        stats = await optimization_service.get_database_statistics()
        
        # Verify
        assert isinstance(stats, DatabaseStats)
        assert stats.total_size_mb == 1024.0  # 1GB in MB
        assert stats.table_count == 10
        assert stats.index_count == 25
        assert stats.active_connections == 5
        assert stats.cache_hit_ratio == 0.95
    
    @pytest.mark.asyncio
    async def test_analyze_video_query_patterns(self, optimization_service):
        """Test video query pattern analysis"""
        # Execute
        recommendations = await optimization_service.analyze_video_query_patterns()
        
        # Verify
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # Check for video-specific recommendations
        table_names = [rec.table_name for rec in recommendations]
        assert 'videos' in table_names
        assert 'view_sessions' in table_names
        
        # Check for GIN index recommendation for tags
        gin_recommendations = [rec for rec in recommendations if rec.index_type == 'gin']
        assert len(gin_recommendations) > 0
        
        # Verify recommendation structure
        for rec in recommendations[:3]:
            assert isinstance(rec, IndexRecommendation)
            assert rec.table_name
            assert rec.columns
            assert rec.index_type in ['btree', 'gin', 'gist', 'hash']
            assert 0.0 <= rec.estimated_benefit <= 1.0
    
    @pytest.mark.asyncio
    async def test_check_existing_indexes(self, optimization_service, mock_db_session):
        """Test checking existing database indexes"""
        # Setup
        mock_indexes = [
            MagicMock(
                tablename='videos',
                indexname='videos_pkey',
                indexdef='CREATE UNIQUE INDEX videos_pkey ON videos USING btree (id)',
                schemaname='public'
            ),
            MagicMock(
                tablename='videos',
                indexname='idx_videos_creator_id',
                indexdef='CREATE INDEX idx_videos_creator_id ON videos USING btree (creator_id)',
                schemaname='public'
            )
        ]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_indexes
        mock_db_session.execute.return_value = mock_result
        
        # Execute
        indexes = await optimization_service.check_existing_indexes()
        
        # Verify
        assert 'videos' in indexes
        assert len(indexes['videos']) == 2
        assert indexes['videos'][0]['name'] == 'videos_pkey'
        assert indexes['videos'][1]['name'] == 'idx_videos_creator_id'
    
    @pytest.mark.asyncio
    async def test_create_recommended_indexes(self, optimization_service, mock_db_session):
        """Test creating recommended indexes"""
        # Setup
        recommendations = [
            IndexRecommendation(
                table_name='videos',
                columns=['visibility', 'status'],
                index_type='btree',
                reason='Test index',
                estimated_benefit=0.8,
                query_patterns=['test_pattern']
            )
        ]
        
        # Mock existing indexes check
        optimization_service.check_existing_indexes = AsyncMock(return_value={'videos': []})
        mock_db_session.execute.return_value = None
        mock_db_session.commit.return_value = None
        
        # Execute
        results = await optimization_service.create_recommended_indexes(recommendations)
        
        # Verify
        assert 'created' in results
        assert 'failed' in results
        assert 'skipped' in results
        assert len(results['created']) == 1
        assert results['created'][0]['table'] == 'videos'
        assert results['created'][0]['columns'] == ['visibility', 'status']
    
    @pytest.mark.asyncio
    async def test_optimize_database_settings(self, optimization_service, mock_db_session):
        """Test database settings optimization"""
        # Setup
        mock_settings_result = MagicMock()
        mock_settings_result.fetchall.return_value = [
            MagicMock(name='shared_buffers', setting='16384'),  # 128MB in 8KB blocks
            MagicMock(name='max_connections', setting='100')
        ]
        
        mock_system_result = MagicMock()
        mock_system_result.fetchone.return_value = MagicMock(
            max_connections='100',
            current_connections='50',
            db_size='500MB'
        )
        
        def mock_execute(query):
            query_text = str(query)
            if 'pg_settings' in query_text:
                return mock_settings_result
            else:
                return mock_system_result
        
        mock_db_session.execute.side_effect = mock_execute
        
        # Execute
        optimization = await optimization_service.optimize_database_settings()
        
        # Verify
        assert 'current_settings' in optimization
        assert 'system_info' in optimization
        assert 'recommendations' in optimization
        assert optimization['system_info']['connection_usage_percent'] == 50.0
    
    @pytest.mark.asyncio
    async def test_analyze_slow_queries(self, optimization_service, sample_query_metric):
        """Test slow query analysis"""
        # Setup - add slow queries to metrics
        slow_metric = QueryPerformanceMetric(
            query_hash='slow123',
            query_text='SELECT * FROM videos WHERE title ILIKE %s',
            execution_time_ms=2000.0,  # Slow query
            rows_examined=50000,
            rows_returned=10,
            timestamp=datetime.utcnow(),
            table_names=['videos']
        )
        
        optimization_service._query_metrics = [slow_metric, sample_query_metric]
        optimization_service.thresholds['slow_query_ms'] = 1000
        
        # Execute
        slow_queries = await optimization_service.analyze_slow_queries(hours=24)
        
        # Verify
        assert len(slow_queries) == 1  # Only one query is slow
        slow_query = slow_queries[0]
        assert slow_query['query_hash'] == 'slow123'
        assert slow_query['avg_execution_time_ms'] == 2000.0
        assert slow_query['execution_count'] == 1
        assert 'optimization_suggestions' in slow_query
    
    def test_get_query_optimization_suggestions(self, optimization_service):
        """Test query optimization suggestions"""
        # Test high row examination
        metric = QueryPerformanceMetric(
            query_hash='test123',
            query_text='SELECT * FROM videos WHERE title ILIKE %s',
            execution_time_ms=1500.0,
            rows_examined=50000,  # High examination
            rows_returned=10,     # Low return
            timestamp=datetime.utcnow(),
            table_names=['videos']
        )
        
        suggestions = optimization_service._get_query_optimization_suggestions(metric)
        
        assert len(suggestions) > 0
        assert any('index' in suggestion.lower() for suggestion in suggestions)
        assert any('selectivity' in suggestion.lower() for suggestion in suggestions)
    
    @pytest.mark.asyncio
    async def test_get_table_statistics(self, optimization_service, mock_db_session):
        """Test getting table statistics"""
        # Setup
        def mock_execute(query):
            result = MagicMock()
            query_text = str(query)
            
            if 'pg_total_relation_size' in query_text:
                result.fetchone.return_value = MagicMock(
                    total_size='100 MB',
                    total_size_bytes=100*1024*1024,
                    estimated_rows=10000
                )
            elif 'pg_stat_user_indexes' in query_text:
                result.fetchall.return_value = [
                    MagicMock(
                        index_name='idx_test',
                        idx_tup_read=1000,
                        idx_tup_fetch=800
                    )
                ]
            
            return result
        
        mock_db_session.execute.side_effect = mock_execute
        
        # Execute
        stats = await optimization_service.get_table_statistics()
        
        # Verify
        assert 'videos' in stats
        video_stats = stats['videos']
        assert video_stats['total_size'] == '100 MB'
        assert video_stats['estimated_rows'] == 10000
        assert len(video_stats['indexes']) == 1
    
    @pytest.mark.asyncio
    async def test_get_optimization_report(self, optimization_service):
        """Test generating optimization report"""
        # Mock all the required methods
        optimization_service.get_database_statistics = AsyncMock(return_value=DatabaseStats(
            total_size_mb=1024.0,
            table_count=10,
            index_count=25,
            active_connections=5,
            slow_queries_count=2,
            cache_hit_ratio=0.95,
            avg_query_time_ms=50.0
        ))
        
        optimization_service.analyze_video_query_patterns = AsyncMock(return_value=[
            IndexRecommendation(
                table_name='videos',
                columns=['tags'],
                index_type='gin',
                reason='Test recommendation',
                estimated_benefit=0.9,
                query_patterns=['video_search']
            )
        ])
        
        optimization_service.analyze_slow_queries = AsyncMock(return_value=[])
        optimization_service.get_table_statistics = AsyncMock(return_value={'videos': {}})
        optimization_service.optimize_database_settings = AsyncMock(return_value={'recommendations': []})
        
        # Execute
        report = await optimization_service.get_optimization_report()
        
        # Verify
        assert 'generated_at' in report
        assert 'optimization_score' in report
        assert 'database_statistics' in report
        assert 'performance_summary' in report
        assert 'index_recommendations' in report
        assert 'action_items' in report
        
        # Check optimization score
        assert 0 <= report['optimization_score'] <= 100
    
    def test_calculate_optimization_score(self, optimization_service):
        """Test optimization score calculation"""
        # Test good performance
        good_stats = DatabaseStats(
            total_size_mb=1024.0,
            table_count=10,
            index_count=25,
            active_connections=5,
            slow_queries_count=0,
            cache_hit_ratio=0.95,
            avg_query_time_ms=50.0
        )
        
        score = optimization_service._calculate_optimization_score(good_stats, [])
        assert score >= 90
        
        # Test poor performance
        poor_stats = DatabaseStats(
            total_size_mb=1024.0,
            table_count=10,
            index_count=25,
            active_connections=5,
            slow_queries_count=10,
            cache_hit_ratio=0.70,
            avg_query_time_ms=500.0
        )
        
        slow_queries = [{'query_hash': f'slow{i}'} for i in range(10)]
        score = optimization_service._calculate_optimization_score(poor_stats, slow_queries)
        assert score < 50
    
    def test_generate_action_items(self, optimization_service):
        """Test action item generation"""
        # Setup test data
        db_stats = DatabaseStats(
            total_size_mb=1024.0,
            table_count=10,
            index_count=25,
            active_connections=5,
            slow_queries_count=5,
            cache_hit_ratio=0.80,  # Below threshold
            avg_query_time_ms=150.0
        )
        
        index_recommendations = [
            IndexRecommendation(
                table_name='videos',
                columns=['tags'],
                index_type='gin',
                reason='High impact recommendation',
                estimated_benefit=0.9,
                query_patterns=['video_search']
            )
        ]
        
        slow_queries = [{'query_hash': f'slow{i}'} for i in range(5)]
        
        # Execute
        action_items = optimization_service._generate_action_items(
            db_stats, index_recommendations, slow_queries
        )
        
        # Verify
        assert len(action_items) > 0
        
        # Check for high priority items
        high_priority_items = [item for item in action_items if item['priority'] == 'high']
        assert len(high_priority_items) > 0
        
        # Verify action item structure
        for item in action_items:
            assert 'priority' in item
            assert 'category' in item
            assert 'title' in item
            assert 'description' in item
            assert 'action' in item
    
    def test_extract_rows_examined(self, optimization_service):
        """Test extracting rows examined from query plan"""
        # Test simple plan
        simple_plan = {'Actual Rows': 100}
        rows = optimization_service._extract_rows_examined(simple_plan)
        assert rows == 100
        
        # Test nested plan
        nested_plan = {
            'Actual Rows': 50,
            'Plans': [
                {'Actual Rows': 200},
                {'Actual Rows': 150, 'Plans': [{'Actual Rows': 75}]}
            ]
        }
        rows = optimization_service._extract_rows_examined(nested_plan)
        assert rows == 475  # 50 + 200 + 150 + 75
    
    def test_extract_table_names(self, optimization_service):
        """Test extracting table names from query plan"""
        # Test simple plan
        simple_plan = {'Relation Name': 'videos'}
        tables = optimization_service._extract_table_names(simple_plan)
        assert tables == ['videos']
        
        # Test nested plan with multiple tables
        nested_plan = {
            'Relation Name': 'videos',
            'Plans': [
                {'Relation Name': 'users'},
                {'Plans': [{'Relation Name': 'view_sessions'}]}
            ]
        }
        tables = optimization_service._extract_table_names(nested_plan)
        assert set(tables) == {'videos', 'users', 'view_sessions'}


class TestQueryPerformanceMetric:
    """Test cases for QueryPerformanceMetric"""
    
    def test_to_dict(self, sample_query_metric):
        """Test converting metric to dictionary"""
        metric_dict = sample_query_metric.to_dict()
        
        assert metric_dict['query_hash'] == 'abc123'
        assert metric_dict['execution_time_ms'] == 150.0
        assert metric_dict['rows_examined'] == 1000
        assert metric_dict['rows_returned'] == 50
        assert metric_dict['table_names'] == ['videos']
        assert 'timestamp' in metric_dict


class TestIndexRecommendation:
    """Test cases for IndexRecommendation"""
    
    def test_to_dict(self):
        """Test converting recommendation to dictionary"""
        recommendation = IndexRecommendation(
            table_name='videos',
            columns=['visibility', 'status'],
            index_type='btree',
            reason='Optimize video queries',
            estimated_benefit=0.8,
            query_patterns=['video_search']
        )
        
        rec_dict = recommendation.to_dict()
        
        assert rec_dict['table_name'] == 'videos'
        assert rec_dict['columns'] == ['visibility', 'status']
        assert rec_dict['index_type'] == 'btree'
        assert rec_dict['estimated_benefit'] == 0.8
        assert rec_dict['query_patterns'] == ['video_search']


class TestDatabaseStats:
    """Test cases for DatabaseStats"""
    
    def test_to_dict(self):
        """Test converting stats to dictionary"""
        stats = DatabaseStats(
            total_size_mb=1024.0,
            table_count=10,
            index_count=25,
            active_connections=5,
            slow_queries_count=2,
            cache_hit_ratio=0.95,
            avg_query_time_ms=50.0
        )
        
        stats_dict = stats.to_dict()
        
        assert stats_dict['total_size_mb'] == 1024.0
        assert stats_dict['table_count'] == 10
        assert stats_dict['cache_hit_ratio'] == 0.95
        assert stats_dict['avg_query_time_ms'] == 50.0


if __name__ == '__main__':
    pytest.main([__file__])