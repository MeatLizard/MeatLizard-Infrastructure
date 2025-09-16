"""
Standalone unit tests for rate limiting infrastructure.
Tests core rate limiting logic without database dependencies.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4
import enum


class UserTier(str, enum.Enum):
    """User tier enumeration for testing."""
    guest = "guest"
    free = "free"
    vip = "vip"
    paid = "paid"
    business = "business"


class RateLimitType(str, enum.Enum):
    """Types of rate limiting."""
    PER_USER = "per_user"
    PER_IP = "per_ip"
    PER_ENDPOINT = "per_endpoint"
    GLOBAL = "global"


class RateLimitConfig:
    """Rate limit configuration."""
    
    def __init__(self, requests_per_hour: int, requests_per_day: int, 
                 burst_limit: int = None, window_size_seconds: int = 3600):
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        self.burst_limit = burst_limit
        self.window_size_seconds = window_size_seconds


class RateLimitResult:
    """Result of rate limit check."""
    
    def __init__(self, allowed: bool, remaining: int, reset_time: datetime,
                 retry_after: int = None, limit_type: str = "", current_usage: int = 0):
        self.allowed = allowed
        self.remaining = remaining
        self.reset_time = reset_time
        self.retry_after = retry_after
        self.limit_type = limit_type
        self.current_usage = current_usage


class MockSlidingWindowRateLimiter:
    """Mock sliding window rate limiter for testing."""
    
    def __init__(self):
        self._memory_store = {}
    
    def _get_key(self, identifier: str, limit_type: RateLimitType, window: str = "hour") -> str:
        """Generate key for rate limit tracking."""
        return f"rate_limit:{limit_type.value}:{identifier}:{window}"
    
    def _sliding_window_check(self, key: str, limit: int, window_seconds: int, 
                            current_time: float = None) -> tuple:
        """Perform sliding window rate limit check."""
        if current_time is None:
            current_time = time.time()
        
        window_start = current_time - window_seconds
        
        # Initialize if not exists
        if key not in self._memory_store:
            self._memory_store[key] = []
        
        # Clean expired entries
        self._memory_store[key] = [
            req_time for req_time in self._memory_store[key]
            if req_time > window_start
        ]
        
        current_count = len(self._memory_store[key])
        
        if current_count < limit:
            self._memory_store[key].append(current_time)
            remaining = limit - current_count - 1
            reset_time = current_time + window_seconds
            return True, remaining, reset_time
        else:
            # Calculate reset time from oldest request
            if self._memory_store[key]:
                oldest_time = min(self._memory_store[key])
                reset_time = oldest_time + window_seconds
            else:
                reset_time = current_time + window_seconds
            
            return False, 0, reset_time
    
    def check_rate_limit(self, identifier: str, limit_type: RateLimitType, 
                        config: RateLimitConfig, current_time: float = None) -> RateLimitResult:
        """Check if request is within rate limits."""
        if current_time is None:
            current_time = time.time()
        
        # Check hourly limit first
        hour_key = self._get_key(identifier, limit_type, "hour")
        hour_allowed, hour_remaining, hour_reset = self._sliding_window_check(
            hour_key, config.requests_per_hour, 3600, current_time
        )
        
        if not hour_allowed:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=datetime.fromtimestamp(hour_reset),
                retry_after=int(hour_reset - current_time),
                limit_type=f"{limit_type.value}_hourly",
                current_usage=config.requests_per_hour
            )
        
        # Check daily limit
        day_key = self._get_key(identifier, limit_type, "day")
        day_allowed, day_remaining, day_reset = self._sliding_window_check(
            day_key, config.requests_per_day, 86400, current_time
        )
        
        if not day_allowed:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=datetime.fromtimestamp(day_reset),
                retry_after=int(day_reset - current_time),
                limit_type=f"{limit_type.value}_daily",
                current_usage=config.requests_per_day
            )
        
        # Both limits passed
        remaining = min(hour_remaining, day_remaining)
        reset_time = datetime.fromtimestamp(min(hour_reset, day_reset))
        
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=reset_time,
            limit_type=limit_type.value,
            current_usage=config.requests_per_hour - hour_remaining - 1
        )
    
    def reset_limits(self, identifier: str, limit_type: RateLimitType) -> bool:
        """Reset rate limits for an identifier."""
        hour_key = self._get_key(identifier, limit_type, "hour")
        day_key = self._get_key(identifier, limit_type, "day")
        
        self._memory_store.pop(hour_key, None)
        self._memory_store.pop(day_key, None)
        
        return True


class MockTierBasedRateLimiter:
    """Mock tier-based rate limiter for testing."""
    
    TIER_RATE_LIMITS = {
        UserTier.guest: RateLimitConfig(
            requests_per_hour=10,
            requests_per_day=50,
            burst_limit=5
        ),
        UserTier.free: RateLimitConfig(
            requests_per_hour=50,
            requests_per_day=500,
            burst_limit=20
        ),
        UserTier.vip: RateLimitConfig(
            requests_per_hour=200,
            requests_per_day=2000,
            burst_limit=50
        ),
        UserTier.paid: RateLimitConfig(
            requests_per_hour=500,
            requests_per_day=5000,
            burst_limit=100
        ),
        UserTier.business: RateLimitConfig(
            requests_per_hour=2000,
            requests_per_day=20000,
            burst_limit=500
        )
    }
    
    def __init__(self, tier_manager=None):
        self.limiter = MockSlidingWindowRateLimiter()
        self.tier_manager = tier_manager
    
    def check_user_rate_limit(self, user_id: str = None, endpoint: str = None, 
                            current_time: float = None) -> RateLimitResult:
        """Check rate limit for a user based on their tier."""
        # Determine user tier
        if user_id and self.tier_manager:
            user_tier = self.tier_manager.get_user_tier(user_id)
        else:
            user_tier = UserTier.guest
        
        # Get rate limit config for tier
        config = self.TIER_RATE_LIMITS.get(user_tier, self.TIER_RATE_LIMITS[UserTier.guest])
        
        # Use user_id or generate guest identifier
        identifier = user_id or f"guest_{int(current_time or time.time()) // 3600}"
        
        return self.limiter.check_rate_limit(
            identifier=identifier,
            limit_type=RateLimitType.PER_USER,
            config=config,
            current_time=current_time
        )
    
    def check_ip_rate_limit(self, ip_address: str, current_time: float = None) -> RateLimitResult:
        """Check rate limit for an IP address."""
        config = RateLimitConfig(
            requests_per_hour=100,
            requests_per_day=1000,
            burst_limit=30
        )
        
        return self.limiter.check_rate_limit(
            identifier=ip_address,
            limit_type=RateLimitType.PER_IP,
            config=config,
            current_time=current_time
        )
    
    def check_endpoint_rate_limit(self, endpoint: str, user_id: str = None, 
                                current_time: float = None) -> RateLimitResult:
        """Check rate limit for a specific endpoint."""
        endpoint_configs = {
            "/api/v1/short-url": RateLimitConfig(
                requests_per_hour=20,
                requests_per_day=200
            ),
            "/api/v1/paste": RateLimitConfig(
                requests_per_hour=30,
                requests_per_day=300
            ),
            "/api/v1/media/upload": RateLimitConfig(
                requests_per_hour=10,
                requests_per_day=50
            )
        }
        
        config = endpoint_configs.get(endpoint, RateLimitConfig(
            requests_per_hour=50,
            requests_per_day=500
        ))
        
        identifier = f"{endpoint}:{user_id or 'anonymous'}"
        
        return self.limiter.check_rate_limit(
            identifier=identifier,
            limit_type=RateLimitType.PER_ENDPOINT,
            config=config,
            current_time=current_time
        )
    
    def get_tier_config(self, tier: UserTier) -> RateLimitConfig:
        """Get rate limit configuration for a tier."""
        return self.TIER_RATE_LIMITS.get(tier, self.TIER_RATE_LIMITS[UserTier.guest])
    
    def reset_user_limits(self, user_id: str) -> bool:
        """Reset rate limits for a user."""
        return self.limiter.reset_limits(user_id, RateLimitType.PER_USER)


class TestRateLimitConfig:
    """Test RateLimitConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig(requests_per_hour=100, requests_per_day=1000)
        
        assert config.requests_per_hour == 100
        assert config.requests_per_day == 1000
        assert config.burst_limit is None
        assert config.window_size_seconds == 3600
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests_per_hour=50,
            requests_per_day=500,
            burst_limit=20,
            window_size_seconds=1800
        )
        
        assert config.requests_per_hour == 50
        assert config.requests_per_day == 500
        assert config.burst_limit == 20
        assert config.window_size_seconds == 1800


