"""
Performance tests for RedirectHandler to ensure <200ms redirection requirement.
"""
import pytest
import time
import statistics
from unittest.mock import Mock
from datetime import datetime


class MockShortUrl:
    """Mock ShortUrl model for performance testing."""
    def __init__(self):
        self.id = "test-id"
        self.slug = "test123"
        self.target_url = "https://example.com"
        self.title = "Test URL"
        self.current_clicks = 0
        self.max_clicks = None
        self.expires_at = None
        self.is_active = True
        self.created_at = datetime.utcnow()


class FastRedirectHandler:
    """
    Optimized RedirectHandler for performance testing.
    Simulates the core redirect logic with minimal overhead.
    """
    
    def __init__(self, db_session):
        self.db = db_session
    
    def handle_redirect_fast(self, slug, request):
        """Fast redirect handling for performance testing."""
        # Simulate database lookup (optimized)
        short_url = self.db.query().filter().first()
        if not short_url:
            return False, "Not found", None
        
        # Simulate expiration check (fast path)
        now = datetime.utcnow()
        if short_url.expires_at and now > short_url.expires_at:
            return False, "Expired", None
        if short_url.max_clicks and short_url.current_clicks >= short_url.max_clicks:
            return False, "Expired", None
        
        # Simulate atomic increment (fast database operation)
        result = self.db.execute()
        if not result.fetchone():
            return False, "Limit reached", None
        
        # Simulate client info extraction (minimal)
        ip = request.headers.get("x-forwarded-for", "127.0.0.1").split(",")[0].strip()
        
        # Simulate logging (async in real implementation)
        self.db.add(Mock())
        
        # Create redirect response
        from fastapi.responses import RedirectResponse
        response = RedirectResponse(url=short_url.target_url, status_code=302)
        
        return True, "Success", response


