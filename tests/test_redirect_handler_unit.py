"""
Unit tests for RedirectHandler - URL redirection with analytics tracking.
Tests core functionality without database dependencies.
"""
import pytest
import time
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request
from fastapi.responses import RedirectResponse


class MockShortUrl:
    """Mock ShortUrl model for testing."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 'test-id')
        self.slug = kwargs.get('slug', 'test123')
        self.target_url = kwargs.get('target_url', 'https://example.com')
        self.title = kwargs.get('title', 'Test URL')
        self.current_clicks = kwargs.get('current_clicks', 0)
        self.max_clicks = kwargs.get('max_clicks', None)
        self.expires_at = kwargs.get('expires_at', None)
        self.is_active = kwargs.get('is_active', True)
        self.created_at = kwargs.get('created_at', datetime.utcnow())


class MockShortUrlAccessLog:
    """Mock ShortUrlAccessLog model for testing."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockAnalyticsCollector:
    """Mock AnalyticsCollector for testing."""
    def __init__(self, db_session):
        self.db = db_session
    
    def track_resource_access(self, **kwargs):
        pass


class RedirectHandlerForTesting:
    """
    Simplified RedirectHandler for unit testing.
    Contains core logic without external dependencies.
    """
    
    def __init__(self, db_session, analytics_collector=None):
        self.db = db_session
        self.analytics = analytics_collector or MockAnalyticsCollector(db_session)
    
    def handle_redirect(self, slug, request, user_id=None):
        """Handle URL redirection with analytics tracking."""
        try:
            # Get the short URL record
            short_url = self._get_active_short_url(slug)
            if not short_url:
                return False, "Short URL not found", None
            
            # Check if URL has expired
            if self._is_expired(short_url):
                return False, "Short URL has expired", None
            
            # Extract client information
            client_info = self._extract_client_info(request)
            
            # Atomically increment click count and check limits
            success, error_msg = self._increment_click_count(short_url)
            if not success:
                return False, error_msg, None
            
            # Log access for analytics
            self._log_access(short_url, client_info, user_id)
            
            # Track analytics event
            self._track_redirect_event(short_url, client_info, user_id)
            
            # Create redirect response
            redirect_response = RedirectResponse(
                url=short_url.target_url,
                status_code=302
            )
            
            return True, "Redirect successful", redirect_response
            
        except Exception as e:
            return False, "Internal server error", None
    
    def _get_active_short_url(self, slug):
        """Get active short URL by slug."""
        return self.db.query().filter().first()
    
    def _is_expired(self, short_url):
        """Check if short URL has expired."""
        now = datetime.utcnow()
        
        # Check time-based expiration
        if short_url.expires_at and now > short_url.expires_at:
            return True
        
        # Check click-based expiration
        if short_url.max_clicks and short_url.current_clicks >= short_url.max_clicks:
            return True
        
        return False
    
    def _extract_client_info(self, request):
        """Extract client information from request."""
        client_ip = self._get_client_ip(request)
        ip_hash = self._hash_ip(client_ip) if client_ip else None
        user_agent = request.headers.get("user-agent", "")
        referrer = request.headers.get("referer", "")
        country_code = self._get_country_code(client_ip)
        
        return {
            "ip_address": client_ip,
            "ip_hash": ip_hash,
            "user_agent": user_agent,
            "referrer": referrer,
            "country_code": country_code
        }
    
    def _get_client_ip(self, request):
        """Get client IP address, handling proxy headers."""
        proxy_headers = [
            "x-forwarded-for",
            "x-real-ip",
            "x-client-ip",
            "cf-connecting-ip",
            "true-client-ip"
        ]
        
        for header in proxy_headers:
            ip = request.headers.get(header)
            if ip:
                return ip.split(",")[0].strip()
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return None
    
    def _hash_ip(self, ip_address):
        """Hash IP address for privacy compliance."""
        salt = "url_shortener_salt_2024"
        return hashlib.sha256(f"{ip_address}{salt}".encode()).hexdigest()
    
    def _get_country_code(self, ip_address):
        """Get country code from IP address (placeholder)."""
        return None
    
    def _increment_click_count(self, short_url):
        """Atomically increment click count and check limits."""
        try:
            result = self.db.execute()
            updated_row = result.fetchone()
            
            if not updated_row:
                if short_url.max_clicks and short_url.current_clicks >= short_url.max_clicks:
                    return False, "Short URL has reached its click limit"
                elif short_url.expires_at and datetime.utcnow() > short_url.expires_at:
                    return False, "Short URL has expired"
                else:
                    return False, "Unable to process redirect"
            
            short_url.current_clicks = updated_row[0]
            self.db.commit()
            return True, None
            
        except Exception as e:
            self.db.rollback()
            return False, "Database error"
    
    def _log_access(self, short_url, client_info, user_id=None):
        """Log access to database for analytics."""
        try:
            access_log = MockShortUrlAccessLog(
                short_url_id=short_url.id,
                ip_hash=client_info.get("ip_hash"),
                user_agent=client_info.get("user_agent"),
                referrer=client_info.get("referrer"),
                country_code=client_info.get("country_code"),
                accessed_at=datetime.utcnow(),
                metadata={
                    "user_id": user_id,
                    "slug": short_url.slug,
                    "target_url": short_url.target_url,
                    "click_number": short_url.current_clicks
                }
            )
            
            self.db.add(access_log)
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
    
    def _track_redirect_event(self, short_url, client_info, user_id=None):
        """Track redirect event in analytics system."""
        try:
            self.analytics.track_resource_access(
                resource_type="short_url",
                resource_id=str(short_url.id),
                access_type="redirect",
                user_id=user_id,
                ip_address=client_info.get("ip_address"),
                user_agent=client_info.get("user_agent"),
                referrer=client_info.get("referrer")
            )
        except Exception as e:
            pass