class TestRateLimitResult:
    """Test RateLimitResult class."""
    
    def test_allowed_result(self):
        """Test allowed rate limit result."""
        reset_time = datetime.now() + timedelta(hours=1)
        result = RateLimitResult(
            allowed=True,
            remaining=50,
            reset_time=reset_time,
            limit_type="per_user",
            current_usage=10
        )
        
        assert result.allowed == True
        assert result.remaining == 50
        assert result.reset_time == reset_time
        assert result.retry_after is None
        assert result.limit_type == "per_user"
        assert result.current_usage == 10
    
    def test_denied_result(self):
        """Test denied rate limit result."""
        reset_time = datetime.now() + timedelta(hours=1)
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            reset_time=reset_time,
            retry_after=3600,
            limit_type="per_user",
            current_usage=100
        )
        
        assert result.allowed == False
        assert result.remaining == 0
        assert result.retry_after == 3600


class TestMockSlidingWindowRateLimiter:
    """Test MockSlidingWindowRateLimiter class."""
    
    @pytest.fixture
    def rate_limiter(self):
        """MockSlidingWindowRateLimiter instance."""
        return MockSlidingWindowRateLimiter()
    
    def test_sliding_window_within_limit(self, rate_limiter):
        """Test sliding window check within limits."""
        config = RateLimitConfig(requests_per_hour=10, requests_per_day=100)
        current_time = time.time()
        
        result = rate_limiter.check_rate_limit(
            identifier="user123",
            limit_type=RateLimitType.PER_USER,
            config=config,
            current_time=current_time
        )
        
        assert result.allowed == True
        assert result.remaining >= 0
        assert result.reset_time > datetime.fromtimestamp(current_time)
    
    def test_sliding_window_exceeds_limit(self, rate_limiter):
        """Test sliding window check exceeding limits."""
        config = RateLimitConfig(requests_per_hour=2, requests_per_day=10)
        current_time = time.time()
        
        # Make requests up to the limit
        for i in range(2):
            result = rate_limiter.check_rate_limit(
                identifier="user123",
                limit_type=RateLimitType.PER_USER,
                config=config,
                current_time=current_time + i
            )
            assert result.allowed == True
        
        # Next request should be denied
        result = rate_limiter.check_rate_limit(
            identifier="user123",
            limit_type=RateLimitType.PER_USER,
            config=config,
            current_time=current_time + 2
        )
        
        assert result.allowed == False
        assert result.remaining == 0
        assert result.retry_after is not None
    
    def test_sliding_window_expiry(self, rate_limiter):
        """Test that old requests expire from sliding window."""
        config = RateLimitConfig(requests_per_hour=2, requests_per_day=10)
        current_time = time.time()
        
        # Make requests at the limit
        for i in range(2):
            result = rate_limiter.check_rate_limit(
                identifier="user123",
                limit_type=RateLimitType.PER_USER,
                config=config,
                current_time=current_time + i
            )
            assert result.allowed == True
        
        # Request should be denied
        result = rate_limiter.check_rate_limit(
            identifier="user123",
            limit_type=RateLimitType.PER_USER,
            config=config,
            current_time=current_time + 2
        )
        assert result.allowed == False
        
        # After window expires, request should be allowed
        result = rate_limiter.check_rate_limit(
            identifier="user123",
            limit_type=RateLimitType.PER_USER,
            config=config,
            current_time=current_time + 3601  # 1 hour + 1 second
        )
        assert result.allowed == True
    
    def test_daily_vs_hourly_limits(self, rate_limiter):
        """Test interaction between daily and hourly limits."""
        config = RateLimitConfig(requests_per_hour=2, requests_per_day=3)
        current_time = time.time()
        
        # Make 2 requests (hourly limit)
        for i in range(2):
            result = rate_limiter.check_rate_limit(
                identifier="user123",
                limit_type=RateLimitType.PER_USER,
                config=config,
                current_time=current_time + i
            )
            assert result.allowed == True
        
        # 3rd request should be denied due to hourly limit
        result = rate_limiter.check_rate_limit(
            identifier="user123",
            limit_type=RateLimitType.PER_USER,
            config=config,
            current_time=current_time + 2
        )
        assert result.allowed == False
        assert "hourly" in result.limit_type
    
    def test_reset_limits(self, rate_limiter):
        """Test resetting rate limits."""
        config = RateLimitConfig(requests_per_hour=2, requests_per_day=10)
        current_time = time.time()
        
        # Make requests up to limit
        for i in range(2):
            rate_limiter.check_rate_limit(
                identifier="user123",
                limit_type=RateLimitType.PER_USER,
                config=config,
                current_time=current_time + i
            )
        
        # Should be at limit
        result = rate_limiter.check_rate_limit(
            identifier="user123",
            limit_type=RateLimitType.PER_USER,
            config=config,
            current_time=current_time + 2
        )
        assert result.allowed == False
        
        # Reset limits
        success = rate_limiter.reset_limits("user123", RateLimitType.PER_USER)
        assert success == True
        
        # Should be allowed again
        result = rate_limiter.check_rate_limit(
            identifier="user123",
            limit_type=RateLimitType.PER_USER,
            config=config,
            current_time=current_time + 3
        )
        assert result.allowed == True


