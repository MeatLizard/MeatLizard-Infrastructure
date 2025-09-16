from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.profile_service import ProfileService

router = APIRouter()

@router.get("/api/profile/{user_id}")
async def get_user_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    service = ProfileService(db)
    user = await service.get_user_profile(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    return {
        "display_label": user.display_label,
        "reputation_score": user.reputation_score,
        "experience_points": user.experience_points,
        "content_count": len(user.content)
    }