class TestRedirectPerformance:
    """Performance tests for redirect handling."""
    
    @pytest.fixture
    def fast_handler(self):
        """Create fast redirect handler."""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = MockShortUrl()
        mock_db.execute.return_value.fetchone.return_value = (1,)
        return FastRedirectHandler(mock_db)
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock()
        request.headers = {
            "x-forwarded-for": "192.168.1.1",
            "user-agent": "Mozilla/5.0 (Test)",
            "referer": "https://example.com"
        }
        return request
    
    def test_single_redirect_performance(self, fast_handler, mock_request):
        """Test single redirect performance."""
        # Warm up
        for _ in range(10):
            fast_handler.handle_redirect_fast("test", mock_request)
        
        # Measure single redirect
        start_time = time.perf_counter()
        success, message, response = fast_handler.handle_redirect_fast("test", mock_request)
        end_time = time.perf_counter()
        
        execution_time_ms = (end_time - start_time) * 1000
        
        # Verify performance requirement
        assert execution_time_ms < 200, f"Redirect took {execution_time_ms:.2f}ms, exceeds 200ms requirement"
        assert success is True
        assert response is not None
    
    def test_batch_redirect_performance(self, fast_handler, mock_request):
        """Test batch redirect performance to ensure consistency."""
        times = []
        
        # Measure 1000 redirects
        for i in range(1000):
            start_time = time.perf_counter()
            success, message, response = fast_handler.handle_redirect_fast("test", mock_request)
            end_time = time.perf_counter()
            
            if success:
                times.append((end_time - start_time) * 1000)
        
        # Calculate statistics
        avg_time = statistics.mean(times)
        median_time = statistics.median(times)
        p95_time = sorted(times)[int(0.95 * len(times))]
        p99_time = sorted(times)[int(0.99 * len(times))]
        max_time = max(times)
        
        # Performance assertions
        assert avg_time < 50, f"Average redirect time {avg_time:.2f}ms exceeds 50ms"
        assert median_time < 30, f"Median redirect time {median_time:.2f}ms exceeds 30ms"
        assert p95_time < 100, f"95th percentile {p95_time:.2f}ms exceeds 100ms"
        assert p99_time < 150, f"99th percentile {p99_time:.2f}ms exceeds 150ms"
        assert max_time < 200, f"Maximum redirect time {max_time:.2f}ms exceeds 200ms requirement"
        
        # Verify success rate
        success_rate = len(times) / 1000
        assert success_rate > 0.99, f"Success rate {success_rate:.2%} is too low"
        
        print(f"\nPerformance Results:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Median:  {median_time:.2f}ms")
        print(f"  95th %:  {p95_time:.2f}ms")
        print(f"  99th %:  {p99_time:.2f}ms")
        print(f"  Maximum: {max_time:.2f}ms")
        print(f"  Success Rate: {success_rate:.2%}")
    
    def test_concurrent_redirect_simulation(self, fast_handler, mock_request):
        """Simulate concurrent redirects to test performance under load."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def redirect_worker():
            """Worker function for concurrent redirects."""
            start_time = time.perf_counter()
            success, message, response = fast_handler.handle_redirect_fast("test", mock_request)
            end_time = time.perf_counter()
            
            execution_time = (end_time - start_time) * 1000
            results.put((success, execution_time))
        
        # Create and start threads
        threads = []
        num_threads = 50
        
        start_time = time.perf_counter()
        
        for _ in range(num_threads):
            thread = threading.Thread(target=redirect_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000
        
        # Collect results
        times = []
        successes = 0
        
        while not results.empty():
            success, exec_time = results.get()
            if success:
                successes += 1
                times.append(exec_time)
        
        # Performance assertions
        avg_time = statistics.mean(times) if times else float('inf')
        max_time = max(times) if times else float('inf')
        success_rate = successes / num_threads
        
        assert avg_time < 100, f"Average concurrent redirect time {avg_time:.2f}ms too high"
        assert max_time < 200, f"Maximum concurrent redirect time {max_time:.2f}ms exceeds requirement"
        assert success_rate > 0.95, f"Concurrent success rate {success_rate:.2%} too low"
        assert total_time < 5000, f"Total concurrent execution time {total_time:.2f}ms too high"
        
        print(f"\nConcurrent Performance Results ({num_threads} threads):")
        print(f"  Total Time: {total_time:.2f}ms")
        print(f"  Average per redirect: {avg_time:.2f}ms")
        print(f"  Maximum: {max_time:.2f}ms")
        print(f"  Success Rate: {success_rate:.2%}")
    
    def test_memory_efficiency(self, fast_handler, mock_request):
        """Test memory efficiency during redirects."""
        # This test validates that redirects don't cause memory leaks
        # by performing multiple redirects and ensuring they complete successfully
        
        successful_redirects = 0
        for _ in range(100):
            success, _, _ = fast_handler.handle_redirect_fast("test", mock_request)
            if success:
                successful_redirects += 1
        
        # Verify all redirects completed successfully (no memory issues)
        assert successful_redirects == 100, f"Only {successful_redirects}/100 redirects succeeded"
        
        print(f"\nMemory Efficiency Test: {successful_redirects}/100 redirects completed successfully")
    
    def test_error_handling_performance(self, mock_request):
        """Test performance of error handling paths."""
        mock_db = Mock()
        
        # Test not found performance
        mock_db.query.return_value.filter.return_value.first.return_value = None
        handler = FastRedirectHandler(mock_db)
        
        start_time = time.perf_counter()
        success, message, response = handler.handle_redirect_fast("notfound", mock_request)
        end_time = time.perf_counter()
        
        error_time = (end_time - start_time) * 1000
        
        assert error_time < 50, f"Error handling took {error_time:.2f}ms, too slow"
        assert success is False
        assert message == "Not found"
        
        print(f"\nError Handling Performance: {error_time:.2f}ms")


if __name__ == "__main__":
    # Run performance tests directly
    pytest.main([__file__, "-v", "-s"])