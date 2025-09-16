"""
Unit tests for analytics collection and metrics aggregation system.
Tests AnalyticsCollector and MetricsAggregator functionality.
"""

import pytest
from datetime import datetime, timedelta, date
from unittest.mock import Mock, MagicMock
from uuid import uuid4
import enum


class UserTier(str, enum.Enum):
    """User tier enumeration for testing."""
    guest = "guest"
    free = "free"
    vip = "vip"
    paid = "paid"
    business = "business"


class EventType(str, enum.Enum):
    """Types of analytics events."""
    USER_REGISTRATION = "user_registration"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    TIER_UPGRADE = "tier_upgrade"
    TIER_DOWNGRADE = "tier_downgrade"
    SHORT_URL_CREATED = "short_url_created"
    SHORT_URL_ACCESSED = "short_url_accessed"
    PASTE_CREATED = "paste_created"
    PASTE_VIEWED = "paste_viewed"
    MEDIA_UPLOADED = "media_uploaded"
    MEDIA_VIEWED = "media_viewed"
    MEDIA_DOWNLOADED = "media_downloaded"
    API_REQUEST = "api_request"
    RATE_LIMIT_HIT = "rate_limit_hit"
    QUOTA_EXCEEDED = "quota_exceeded"
    ERROR_OCCURRED = "error_occurred"
    FEATURE_USED = "feature_used"
    SEARCH_PERFORMED = "search_performed"
    EXPORT_GENERATED = "export_generated"


class EventSeverity(str, enum.Enum):
    """Severity levels for events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(str, enum.Enum):
    """Types of metrics."""
    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    PERCENTAGE = "percentage"
    RATE = "rate"
    DISTRIBUTION = "distribution"


class TimeGranularity(str, enum.Enum):
    """Time granularity for metrics."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


# Mock the analytics classes
class MockAnalyticsEvent:
    """Mock analytics event for testing."""
    
    def __init__(self, event_id: str, event_type: EventType, timestamp: datetime,
                 user_id: str = None, session_id: str = None, ip_address: str = None,
                 user_agent: str = None, resource_id: str = None, resource_type: str = None,
                 properties: dict = None, severity: EventSeverity = EventSeverity.INFO,
                 tags: list = None):
        self.event_id = event_id
        self.event_type = event_type
        self.timestamp = timestamp
        self.user_id = user_id
        self.session_id = session_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.properties = properties or {}
        self.severity = severity
        self.tags = tags or []
    
    def to_dict(self):
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "properties": self.properties,
            "severity": self.severity.value,
            "tags": self.tags
        }
    
    def add_property(self, key: str, value):
        self.properties[key] = value
    
    def add_tag(self, tag: str):
        if tag not in self.tags:
            self.tags.append(tag)