class TestRedirectHandlerCore:
    """Test core RedirectHandler functionality."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.execute.return_value.fetchone.return_value = (1,)
        return db
    
    @pytest.fixture
    def mock_analytics(self):
        """Mock analytics collector."""
        return Mock(spec=MockAnalyticsCollector)
    
    @pytest.fixture
    def redirect_handler(self, mock_db, mock_analytics):
        """Create RedirectHandler instance."""
        return RedirectHandlerForTesting(mock_db, mock_analytics)
    
    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request."""
        request = Mock(spec=Request)
        request.headers = {
            "user-agent": "Mozilla/5.0 (Test Browser)",
            "referer": "https://example.com",
            "x-forwarded-for": "192.168.1.1"
        }
        request.client = Mock()
        request.client.host = "192.168.1.1"
        return request
    
    @pytest.fixture
    def sample_short_url(self):
        """Create sample short URL."""
        return MockShortUrl(
            id="123e4567-e89b-12d3-a456-426614174000",
            slug="test123",
            target_url="https://example.com",
            title="Test URL",
            current_clicks=5,
            max_clicks=None,
            expires_at=None,
            is_active=True,
            created_at=datetime.utcnow()
        )
    
    def test_successful_redirect(self, redirect_handler, mock_db, mock_analytics, mock_request, sample_short_url):
        """Test successful URL redirection."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_short_url
        mock_db.execute.return_value.fetchone.return_value = (6,)
        
        # Execute
        success, message, response = redirect_handler.handle_redirect("test123", mock_request)
        
        # Verify
        assert success is True
        assert message == "Redirect successful"
        assert isinstance(response, RedirectResponse)
        assert response.headers["location"] == "https://example.com"
        assert response.status_code == 302
        
        # Verify analytics tracking
        mock_analytics.track_resource_access.assert_called_once()
        
        # Verify database operations
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
    
    def test_redirect_not_found(self, redirect_handler, mock_db, mock_request):
        """Test redirect when URL not found."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Execute
        success, message, response = redirect_handler.handle_redirect("nonexistent", mock_request)
        
        # Verify
        assert success is False
        assert message == "Short URL not found"
        assert response is None
    
    def test_redirect_time_expired(self, redirect_handler, mock_db, mock_request, sample_short_url):
        """Test redirect when URL is time-expired."""
        # Setup - URL expired 1 hour ago
        sample_short_url.expires_at = datetime.utcnow() - timedelta(hours=1)
        mock_db.query.return_value.filter.return_value.first.return_value = sample_short_url
        
        # Execute
        success, message, response = redirect_handler.handle_redirect("test123", mock_request)
        
        # Verify
        assert success is False
        assert message == "Short URL has expired"
        assert response is None
    
    def test_redirect_click_expired(self, redirect_handler, mock_db, mock_request, sample_short_url):
        """Test redirect when URL has reached click limit."""
        # Setup - URL at click limit
        sample_short_url.max_clicks = 5
        sample_short_url.current_clicks = 5
        mock_db.query.return_value.filter.return_value.first.return_value = sample_short_url
        
        # Execute
        success, message, response = redirect_handler.handle_redirect("test123", mock_request)
        
        # Verify
        assert success is False
        assert message == "Short URL has expired"
        assert response is None
    
    def test_client_info_extraction(self, redirect_handler, mock_request):
        """Test client information extraction from request."""
        # Execute
        client_info = redirect_handler._extract_client_info(mock_request)
        
        # Verify
        assert client_info["ip_address"] == "192.168.1.1"
        assert client_info["user_agent"] == "Mozilla/5.0 (Test Browser)"
        assert client_info["referrer"] == "https://example.com"
        assert client_info["ip_hash"] is not None
        assert len(client_info["ip_hash"]) == 64  # SHA-256 hash length
    
    def test_ip_hashing_privacy(self, redirect_handler):
        """Test IP address hashing for privacy."""
        # Test same IP produces same hash
        hash1 = redirect_handler._hash_ip("192.168.1.1")
        hash2 = redirect_handler._hash_ip("192.168.1.1")
        assert hash1 == hash2
        
        # Test different IPs produce different hashes
        hash3 = redirect_handler._hash_ip("192.168.1.2")
        assert hash1 != hash3
        
        # Test hash is not reversible (not the original IP)
        assert hash1 != "192.168.1.1"
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_proxy_header_handling(self, redirect_handler):
        """Test handling of various proxy headers."""
        # Test X-Forwarded-For with multiple IPs
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "203.0.113.1, 192.168.1.1, 10.0.0.1"}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        ip = redirect_handler._get_client_ip(request)
        assert ip == "203.0.113.1"  # Should take first IP
        
        # Test Cloudflare header
        request.headers = {"cf-connecting-ip": "203.0.113.2"}
        ip = redirect_handler._get_client_ip(request)
        assert ip == "203.0.113.2"
        
        # Test fallback to client.host
        request.headers = {}
        ip = redirect_handler._get_client_ip(request)
        assert ip == "127.0.0.1"
    
    def test_performance_requirement(self, redirect_handler, mock_db, mock_analytics, mock_request, sample_short_url):
        """Test that redirection meets <200ms performance requirement."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_short_url
        mock_db.execute.return_value.fetchone.return_value = (6,)
        
        # Measure execution time
        start_time = time.time()
        success, message, response = redirect_handler.handle_redirect("test123", mock_request)
        end_time = time.time()
        
        execution_time_ms = (end_time - start_time) * 1000
        
        # Verify performance (allowing some margin for test overhead)
        assert execution_time_ms < 50  # Much less than 200ms requirement
        assert success is True
    
    def test_error_handling_database_error(self, redirect_handler, mock_db, mock_request, sample_short_url):
        """Test error handling for database errors."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_short_url
        mock_db.execute.side_effect = Exception("Database connection error")
        
        # Execute
        success, message, response = redirect_handler.handle_redirect("test123", mock_request)
        
        # Verify
        assert success is False
        assert message == "Database error"
        assert response is None
    
    def test_error_handling_analytics_failure(self, redirect_handler, mock_db, mock_analytics, mock_request, sample_short_url):
        """Test that analytics failures don't break redirection."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_short_url
        mock_db.execute.return_value.fetchone.return_value = (6,)
        mock_analytics.track_resource_access.side_effect = Exception("Analytics error")
        
        # Execute
        success, message, response = redirect_handler.handle_redirect("test123", mock_request)
        
        # Verify redirect still works despite analytics failure
        assert success is True
        assert message == "Redirect successful"
        assert isinstance(response, RedirectResponse)


class TestRedirectHandlerPerformance:
    """Performance-focused tests for RedirectHandler."""
    
    def test_redirect_performance_benchmark(self):
        """Benchmark redirect performance to ensure <200ms requirement."""
        mock_db = Mock()
        redirect_handler = RedirectHandlerForTesting(mock_db)
        
        # Setup fast mock responses
        sample_url = MockShortUrl(
            id="test-id",
            target_url="https://example.com",
            expires_at=None,
            max_clicks=None,
            current_clicks=0,
            is_active=True,
            slug="test"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_url
        mock_db.execute.return_value.fetchone.return_value = (1,)
        
        mock_request = Mock()
        mock_request.headers = {"user-agent": "test"}
        mock_request.client = Mock()
        mock_request.client.host = "127.0.0.1"
        
        # Measure multiple iterations
        times = []
        for _ in range(100):
            start = time.time()
            success, _, response = redirect_handler.handle_redirect("test", mock_request)
            end = time.time()
            
            if success:
                times.append((end - start) * 1000)  # Convert to milliseconds
        
        # Verify performance
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        assert avg_time < 10  # Average should be much less than 200ms
        assert max_time < 50   # Even worst case should be well under 200ms
        assert len(times) > 90  # Most requests should succeed
    
    def test_hash_performance(self):
        """Test IP hashing performance."""
        redirect_handler = RedirectHandlerForTesting(Mock())
        
        # Test hashing performance
        start_time = time.time()
        for i in range(1000):
            hash_result = redirect_handler._hash_ip(f"192.168.1.{i % 255}")
        end_time = time.time()
        
        avg_time_per_hash = ((end_time - start_time) / 1000) * 1000  # ms
        assert avg_time_per_hash < 1  # Should be very fast
    
    def test_client_info_extraction_performance(self):
        """Test client info extraction performance."""
        redirect_handler = RedirectHandlerForTesting(Mock())
        
        mock_request = Mock()
        mock_request.headers = {
            "user-agent": "Mozilla/5.0 (Test Browser)",
            "referer": "https://example.com",
            "x-forwarded-for": "192.168.1.1"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Test extraction performance
        start_time = time.time()
        for _ in range(1000):
            client_info = redirect_handler._extract_client_info(mock_request)
        end_time = time.time()
        
        avg_time = ((end_time - start_time) / 1000) * 1000  # ms
        assert avg_time < 5  # Should be very fast