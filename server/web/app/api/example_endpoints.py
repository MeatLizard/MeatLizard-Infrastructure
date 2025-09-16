"""
Example API endpoints demonstrating tier-based permission system usage.
Shows how to integrate TierManager, PermissionChecker, and QuotaEnforcer.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..db import get_db
from ..models import User
from ..middleware.permissions import (
    get_current_user_dep,
    get_tier_manager_dep,
    require_url_shortener_access,
    require_custom_vanity_slugs,
    check_short_url_quota,
    require_vip_tier
)
from ..services.tier_manager import TierManager
from ..services.quota_enforcer import QuotaEnforcer

router = APIRouter(prefix="/api/v1", tags=["examples"])


class CreateShortUrlRequest(BaseModel):
    """Request model for creating short URLs."""
    target_url: str
    custom_slug: Optional[str] = None
    title: Optional[str] = None
    expires_at: Optional[str] = None


class QuotaInfoResponse(BaseModel):
    """Response model for quota information."""
    user_tier: str
    quotas: Dict[str, Any]
    usage_stats: Dict[str, Any]
    warnings: list


@router.get("/quota-info")
async def get_quota_info(
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    db: Session = Depends(get_db)
) -> QuotaInfoResponse:
    """
    Get quota information for the current user.
    
    This endpoint demonstrates:
    - Getting current user from JWT token
    - Using TierManager to get tier and quota info
    - Using QuotaEnforcer to get usage summary
    """
    user_id = str(current_user.id) if current_user else None
    quota_enforcer = QuotaEnforcer(db)
    
    # Get user tier and configuration
    user_tier = tier_manager.get_user_tier(user_id)
    tier_config = tier_manager.get_tier_config(user_tier)
    
    # Get usage summary
    usage_summary = quota_enforcer.get_usage_summary(user_id, days=30)
    
    # Check for approaching limits
    warnings = quota_enforcer.check_approaching_limits(user_id, threshold_percent=80.0)
    
    return QuotaInfoResponse(
        user_tier=user_tier.value,
        quotas=usage_summary.get("quotas", {}),
        usage_stats=usage_summary.get("usage_stats", {}),
        warnings=warnings
    )


@router.post("/short-url")
@require_url_shortener_access("URL shortener not available for your tier")
@check_short_url_quota(1)
async def create_short_url(
    request: CreateShortUrlRequest,
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    quota_info: Dict[str, Any] = None,  # Injected by check_short_url_quota decorator
    db: Session = Depends(get_db)
):
    """
    Create a new short URL.
    
    This endpoint demonstrates:
    - Permission checking with @require_url_shortener_access
    - Quota enforcement with @check_short_url_quota
    - Custom vanity slug validation for tier permissions
    """
    user_id = str(current_user.id) if current_user else None
    
    # Check custom slug permission if requested
    if request.custom_slug:
        if not tier_manager.has_permission(user_id, "custom_vanity_slugs"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Custom vanity slugs not available for your tier"
            )
    
    # Track resource creation
    quota_enforcer = QuotaEnforcer(db)
    quota_enforcer.track_resource_creation(user_id, "short_url", {
        "target_url": request.target_url,
        "custom_slug": bool(request.custom_slug)
    })
    
    # In a real implementation, you would:
    # 1. Validate the target URL
    # 2. Generate or validate the slug
    # 3. Create the ShortUrl database record
    # 4. Return the created short URL
    
    return {
        "message": "Short URL created successfully",
        "slug": request.custom_slug or "generated-slug-123",
        "target_url": request.target_url,
        "quota_info": quota_info
    }


@router.get("/vip-feature")
@require_vip_tier()
async def vip_only_feature(
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep)
):
    """
    Example VIP-only feature.
    
    This endpoint demonstrates:
    - Tier-based access control with @require_vip_tier
    - Accessing user information in protected endpoints
    """
    user_id = str(current_user.id) if current_user else None
    user_tier = tier_manager.get_user_tier(user_id)
    
    return {
        "message": "Welcome to the VIP feature!",
        "user_tier": user_tier.value,
        "features": [
            "Custom vanity slugs",
            "Private pastes",
            "4GB media storage",
            "Priority support"
        ]
    }


@router.get("/tier-upgrade-suggestions")
async def get_tier_upgrade_suggestions(
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep)
):
    """
    Get personalized tier upgrade suggestions.
    
    This endpoint demonstrates:
    - Using TierManager to analyze usage patterns
    - Providing upgrade recommendations based on current usage
    """
    user_id = str(current_user.id) if current_user else None
    
    suggestions = tier_manager.get_tier_upgrade_suggestions(user_id)
    current_tier = tier_manager.get_user_tier(user_id)
    
    return {
        "current_tier": current_tier.value,
        "suggestions": suggestions,
        "message": "Upgrade suggestions based on your usage patterns"
    }


@router.post("/cleanup-expired")
async def cleanup_expired_resources(
    current_user: Optional[User] = Depends(get_current_user_dep),
    tier_manager: TierManager = Depends(get_tier_manager_dep),
    db: Session = Depends(get_db)
):
    """
    Clean up expired resources for the current user.
    
    This endpoint demonstrates:
    - Using QuotaEnforcer to clean up expired content
    - Freeing up quota space for users
    """
    user_id = str(current_user.id) if current_user else None
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    quota_enforcer = QuotaEnforcer(db)
    cleanup_results = quota_enforcer.cleanup_expired_resources(user_id)
    
    return {
        "message": "Cleanup completed",
        "results": cleanup_results,
        "freed_quota": {
            "short_urls": cleanup_results["expired_short_urls"],
            "pastes": cleanup_results["expired_pastes"],
            "storage_bytes": cleanup_results["storage_freed_bytes"]
        }
    }


# Error handlers for common permission/quota errors
@router.exception_handler(HTTPException)
async def permission_exception_handler(request, exc: HTTPException):
    """Handle permission-related HTTP exceptions with helpful messages."""
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        return {
            "error": "Permission denied",
            "message": exc.detail,
            "suggestion": "Consider upgrading your tier for access to this feature",
            "upgrade_endpoint": "/api/v1/tier-upgrade-suggestions"
        }
    elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        return {
            "error": "Quota exceeded",
            "message": exc.detail,
            "suggestion": "Clean up expired resources or upgrade your tier",
            "cleanup_endpoint": "/api/v1/cleanup-expired",
            "upgrade_endpoint": "/api/v1/tier-upgrade-suggestions"
        }
    
    return {"error": exc.detail}