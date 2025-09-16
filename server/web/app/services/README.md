# Tier-Based Permission System

This directory contains the implementation of the tier-based permission and quota management system for the multi-service platform.

## Overview

The tier-based permission system provides:

- **User Tier Management**: Assign and manage user tiers (guest, free, VIP, paid, business)
- **Permission Checking**: Validate feature access based on user tier
- **Quota Enforcement**: Track and enforce usage limits across services
- **Usage Analytics**: Monitor resource consumption and provide insights
- **Upgrade Suggestions**: Recommend tier upgrades based on usage patterns

## Components

### TierManager (`tier_manager.py`)

The core service for managing user tiers and permissions.

**Key Features:**
- Get user's current active tier
- Check permissions for specific features
- Retrieve quota limits and current usage
- Validate quota before resource creation
- Generate tier upgrade suggestions

**Usage Example:**
```python
from .services.tier_manager import TierManager

tier_manager = TierManager(db)

# Check if user can create custom vanity slugs
if tier_manager.has_permission(user_id, "custom_vanity_slugs"):
    # Allow custom slug creation
    pass

# Check quota before creating short URL
allowed, info = tier_manager.check_quota(user_id, "short_urls", 1)
if allowed:
    # Create short URL
    pass
```

### QuotaEnforcer (`quota_enforcer.py`)

Enforces usage quotas and tracks resource consumption.

**Key Features:**
- Enforce quotas for different resource types
- Track resource creation and usage
- Monitor storage usage changes
- Generate usage summaries and analytics
- Clean up expired resources
- Detect approaching quota limits

**Usage Example:**
```python
from .services.quota_enforcer import QuotaEnforcer

quota_enforcer = QuotaEnforcer(db)

# Check storage quota before upload
allowed, info = quota_enforcer.enforce_storage_quota(user_id, file_size_bytes)
if allowed:
    # Proceed with upload
    quota_enforcer.track_storage_usage_change(user_id, file_size_bytes, "upload")
```

### PermissionChecker (`../middleware/permissions.py`)

FastAPI middleware for endpoint protection and permission validation.

**Key Features:**
- JWT token validation and user extraction
- Permission requirement decorators
- Tier requirement decorators
- Quota checking decorators
- FastAPI dependency injection support

**Usage Example:**
```python
from ..middleware.permissions import (
    require_url_shortener_access,
    check_short_url_quota,
    require_vip_tier
)

@router.post("/short-url")
@require_url_shortener_access()
@check_short_url_quota(1)
async def create_short_url(
    request: CreateShortUrlRequest,
    current_user: User = Depends(get_current_user_dep),
    quota_info: dict = None  # Injected by decorator
):
    # Endpoint implementation
    pass
```

## Tier Configuration

### Tier Hierarchy

1. **Guest** - Minimal access, view-only
2. **Free** - Basic features with limits
3. **VIP** - Enhanced features and higher limits
4. **Paid** - Premium features and priority processing
5. **Business** - Unlimited usage and enterprise features

### Default Tier Permissions

| Feature | Guest | Free | VIP | Paid | Business |
|---------|-------|------|-----|------|----------|
| URL Shortener | ❌ | ✅ (100) | ✅ (1000) | ✅ (5000) | ✅ (∞) |
| Custom Vanity Slugs | ❌ | ❌ | ✅ | ✅ | ✅ |
| Pastebin | ❌ | ✅ (200) | ✅ (1000) | ✅ (5000) | ✅ (∞) |
| Private Pastes | ❌ | ❌ | ✅ | ✅ | ✅ |
| Media Upload | ❌ | ✅ (1GB) | ✅ (3GB) | ✅ (5GB) | ✅ (50GB) |
| API Access | ❌ | ❌ | ❌ | ❌ | ✅ |
| Analytics Export | ❌ | ❌ | ❌ | ❌ | ✅ |

### Rate Limits

| Tier | Requests/Hour | Requests/Day |
|------|---------------|--------------|
| Guest | 10 | 50 |
| Free | 50 | 500 |
| VIP | 200 | 2,000 |
| Paid | 500 | 5,000 |
| Business | 2,000 | 20,000 |

## Database Models

The system uses the following database models:

