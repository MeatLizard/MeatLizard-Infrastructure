
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.url_shortener import URLShortenerService
from server.web.app.models import User
from server.web.app.middleware.permissions import get_current_user, PermissionChecker

router = APIRouter()

class ShortenRequest(BaseModel):
    target_url: str
    custom_slug: str = None

@router.post("/api/shorten", dependencies=[Depends(PermissionChecker("allow_vanity_slugs"))])
async def shorten_url(
    request: ShortenRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    service = URLShortenerService(db)
    if not service.is_valid_url(request.target_url):
        raise HTTPException(status_code=400, detail="Invalid target URL.")
    
    try:
        short_url = await service.create_short_url(request.target_url, user, request.custom_slug)
        return {"short_url": f"/{short_url.slug}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{slug}")
async def redirect_to_target(slug: str, db: AsyncSession = Depends(get_db)):
    service = URLShortenerService(db)
    short_url = await service.get_url_by_slug(slug) # This method needs to be implemented
    if not short_url:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    
    # In a real app, you'd return a RedirectResponse
    return {"target_url": short_url.target_url}