class TestMockTierBasedRateLimiter:
    """Test MockTierBasedRateLimiter class."""
    
    @pytest.fixture
    def mock_tier_manager(self):
        """Mock TierManager."""
        tier_manager = Mock()
        tier_manager.get_user_tier.return_value = UserTier.free
        return tier_manager
    
    @pytest.fixture
    def tier_rate_limiter(self, mock_tier_manager):
        """MockTierBasedRateLimiter with mock dependencies."""
        return MockTierBasedRateLimiter(tier_manager=mock_tier_manager)
    
    def test_guest_user_rate_limit(self, tier_rate_limiter):
        """Test rate limiting for guest users."""
        result = tier_rate_limiter.check_user_rate_limit(user_id=None)
        
        assert result.allowed == True  # First request should be allowed
        assert result.remaining >= 0
    
    def test_free_user_rate_limit(self, tier_rate_limiter):
        """Test rate limiting for free tier users."""
        user_id = str(uuid4())
        
        result = tier_rate_limiter.check_user_rate_limit(user_id=user_id)
        
        assert result.allowed == True
        assert result.remaining >= 0
    
    def test_tier_hierarchy_limits(self, tier_rate_limiter):
        """Test that higher tiers have higher limits."""
        guest_config = tier_rate_limiter.TIER_RATE_LIMITS[UserTier.guest]
        free_config = tier_rate_limiter.TIER_RATE_LIMITS[UserTier.free]
        vip_config = tier_rate_limiter.TIER_RATE_LIMITS[UserTier.vip]
        paid_config = tier_rate_limiter.TIER_RATE_LIMITS[UserTier.paid]
        business_config = tier_rate_limiter.TIER_RATE_LIMITS[UserTier.business]
        
        # Check hourly limits progression
        assert guest_config.requests_per_hour < free_config.requests_per_hour
        assert free_config.requests_per_hour < vip_config.requests_per_hour
        assert vip_config.requests_per_hour < paid_config.requests_per_hour
        assert paid_config.requests_per_hour < business_config.requests_per_hour
        
        # Check daily limits progression
        assert guest_config.requests_per_day < free_config.requests_per_day
        assert free_config.requests_per_day < vip_config.requests_per_day
        assert vip_config.requests_per_day < paid_config.requests_per_day
        assert paid_config.requests_per_day < business_config.requests_per_day
    
    def test_ip_rate_limit(self, tier_rate_limiter):
        """Test IP-based rate limiting."""
        ip_address = "192.168.1.1"
        
        result = tier_rate_limiter.check_ip_rate_limit(ip_address)
        
        assert result.allowed == True
        assert result.remaining >= 0
        assert result.limit_type == "per_ip"
    
    def test_endpoint_rate_limit(self, tier_rate_limiter):
        """Test endpoint-specific rate limiting."""
        endpoint = "/api/v1/short-url"
        user_id = str(uuid4())
        
        result = tier_rate_limiter.check_endpoint_rate_limit(endpoint, user_id)
        
        assert result.allowed == True
        assert result.remaining >= 0
        assert result.limit_type == "per_endpoint"
    
    def test_different_endpoints_separate_limits(self, tier_rate_limiter):
        """Test that different endpoints have separate rate limits."""
        user_id = str(uuid4())
        
        # Make requests to different endpoints
        result1 = tier_rate_limiter.check_endpoint_rate_limit("/api/v1/short-url", user_id)
        result2 = tier_rate_limiter.check_endpoint_rate_limit("/api/v1/paste", user_id)
        
        assert result1.allowed == True
        assert result2.allowed == True
    
    def test_get_tier_config(self, tier_rate_limiter):
        """Test getting tier configuration."""
        for tier in UserTier:
            config = tier_rate_limiter.get_tier_config(tier)
            
            assert isinstance(config, RateLimitConfig)
            assert config.requests_per_hour > 0
            assert config.requests_per_day > 0
    
    def test_reset_user_limits(self, tier_rate_limiter):
        """Test resetting user rate limits."""
        user_id = str(uuid4())
        
        success = tier_rate_limiter.reset_user_limits(user_id)
        assert success == True