- `UserTierModel`: Tracks user tier assignments and expiration
- `TierConfiguration`: Stores tier-specific configuration
- `UserStorageUsage`: Tracks storage quota usage
- `UserUsageStats`: Daily usage statistics
- `ShortUrl`, `Paste`, `MediaFile`: Resource models with user relationships

## API Integration

### Decorators

**Permission Decorators:**
```python
@require_url_shortener_access()
@require_pastebin_access()
@require_media_upload_access()
@require_custom_vanity_slugs()
@require_private_pastes()
@require_api_access()
```

**Tier Decorators:**
```python
@require_free_tier()
@require_vip_tier()
@require_paid_tier()
@require_business_tier()
```

**Quota Decorators:**
```python
@check_short_url_quota(count=1)
@check_paste_quota(count=1)
@check_storage_quota(gb=1)
```

### Dependencies

**FastAPI Dependencies:**
```python
current_user: User = Depends(get_current_user_dep)
tier_manager: TierManager = Depends(get_tier_manager_dep)
db: Session = Depends(get_db)
```

## Error Handling

The system provides structured error responses:

### Permission Denied (403)
```json
{
    "error": "Permission denied",
    "message": "Custom vanity slugs not available for your tier",
    "current_tier": "free",
    "required_tier": "vip"
}
```

### Quota Exceeded (429)
```json
{
    "error": "Quota exceeded",
    "message": "Would exceed short_urls quota limit",
    "quota_info": {
        "limit": 100,
        "current_usage": 95,
        "remaining": 5
    }
}
```

## Usage Analytics

### Usage Summary
```python
summary = quota_enforcer.get_usage_summary(user_id, days=30)
# Returns:
# {
#     "period_days": 30,
#     "current_tier": "vip",
#     "quotas": {...},
#     "usage_stats": {...}
# }
```

### Approaching Limits
```python
warnings = quota_enforcer.check_approaching_limits(user_id, threshold_percent=80.0)
# Returns list of warnings for quotas above 80% usage
```

### Cleanup Expired Resources
```python
results = quota_enforcer.cleanup_expired_resources(user_id)
# Returns:
# {
#     "expired_short_urls": 5,
#     "expired_pastes": 3,
#     "storage_freed_bytes": 1048576
# }
```

## Testing

The system includes comprehensive unit tests:

- `tests/test_tier_system_unit.py`: Standalone unit tests
- `tests/test_tier_permissions.py`: Integration tests (requires database setup)

Run tests:
```bash
python -m pytest tests/test_tier_system_unit.py -v
```

## Configuration

Tier configurations can be managed through:

1. **Database**: `TierConfiguration` table for dynamic configuration
2. **Code**: `TierPermissions.TIER_CONFIGS` for default fallback values
3. **Admin Interface**: Future admin panel for configuration management

## Security Considerations

- JWT token validation for user authentication
- Permission checks at multiple layers (middleware + service)
- Quota enforcement prevents resource abuse
- Rate limiting prevents API abuse
- Audit logging for tier changes and usage patterns

## Performance Optimization

- Database indexes on frequently queried fields
- Caching of tier configurations
- Efficient quota calculation queries
- Background cleanup of expired resources
- Usage statistics aggregation

## Rate Limiting Infrastructure

### RateLimiter (`rate_limiter.py`)

Redis-based sliding window rate limiter with tier-based configurations.

**Key Features:**
- Sliding window algorithm for accurate rate limiting
- Redis-based storage with memory fallback
- Per-user, per-IP, and per-endpoint rate limiting
- Tier-based rate limit configurations
- Burst traffic handling
- Rate limit statistics and monitoring

**Usage Example:**
```python
from .services.rate_limiter import TierBasedRateLimiter

rate_limiter = TierBasedRateLimiter(redis_client, tier_manager)

# Check user rate limit
result = rate_limiter.check_user_rate_limit(user_id)
if result.allowed:
    # Process request
    pass
else:
    # Return rate limit error
    return {"error": "Rate limit exceeded", "retry_after": result.retry_after}
```

### Rate Limiting Middleware (`../middleware/rate_limiting.py`)

FastAPI middleware for automatic rate limiting enforcement.

