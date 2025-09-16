from sqlalchemy.ext.asyncio import AsyncSession
from server.celery_app import celery_app
from server.web.app.models import AnalyticsEvent, MediaFile
from server.web.app.services.transcoding_service import TranscodingService
from server.web.app.services.uptime_service import UptimeService
from server.web.app.db import AsyncSessionLocal as SessionLocal
from shared_lib.config import get_config
import httpx

settings = get_config()

@celery_app.task
def process_analytics_event(event_data: dict):
    # In a real app, you would have a database session available to store the event
    print(f"Processing analytics event: {event_data}")

@celery_app.task
def transcode_media_file(media_file_id: str):
    # In a real app, you would have a database session available to get the media file
    print(f"Transcoding media file: {media_file_id}")

@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(60.0, check_ai_endpoint_status.s(), name='check ai endpoint every 60 seconds')

@celery_app.task
async def check_ai_endpoint_status():
    """
    Periodically checks the status of the AI endpoint and records it.
    """
    # In a real app, this URL would be configurable
    ai_endpoint_url = "http://localhost:8000/health" # Assuming the main app health check is a proxy for the AI service
    
    async with SessionLocal() as session:
        uptime_service = UptimeService(session)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(ai_endpoint_url)
                if response.status_code == 200:
                    await uptime_service.record_status("AI Endpoint", is_online=True)
                else:
                    await uptime_service.record_status("AI Endpoint", is_online=False, details=f"Status code: {response.status_code}")
        except httpx.RequestError as e:
            await uptime_service.record_status("AI Endpoint", is_online=False, details=str(e))
