# server/web/app/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import asyncio

from server.web.app.config import get_settings

# Import frontend routes
from server.web.app.api.frontend import (
    landing, chat, pastebin, url_shortener, file_storage, video_player, 
    video_upload as video_upload_frontend, channels as channels_frontend, 
    video_settings, analytics_dashboard, admin_dashboard, 
    media_import as media_import_frontend, dashboard, profile, 
    leaderboard, trending
)

# Import API routes
from server.web.app.api import (
    auth, email, chat as api_chat, pastebin as api_pastebin, 
    url_shortener as api_url_shortener, video_upload, video_metadata, 
    quality_presets, video_thumbnails, transcoding, streaming, 
    video_likes, video_comments, viewing_history, channels, playlists, 
    content_discovery, video_access_control, secure_streaming, 
    content_moderation, video_analytics, system_monitoring, admin_video, 
    system_config, media_import, imported_content, uptime, sessions,
    social, profiles, leaderboards, reporting, analytics_examples,
    rate_limit_examples
)

settings = get_settings()

app = FastAPI(
    title="MeatLizard AI Platform",
    description="Private AI chat platform with integrated content sharing and collaboration tools.",
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [f"https://{settings.DOMAIN}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="server/web/app/static"), name="static")

# Frontend routes (HTML pages)
app.include_router(landing.router)
app.include_router(dashboard.router)
app.include_router(profile.router)
app.include_router(leaderboard.router)
app.include_router(trending.router)
app.include_router(chat.router)
app.include_router(pastebin.router)
app.include_router(url_shortener.router)
app.include_router(file_storage.router)
app.include_router(video_player.router)
app.include_router(video_upload_frontend.router)
app.include_router(channels_frontend.router)
app.include_router(video_settings.router)
app.include_router(analytics_dashboard.router)
app.include_router(admin_dashboard.router)
app.include_router(media_import_frontend.router)

# API routes
app.include_router(auth.router)
app.include_router(email.router)
app.include_router(api_chat.router, prefix="/api")
app.include_router(api_pastebin.router, prefix="/api")
app.include_router(api_url_shortener.router, prefix="/api")
app.include_router(video_upload.router, prefix="/api")
app.include_router(video_metadata.router, prefix="/api")
app.include_router(quality_presets.router, prefix="/api")
app.include_router(video_thumbnails.router, prefix="/api")
app.include_router(transcoding.router, prefix="/api")
app.include_router(streaming.router, prefix="/api")
app.include_router(video_likes.router, prefix="/api")
app.include_router(video_comments.router, prefix="/api")
app.include_router(viewing_history.router, prefix="/api")
app.include_router(channels.router, prefix="/api")
app.include_router(playlists.router, prefix="/api")
app.include_router(content_discovery.router, prefix="/api")
app.include_router(video_access_control.router, prefix="/api")
app.include_router(secure_streaming.router, prefix="/api")
app.include_router(content_moderation.router, prefix="/api")
app.include_router(video_analytics.router, prefix="/api")
app.include_router(system_monitoring.router, prefix="/api")
app.include_router(admin_video.router, prefix="/api")
app.include_router(system_config.router, prefix="/api")
app.include_router(media_import.router, prefix="/api")
app.include_router(imported_content.router, prefix="/api")
app.include_router(uptime.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(social.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(leaderboards.router, prefix="/api")
app.include_router(reporting.router, prefix="/api")

# Global message queue for server bot communication
app.state.message_queue = asyncio.Queue()
app.state.response_queues = {}

@app.get("/")
async def root():
    """Redirect root to landing page."""
    return RedirectResponse(url="/", status_code=302)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "web", "version": settings.VERSION}