**Key Features:**
- Decorator-based rate limiting
- Automatic rate limit headers
- Tier-based bypass options
- IP and endpoint-specific limiting
- FastAPI dependency integration

**Usage Example:**
```python
from ..middleware.rate_limiting import rate_limit_user, rate_limit_strict

@router.post("/create-resource")
@rate_limit_user()
async def create_resource(
    request: Request,
    current_user: User = Depends(get_current_user_dep)
):
    # Endpoint implementation
    pass
```

### Rate Limit Configurations

| Tier | Requests/Hour | Requests/Day | Burst Limit |
|------|---------------|--------------|-------------|
| Guest | 10 | 50 | 5 |
| Free | 50 | 500 | 20 |
| VIP | 200 | 2,000 | 50 |
| Paid | 500 | 5,000 | 100 |
| Business | 2,000 | 20,000 | 500 |

## Analytics Collection System

### AnalyticsCollector (`analytics_collector.py`)

Comprehensive analytics event tracking and collection system.

**Key Features:**
- Event-driven analytics tracking
- User journey mapping
- Resource usage monitoring
- Error and performance tracking
- Buffered event processing
- Tier-aware event enrichment

**Usage Example:**
```python
from .services.analytics_collector import AnalyticsCollector, EventType

analytics = AnalyticsCollector(db, tier_manager)

# Track user registration
analytics.track_user_registration(
    user_id="user-123",
    email="user@example.com",
    registration_method="email"
)

# Track resource creation
analytics.track_resource_creation(
    user_id="user-123",
    resource_type="short_url",
    resource_id="url-456",
    properties={"target_url": "https://example.com"}
)
```

### MetricsAggregator (`metrics_aggregator.py`)

Advanced metrics calculation and business intelligence system.

**Key Features:**
- User-specific metrics calculation
- System-wide performance metrics
- Tier-based analytics
- Conversion rate tracking
- Time series data generation
- Business intelligence reporting

**Usage Example:**
```python
from .services.metrics_aggregator import MetricsAggregator

aggregator = MetricsAggregator(db, tier_manager)

# Calculate user metrics
user_metrics = aggregator.calculate_user_metrics("user-123")

# Generate system metrics
system_metrics = aggregator.calculate_system_metrics()

# Calculate conversion rates
conversions = aggregator.calculate_conversion_metrics()
```

### Analytics Event Types

| Event Type | Description | Use Case |
|------------|-------------|----------|
| USER_REGISTRATION | User account creation | User acquisition tracking |
| USER_LOGIN | User authentication | Engagement monitoring |
| TIER_UPGRADE | Tier subscription change | Revenue optimization |
| SHORT_URL_CREATED | URL shortener usage | Feature adoption |
| PASTE_CREATED | Pastebin usage | Feature adoption |
| MEDIA_UPLOADED | Media service usage | Storage analytics |
| API_REQUEST | API endpoint access | Performance monitoring |
| RATE_LIMIT_HIT | Rate limit exceeded | Abuse detection |
| QUOTA_EXCEEDED | Usage quota exceeded | Upgrade opportunities |
| ERROR_OCCURRED | System errors | Reliability monitoring |

### Metrics Categories

**User Metrics:**
- Account age and tier information
- Resource creation counts
- Storage usage and quotas
- Activity scores and engagement
- Feature usage patterns

**System Metrics:**
- Total and active user counts
- Resource creation rates
- API performance statistics
- Error rates and reliability
- Growth and conversion rates

**Tier Metrics:**
- User distribution across tiers
- Tier-specific usage patterns
- Conversion rates between tiers
- Revenue optimization insights

### Endpoint-Specific Limits

| Endpoint | Requests/Hour | Requests/Day |
|----------|---------------|--------------|
| Short URL Creation | 20 | 200 |
| Paste Creation | 30 | 300 |
| Media Upload | 10 | 50 |
| Default API | 50 | 500 |

## Future Enhancements

- Real-time quota monitoring dashboard
- Automated tier upgrade recommendations
- Usage-based pricing calculations
- Team and organization tier management
- Advanced analytics and reporting
- Integration with payment systems
- Distributed rate limiting across multiple servers
- Machine learning-based abuse detection
- Dynamic rate limit adjustment based on system load