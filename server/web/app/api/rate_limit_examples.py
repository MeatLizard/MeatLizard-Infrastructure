"""
Example API endpoints demonstrating rate limiting middleware usage.
Shows how to integrate rate limiting with tier-based permissions.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..middleware.permissions import get_current_user_dep
from ..middleware.rate_limiting import (
    rate_limit_user,
    rate_limit_ip,
    rate_limit_endpoint,
    rate_limit_strict,
    rate_limit_public,
    rate_limit_upload,
    check_user_rate_limit_dep,
    check_ip_rate_limit_dep,
    get_rate_limiter
)
from ..services.rate_limiter import TierBasedRateLimiter, RateLimitResult
from ..models import UserTier

router = APIRouter(prefix="/api/v1/rate-limit-examples", tags=["rate-limiting"])


@router.get("/basic-user-limit")
@rate_limit_user()
async def basic_user_rate_limit(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """
    Example endpoint with basic user rate limiting.
    
    This endpoint demonstrates:
    - User-based rate limiting with tier-specific limits
    - Automatic rate limit headers in response
    - Graceful handling of rate limit exceeded
    """
    user_id = str(current_user.id) if current_user else "guest"
    
    return {
        "message": "Request successful",
        "user_id": user_id,
        "endpoint": "/basic-user-limit",
        "note": "This endpoint has user-based rate limiting"
    }


@router.get("/strict-rate-limit")
@rate_limit_strict()
async def strict_rate_limit(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """
    Example endpoint with strict rate limiting for sensitive operations.
    
    This endpoint demonstrates:
    - Strict rate limiting for sensitive endpoints
    - Lower rate limits for security-critical operations
    """
    return {
        "message": "Sensitive operation completed",
        "note": "This endpoint has strict rate limiting for security"
    }


@router.get("/public-ip-limit")
@rate_limit_public()
async def public_ip_rate_limit(request: Request):
    """
    Example public endpoint with IP-based rate limiting.
    
    This endpoint demonstrates:
    - IP-based rate limiting for public endpoints
    - No authentication required
    - Protection against IP-based abuse
    """
    client_ip = request.client.host if request.client else "unknown"
    
    return {
        "message": "Public endpoint accessed",
        "client_ip": client_ip,
        "note": "This endpoint uses IP-based rate limiting"
    }


@router.post("/upload-simulation")
@rate_limit_upload()
async def upload_simulation(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """
    Example upload endpoint with specialized rate limiting.
    
    This endpoint demonstrates:
    - Lower rate limits for resource-intensive operations
    - Upload-specific rate limiting configuration
    """
    return {
        "message": "Upload simulation completed",
        "note": "This endpoint has specialized upload rate limiting"
    }


@router.get("/tier-bypass-example")
@rate_limit_user(bypass_for_tiers=[UserTier.business])
async def tier_bypass_example(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    db: Session = Depends(get_db)
):
    """
    Example endpoint that bypasses rate limiting for certain tiers.
    
    This endpoint demonstrates:
    - Tier-based rate limit bypassing
    - Business tier users bypass rate limits
    - Other tiers still subject to rate limiting
    """
    user_tier = "guest"
    if current_user and db:
        from ..services.tier_manager import TierManager
        tier_manager = TierManager(db)
        user_tier = tier_manager.get_user_tier(str(current_user.id)).value
    
    return {
        "message": "Request successful",
        "user_tier": user_tier,
        "note": "Business tier users bypass rate limits on this endpoint"
    }


@router.get("/endpoint-specific-limit")
@rate_limit_endpoint("/api/v1/rate-limit-examples/endpoint-specific-limit", 
                    requests_per_hour=5, requests_per_day=20)
async def endpoint_specific_limit(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep)
):
    """
    Example endpoint with custom endpoint-specific rate limits.
    
    This endpoint demonstrates:
    - Custom rate limits per endpoint
    - Very restrictive limits (5/hour, 20/day)
    - Endpoint-specific configuration
    """
    return {
        "message": "Endpoint-specific rate limit applied",
        "limits": {
            "requests_per_hour": 5,
            "requests_per_day": 20
        },
        "note": "This endpoint has very restrictive custom limits"
    }


@router.get("/rate-limit-info")
async def get_rate_limit_info(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    rate_limiter: TierBasedRateLimiter = Depends(get_rate_limiter)
):
    """
    Get current rate limit information for the user.
    
    This endpoint demonstrates:
    - Checking rate limits without consuming them
    - Providing rate limit information to clients
    - Tier-specific rate limit details
    """
    user_id = str(current_user.id) if current_user else None
    
    # Get user rate limit info (this doesn't consume a request)
    user_result = rate_limiter.check_user_rate_limit(user_id)
    
    # Get IP rate limit info
    client_ip = request.client.host if request.client else "unknown"
    ip_result = rate_limiter.check_ip_rate_limit(client_ip)
    
    # Get tier configuration
    if current_user:
        from ..services.tier_manager import TierManager
        from ..db import get_db
        # Note: In a real implementation, you'd inject the db dependency
        tier_manager = TierManager(next(get_db()))
        user_tier = tier_manager.get_user_tier(user_id)
        tier_config = rate_limiter.get_tier_config(user_tier)
    else:
        user_tier = UserTier.guest
        tier_config = rate_limiter.get_tier_config(UserTier.guest)
    
    return {
        "user_tier": user_tier.value,
        "tier_limits": {
            "requests_per_hour": tier_config.requests_per_hour,
            "requests_per_day": tier_config.requests_per_day,
            "burst_limit": tier_config.burst_limit
        },
        "current_limits": {
            "user": {
                "allowed": user_result.allowed,
                "remaining": user_result.remaining,
                "reset_time": user_result.reset_time.isoformat(),
                "current_usage": user_result.current_usage
            },
            "ip": {
                "allowed": ip_result.allowed,
                "remaining": ip_result.remaining,
                "reset_time": ip_result.reset_time.isoformat(),
                "current_usage": ip_result.current_usage
            }
        }
    }


@router.get("/dependency-based-check")
async def dependency_based_rate_limit_check(
    request: Request,
    user_rate_limit: RateLimitResult = Depends(check_user_rate_limit_dep),
    ip_rate_limit: RateLimitResult = Depends(check_ip_rate_limit_dep),
    current_user: Optional[User] = Depends(get_current_user_dep)
):
    """
    Example using rate limit dependencies instead of decorators.
    
    This endpoint demonstrates:
    - Using FastAPI dependencies for rate limiting
    - Access to rate limit results in endpoint logic
    - Multiple rate limit checks (user + IP)
    """
    return {
        "message": "Request passed all rate limit checks",
        "rate_limit_info": {
            "user_limit": {
                "remaining": user_rate_limit.remaining,
                "reset_time": user_rate_limit.reset_time.isoformat()
            },
            "ip_limit": {
                "remaining": ip_rate_limit.remaining,
                "reset_time": ip_rate_limit.reset_time.isoformat()
            }
        },
        "note": "This endpoint uses dependency-based rate limiting"
    }


@router.post("/reset-user-limits")
async def reset_user_rate_limits(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    rate_limiter: TierBasedRateLimiter = Depends(get_rate_limiter),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to reset rate limits for a user.
    
    This endpoint demonstrates:
    - Administrative rate limit management
    - Resetting rate limits programmatically
    - Useful for customer support scenarios
    
    Note: In production, this would require admin authentication
    """
    if not current_user:
        return {"error": "Authentication required"}
    
    user_id = str(current_user.id)
    
    # Check if user has admin privileges (simplified check)
    from ..services.tier_manager import TierManager
    tier_manager = TierManager(db)
    user_tier = tier_manager.get_user_tier(user_id)
    
    if user_tier != UserTier.business:  # Simplified admin check
        return {"error": "Admin privileges required"}
    
    # Reset rate limits
    success = rate_limiter.reset_user_limits(user_id)
    
    return {
        "message": "Rate limits reset successfully" if success else "Failed to reset rate limits",
        "user_id": user_id,
        "success": success
    }


@router.get("/usage-stats")
async def get_usage_statistics(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_dep),
    rate_limiter: TierBasedRateLimiter = Depends(get_rate_limiter)
):
    """
    Get usage statistics for the current user.
    
    This endpoint demonstrates:
    - Retrieving usage statistics
    - Monitoring rate limit consumption
    - User-facing analytics
    """
    if not current_user:
        return {"error": "Authentication required"}
    
    user_id = str(current_user.id)
    
    # Get usage statistics
    user_stats = rate_limiter.get_user_usage_stats(user_id)
    
    # Get IP statistics
    client_ip = request.client.host if request.client else "unknown"
    ip_stats = rate_limiter.get_ip_usage_stats(client_ip)
    
    return {
        "user_stats": user_stats,
        "ip_stats": ip_stats,
        "note": "Usage statistics for monitoring rate limit consumption"
    }