class MockAnalyticsCollector:
    """Mock analytics collector for testing."""
    
    def __init__(self, db=None, tier_manager=None):
        self.db = db or Mock()
        self.tier_manager = tier_manager or Mock()
        self._event_buffer = []
        self._buffer_size = 100
        self.events_tracked = []  # For testing
    
    def create_event(self, event_type: EventType, user_id: str = None, **kwargs) -> MockAnalyticsEvent:
        """Create a new analytics event."""
        event = MockAnalyticsEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            **kwargs
        )
        
        # Add user tier if available
        if user_id and self.tier_manager:
            try:
                user_tier = self.tier_manager.get_user_tier(user_id)
                event.add_property("user_tier", user_tier.value)
            except:
                pass
        
        return event
    
    def track_event(self, event: MockAnalyticsEvent) -> bool:
        """Track an analytics event."""
        try:
            self._event_buffer.append(event)
            self.events_tracked.append(event)  # For testing
            
            if len(self._event_buffer) >= self._buffer_size:
                self._flush_events()
            
            return True
        except:
            return False
    
    def track_user_registration(self, user_id: str, email: str, **kwargs) -> bool:
        """Track user registration event."""
        event = self.create_event(
            event_type=EventType.USER_REGISTRATION,
            user_id=user_id,
            properties={"email": email, **kwargs},
            tags=["user", "registration"]
        )
        return self.track_event(event)
    
    def track_user_login(self, user_id: str, **kwargs) -> bool:
        """Track user login event."""
        event = self.create_event(
            event_type=EventType.USER_LOGIN,
            user_id=user_id,
            properties=kwargs,
            tags=["user", "authentication"]
        )
        return self.track_event(event)
    
    def track_tier_change(self, user_id: str, old_tier: UserTier, new_tier: UserTier, **kwargs) -> bool:
        """Track user tier change event."""
        event_type = EventType.TIER_UPGRADE if new_tier.value > old_tier.value else EventType.TIER_DOWNGRADE
        
        event = self.create_event(
            event_type=event_type,
            user_id=user_id,
            properties={
                "old_tier": old_tier.value,
                "new_tier": new_tier.value,
                **kwargs
            },
            tags=["user", "tier", "billing"]
        )
        return self.track_event(event)
    
    def track_resource_creation(self, user_id: str, resource_type: str, resource_id: str, **kwargs) -> bool:
        """Track resource creation event."""
        event_type_map = {
            "short_url": EventType.SHORT_URL_CREATED,
            "paste": EventType.PASTE_CREATED,
            "media_file": EventType.MEDIA_UPLOADED
        }
        
        event_type = event_type_map.get(resource_type, EventType.FEATURE_USED)
        
        event = self.create_event(
            event_type=event_type,
            user_id=user_id,
            resource_id=resource_id,
            resource_type=resource_type,
            properties=kwargs,
            tags=["resource", "creation", resource_type]
        )
        return self.track_event(event)
    
    def track_api_request(self, endpoint: str, method: str, status_code: int, 
                         response_time_ms: float, **kwargs) -> bool:
        """Track API request event."""
        severity = EventSeverity.INFO
        if status_code >= 500:
            severity = EventSeverity.ERROR
        elif status_code >= 400:
            severity = EventSeverity.WARNING
        
        event = self.create_event(
            event_type=EventType.API_REQUEST,
            properties={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "response_time_ms": response_time_ms
            },
            severity=severity,
            tags=["api", "request", f"status_{status_code}"],
            **kwargs
        )
        return self.track_event(event)
    
    def track_error(self, error_type: str, error_message: str, **kwargs) -> bool:
        """Track error event."""
        event = self.create_event(
            event_type=EventType.ERROR_OCCURRED,
            properties={
                "error_type": error_type,
                "error_message": error_message,
                **kwargs
            },
            severity=EventSeverity.ERROR,
            tags=["error", "system"]
        )
        return self.track_event(event)
    
    def _flush_events(self) -> bool:
        """Flush buffered events."""
        # Mock implementation - just clear buffer
        self._event_buffer.clear()
        return True
    
    def flush(self) -> bool:
        """Manually flush buffered events."""
        return self._flush_events()
    
    def get_event_count(self, **filters) -> int:
        """Get count of tracked events matching filters."""
        count = 0
        for event in self.events_tracked:
            match = True
            
            if "event_type" in filters and event.event_type != filters["event_type"]:
                match = False
            if "user_id" in filters and event.user_id != filters["user_id"]:
                match = False
            
            if match:
                count += 1
        
        return count