class TestRateLimitScenarios:
    """Test realistic rate limiting scenarios."""
    
    @pytest.fixture
    def tier_rate_limiter(self):
        """MockTierBasedRateLimiter with memory storage."""
        return MockTierBasedRateLimiter(tier_manager=None)
    
    def test_burst_traffic_handling(self, tier_rate_limiter):
        """Test handling of burst traffic."""
        user_id = str(uuid4())
        current_time = time.time()
        
        # Simulate burst of requests
        allowed_count = 0
        denied_count = 0
        
        for i in range(15):  # Try 15 requests quickly (guest limit is 10/hour)
            result = tier_rate_limiter.check_user_rate_limit(
                user_id, current_time=current_time + i * 0.1
            )
            if result.allowed:
                allowed_count += 1
            else:
                denied_count += 1
        
        # Some should be allowed (up to guest limit), some denied
        assert allowed_count == 10  # Guest hourly limit
        assert denied_count == 5   # Remaining requests denied
    
    def test_multiple_users_separate_limits(self, tier_rate_limiter):
        """Test that different users have separate rate limits."""
        user1 = str(uuid4())
        user2 = str(uuid4())
        current_time = time.time()
        
        # Both users should be able to make requests independently
        result1 = tier_rate_limiter.check_user_rate_limit(user1, current_time=current_time)
        result2 = tier_rate_limiter.check_user_rate_limit(user2, current_time=current_time)
        
        assert result1.allowed == True
        assert result2.allowed == True
    
    def test_ip_and_user_limits_independent(self, tier_rate_limiter):
        """Test that IP and user limits are independent."""
        user_id = str(uuid4())
        ip_address = "192.168.1.100"
        current_time = time.time()
        
        # User rate limit check
        user_result = tier_rate_limiter.check_user_rate_limit(user_id, current_time=current_time)
        
        # IP rate limit check
        ip_result = tier_rate_limiter.check_ip_rate_limit(ip_address, current_time=current_time)
        
        # Both should be independent
        assert user_result.allowed == True
        assert ip_result.allowed == True
    
    def test_endpoint_specific_limits(self, tier_rate_limiter):
        """Test endpoint-specific rate limiting."""
        user_id = str(uuid4())
        current_time = time.time()
        
        # Upload endpoint has lower limits (10/hour)
        upload_allowed = 0
        for i in range(15):
            result = tier_rate_limiter.check_endpoint_rate_limit(
                "/api/v1/media/upload", user_id, current_time=current_time + i
            )
            if result.allowed:
                upload_allowed += 1
        
        # Should be limited to 10 requests per hour
        assert upload_allowed == 10
        
        # Short URL endpoint has higher limits (20/hour)
        url_allowed = 0
        for i in range(25):
            result = tier_rate_limiter.check_endpoint_rate_limit(
                "/api/v1/short-url", user_id, current_time=current_time + 100 + i
            )
            if result.allowed:
                url_allowed += 1
        
        # Should be limited to 20 requests per hour
        assert url_allowed == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])