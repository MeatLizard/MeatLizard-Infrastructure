from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.db import get_db
from server.web.app.services.streaming_service import StreamingService

router = APIRouter()

@router.get("/api/stream/{media_id}")
async def stream_media(media_id: str, quality: str = "720p", db: AsyncSession = Depends(get_db)):
    service = StreamingService(db)
    media_file = await service.get_media_file(media_id)
    if not media_file:
        raise HTTPException(status_code=404, detail="Media file not found.")
    
    response = service.get_stream_response(media_file, quality)
    if not response:
        raise HTTPException(status_code=404, detail="Streamable file not found.")
        
    return response