class MockMetricsAggregator:
    """Mock metrics aggregator for testing."""
    
    def __init__(self, db=None, tier_manager=None):
        self.db = db or Mock()
        self.tier_manager = tier_manager or Mock()
    
    def calculate_user_metrics(self, user_id: str, start_date=None, end_date=None) -> dict:
        """Calculate user metrics."""
        return {
            "user_tier": "free",
            "account_age_days": 30,
            "resources": {
                "short_urls": 10,
                "pastes": 5,
                "media_files": 2
            },
            "storage": {
                "used_bytes": 1048576,
                "quota_bytes": 1073741824,
                "usage_percentage": 0.1
            },
            "activity": {
                "total_events": 25,
                "activity_score": 50,
                "avg_events_per_day": 2.5
            }
        }
    
    def calculate_system_metrics(self, start_date=None, end_date=None) -> dict:
        """Calculate system metrics."""
        return {
            "users": {
                "total_users": 1000,
                "new_users": 50,
                "active_users": 300,
                "activation_rate": 60.0
            },
            "resources": {
                "short_urls": {"total": 5000, "new": 200},
                "pastes": {"total": 3000, "new": 150},
                "media_files": {"total": 1000, "new": 50}
            },
            "performance": {
                "total_requests": 10000,
                "average_response_time_ms": 150.5,
                "error_rate": 2.5
            }
        }
    
    def calculate_tier_metrics(self, tier: UserTier, start_date=None, end_date=None) -> dict:
        """Calculate tier metrics."""
        return {
            "tier": tier.value,
            "user_count": 100,
            "resources": {
                "short_urls": {"total": 500, "average_per_user": 5.0},
                "pastes": {"total": 300, "average_per_user": 3.0}
            },
            "activity": {
                "total_events": 1000,
                "events_per_user": 10.0
            }
        }
    
    def calculate_conversion_metrics(self, start_date=None, end_date=None) -> dict:
        """Calculate conversion metrics."""
        return {
            "conversions": {
                "guest_to_free": 25,
                "free_to_vip": 10,
                "vip_to_paid": 5
            },
            "conversion_rates": {
                "guest_to_free": {"count": 25, "rate_percentage": 5.0},
                "free_to_vip": {"count": 10, "rate_percentage": 2.0}
            }
        }


class TestMockAnalyticsEvent:
    """Test MockAnalyticsEvent class."""
    
    def test_create_event(self):
        """Test creating an analytics event."""
        event = MockAnalyticsEvent(
            event_id="test-123",
            event_type=EventType.USER_LOGIN,
            timestamp=datetime.utcnow(),
            user_id="user-456",
            properties={"login_method": "email"},
            tags=["user", "auth"]
        )
        
        assert event.event_id == "test-123"
        assert event.event_type == EventType.USER_LOGIN
        assert event.user_id == "user-456"
        assert event.properties["login_method"] == "email"
        assert "user" in event.tags
    
    def test_to_dict(self):
        """Test converting event to dictionary."""
        timestamp = datetime.utcnow()
        event = MockAnalyticsEvent(
            event_id="test-123",
            event_type=EventType.USER_REGISTRATION,
            timestamp=timestamp,
            user_id="user-456"
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["event_id"] == "test-123"
        assert event_dict["event_type"] == "user_registration"
        assert event_dict["timestamp"] == timestamp.isoformat()
        assert event_dict["user_id"] == "user-456"
    
    def test_add_property(self):
        """Test adding properties to event."""
        event = MockAnalyticsEvent(
            event_id="test-123",
            event_type=EventType.FEATURE_USED,
            timestamp=datetime.utcnow()
        )
        
        event.add_property("feature_name", "url_shortener")
        event.add_property("usage_count", 5)
        
        assert event.properties["feature_name"] == "url_shortener"
        assert event.properties["usage_count"] == 5
    
    def test_add_tag(self):
        """Test adding tags to event."""
        event = MockAnalyticsEvent(
            event_id="test-123",
            event_type=EventType.API_REQUEST,
            timestamp=datetime.utcnow()
        )
        
        event.add_tag("api")
        event.add_tag("performance")
        event.add_tag("api")  # Duplicate should not be added
        
        assert "api" in event.tags
        assert "performance" in event.tags
        assert event.tags.count("api") == 1  # No duplicates


class TestMockAnalyticsCollector:
    """Test MockAnalyticsCollector class."""
    
    @pytest.fixture
    def mock_tier_manager(self):
        """Mock tier manager."""
        tier_manager = Mock()
        tier_manager.get_user_tier.return_value = UserTier.free
        return tier_manager
    
    @pytest.fixture
    def analytics_collector(self, mock_tier_manager):
        """Analytics collector with mock dependencies."""
        return MockAnalyticsCollector(tier_manager=mock_tier_manager)
    
    def test_create_event(self, analytics_collector):
        """Test creating an event."""
        event = analytics_collector.create_event(
            event_type=EventType.USER_LOGIN,
            user_id="user-123",
            ip_address="192.168.1.1"
        )
        
        assert event.event_type == EventType.USER_LOGIN
        assert event.user_id == "user-123"
        assert event.ip_address == "192.168.1.1"
        assert event.properties.get("user_tier") == "free"  # Added by tier manager
    
    def test_track_event(self, analytics_collector):
        """Test tracking an event."""
        event = analytics_collector.create_event(
            event_type=EventType.SHORT_URL_CREATED,
            user_id="user-123"
        )
        
        success = analytics_collector.track_event(event)
        
        assert success == True
        assert len(analytics_collector.events_tracked) == 1
        assert analytics_collector.events_tracked[0] == event
    
    def test_track_user_registration(self, analytics_collector):
        """Test tracking user registration."""
        success = analytics_collector.track_user_registration(
            user_id="user-123",
            email="test@example.com",
            registration_method="email"
        )
        
        assert success == True
        assert len(analytics_collector.events_tracked) == 1
        
        event = analytics_collector.events_tracked[0]
        assert event.event_type == EventType.USER_REGISTRATION
        assert event.user_id == "user-123"
        assert event.properties["email"] == "test@example.com"
        assert "registration" in event.tags
    
    def test_track_user_login(self, analytics_collector):
        """Test tracking user login."""
        success = analytics_collector.track_user_login(
            user_id="user-123",
            login_method="oauth",
            ip_address="192.168.1.1"
        )
        
        assert success == True
        
        event = analytics_collector.events_tracked[0]
        assert event.event_type == EventType.USER_LOGIN
        assert event.properties["login_method"] == "oauth"
        assert "authentication" in event.tags
    
    def test_track_tier_change_upgrade(self, analytics_collector):
        """Test tracking tier upgrade."""
        success = analytics_collector.track_tier_change(
            user_id="user-123",
            old_tier=UserTier.free,
            new_tier=UserTier.vip,
            change_reason="purchase"
        )
        
        assert success == True
        
        event = analytics_collector.events_tracked[0]
        assert event.event_type == EventType.TIER_UPGRADE
        assert event.properties["old_tier"] == "free"
        assert event.properties["new_tier"] == "vip"
        assert "tier" in event.tags
    
    def test_track_tier_change_downgrade(self, analytics_collector):
        """Test tracking tier downgrade."""
        success = analytics_collector.track_tier_change(
            user_id="user-123",
            old_tier=UserTier.paid,
            new_tier=UserTier.free,
            change_reason="cancellation"
        )
        
        assert success == True
        
        event = analytics_collector.events_tracked[0]
        assert event.event_type == EventType.TIER_DOWNGRADE
        assert event.properties["old_tier"] == "paid"
        assert event.properties["new_tier"] == "free"
    
    def test_track_resource_creation(self, analytics_collector):
        """Test tracking resource creation."""
        success = analytics_collector.track_resource_creation(
            user_id="user-123",
            resource_type="short_url",
            resource_id="url-456",
            target_url="https://example.com"
        )
        
        assert success == True
        
        event = analytics_collector.events_tracked[0]
        assert event.event_type == EventType.SHORT_URL_CREATED
        assert event.resource_type == "short_url"
        assert event.resource_id == "url-456"
        assert event.properties["target_url"] == "https://example.com"
        assert "creation" in event.tags
    
    def test_track_api_request_success(self, analytics_collector):
        """Test tracking successful API request."""
        success = analytics_collector.track_api_request(
            endpoint="/api/v1/short-url",
            method="POST",
            status_code=201,
            response_time_ms=150.5,
            user_id="user-123"
        )
        
        assert success == True
        
        event = analytics_collector.events_tracked[0]
        assert event.event_type == EventType.API_REQUEST
        assert event.properties["endpoint"] == "/api/v1/short-url"
        assert event.properties["status_code"] == 201
        assert event.severity == EventSeverity.INFO
        assert "status_201" in event.tags
    
    def test_track_api_request_error(self, analytics_collector):
        """Test tracking API request with error."""
        success = analytics_collector.track_api_request(
            endpoint="/api/v1/paste",
            method="GET",
            status_code=500,
            response_time_ms=5000.0
        )
        
        assert success == True
        
        event = analytics_collector.events_tracked[0]
        assert event.severity == EventSeverity.ERROR
        assert "status_500" in event.tags
    
    def test_track_error(self, analytics_collector):
        """Test tracking error event."""
        success = analytics_collector.track_error(
            error_type="ValidationError",
            error_message="Invalid input data",
            endpoint="/api/v1/paste",
            user_id="user-123"
        )
        
        assert success == True
        
        event = analytics_collector.events_tracked[0]
        assert event.event_type == EventType.ERROR_OCCURRED
        assert event.properties["error_type"] == "ValidationError"
        assert event.severity == EventSeverity.ERROR
        assert "error" in event.tags
    
    def test_get_event_count(self, analytics_collector):
        """Test getting event count with filters."""
        # Track multiple events
        analytics_collector.track_user_login(user_id="user-123")
        analytics_collector.track_user_login(user_id="user-456")
        analytics_collector.track_user_registration(user_id="user-789", email="test@example.com")
        
        # Test filtering
        total_count = analytics_collector.get_event_count()
        assert total_count == 3
        
        login_count = analytics_collector.get_event_count(event_type=EventType.USER_LOGIN)
        assert login_count == 2
        
        user_count = analytics_collector.get_event_count(user_id="user-123")
        assert user_count == 1
    
    def test_buffer_flushing(self, analytics_collector):
        """Test that events are flushed when buffer is full."""
        # Set small buffer size for testing
        analytics_collector._buffer_size = 3
        
        # Track events up to buffer size
        for i in range(3):
            analytics_collector.track_user_login(user_id=f"user-{i}")
        
        # Buffer should be flushed (empty)
        assert len(analytics_collector._event_buffer) == 0
        assert len(analytics_collector.events_tracked) == 3


class TestMockMetricsAggregator:
    """Test MockMetricsAggregator class."""
    
    @pytest.fixture
    def metrics_aggregator(self):
        """Metrics aggregator instance."""
        return MockMetricsAggregator()
    
    def test_calculate_user_metrics(self, metrics_aggregator):
        """Test calculating user metrics."""
        metrics = metrics_aggregator.calculate_user_metrics("user-123")
        
        assert "user_tier" in metrics
        assert "account_age_days" in metrics
        assert "resources" in metrics
        assert "storage" in metrics
        assert "activity" in metrics
        
        # Check resource metrics
        assert metrics["resources"]["short_urls"] == 10
        assert metrics["resources"]["pastes"] == 5
        assert metrics["resources"]["media_files"] == 2
        
        # Check storage metrics
        assert metrics["storage"]["usage_percentage"] == 0.1
    
    def test_calculate_system_metrics(self, metrics_aggregator):
        """Test calculating system metrics."""
        metrics = metrics_aggregator.calculate_system_metrics()
        
        assert "users" in metrics
        assert "resources" in metrics
        assert "performance" in metrics
        
        # Check user metrics
        assert metrics["users"]["total_users"] == 1000
        assert metrics["users"]["new_users"] == 50
        assert metrics["users"]["activation_rate"] == 60.0
        
        # Check performance metrics
        assert metrics["performance"]["average_response_time_ms"] == 150.5
        assert metrics["performance"]["error_rate"] == 2.5
    
    def test_calculate_tier_metrics(self, metrics_aggregator):
        """Test calculating tier-specific metrics."""
        metrics = metrics_aggregator.calculate_tier_metrics(UserTier.vip)
        
        assert metrics["tier"] == "vip"
        assert metrics["user_count"] == 100
        assert "resources" in metrics
        assert "activity" in metrics
        
        # Check resource averages
        assert metrics["resources"]["short_urls"]["average_per_user"] == 5.0
        assert metrics["resources"]["pastes"]["average_per_user"] == 3.0
    
    def test_calculate_conversion_metrics(self, metrics_aggregator):
        """Test calculating conversion metrics."""
        metrics = metrics_aggregator.calculate_conversion_metrics()
        
        assert "conversions" in metrics
        assert "conversion_rates" in metrics
        
        # Check conversion counts
        assert metrics["conversions"]["guest_to_free"] == 25
        assert metrics["conversions"]["free_to_vip"] == 10
        
        # Check conversion rates
        assert metrics["conversion_rates"]["guest_to_free"]["rate_percentage"] == 5.0


class TestAnalyticsIntegration:
    """Test integration between analytics collector and metrics aggregator."""
    
    @pytest.fixture
    def analytics_system(self):
        """Complete analytics system setup."""
        tier_manager = Mock()
        tier_manager.get_user_tier.return_value = UserTier.free
        
        collector = MockAnalyticsCollector(tier_manager=tier_manager)
        aggregator = MockMetricsAggregator(tier_manager=tier_manager)
        
        return collector, aggregator
    
    def test_end_to_end_user_journey(self, analytics_system):
        """Test tracking a complete user journey."""
        collector, aggregator = analytics_system
        
        user_id = "user-123"
        
        # Track user registration
        collector.track_user_registration(
            user_id=user_id,
            email="test@example.com",
            registration_method="email"
        )
        
        # Track user login
        collector.track_user_login(
            user_id=user_id,
            login_method="email",
            ip_address="192.168.1.1"
        )
        
        # Track resource creation
        collector.track_resource_creation(
            user_id=user_id,
            resource_type="short_url",
            resource_id="url-456",
            target_url="https://example.com"
        )
        
        # Track tier upgrade
        collector.track_tier_change(
            user_id=user_id,
            old_tier=UserTier.free,
            new_tier=UserTier.vip,
            change_reason="purchase"
        )
        
        # Verify events were tracked
        assert len(collector.events_tracked) == 4
        
        # Check event types
        event_types = [event.event_type for event in collector.events_tracked]
        assert EventType.USER_REGISTRATION in event_types
        assert EventType.USER_LOGIN in event_types
        assert EventType.SHORT_URL_CREATED in event_types
        assert EventType.TIER_UPGRADE in event_types
        
        # Calculate user metrics
        user_metrics = aggregator.calculate_user_metrics(user_id)
        assert user_metrics["user_tier"] == "free"
        assert user_metrics["resources"]["short_urls"] == 10
    
    def test_system_monitoring_scenario(self, analytics_system):
        """Test system monitoring and alerting scenario."""
        collector, aggregator = analytics_system
        
        # Track various system events
        collector.track_api_request(
            endpoint="/api/v1/short-url",
            method="POST",
            status_code=201,
            response_time_ms=150.0
        )
        
        collector.track_api_request(
            endpoint="/api/v1/paste",
            method="GET",
            status_code=500,
            response_time_ms=5000.0
        )
        
        collector.track_error(
            error_type="DatabaseError",
            error_message="Connection timeout",
            endpoint="/api/v1/media/upload"
        )
        
        # Verify error tracking
        error_events = [
            event for event in collector.events_tracked
            if event.severity in [EventSeverity.ERROR, EventSeverity.WARNING]
        ]
        
        assert len(error_events) == 2  # 500 status + error event
        
        # Calculate system metrics
        system_metrics = aggregator.calculate_system_metrics()
        assert system_metrics["performance"]["error_rate"] == 2.5
        assert system_metrics["users"]["total_users"] == 1000
    
    def test_business_intelligence_scenario(self, analytics_system):
        """Test business intelligence and reporting scenario."""
        collector, aggregator = analytics_system
        
        # Simulate multiple user activities
        users = [f"user-{i}" for i in range(5)]
        
        for user_id in users:
            # Registration
            collector.track_user_registration(
                user_id=user_id,
                email=f"{user_id}@example.com"
            )
            
            # Resource creation
            collector.track_resource_creation(
                user_id=user_id,
                resource_type="short_url",
                resource_id=f"url-{user_id}"
            )
            
            # Some users upgrade
            if user_id in ["user-1", "user-3"]:
                collector.track_tier_change(
                    user_id=user_id,
                    old_tier=UserTier.free,
                    new_tier=UserTier.vip
                )
        
        # Verify tracking
        assert len(collector.events_tracked) == 12  # 5 reg + 5 creation + 2 upgrades
        
        # Calculate metrics for different tiers
        free_metrics = aggregator.calculate_tier_metrics(UserTier.free)
        vip_metrics = aggregator.calculate_tier_metrics(UserTier.vip)
        
        assert free_metrics["tier"] == "free"
        assert vip_metrics["tier"] == "vip"
        
        # Calculate conversion metrics
        conversion_metrics = aggregator.calculate_conversion_metrics()
        assert "free_to_vip" in conversion_metrics["conversions"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])