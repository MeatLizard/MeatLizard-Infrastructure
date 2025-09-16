# server/web/app/main.py
from fastapi import FastAPI
from server.web.app.api.frontend import chat, pastebin, url_shortener, file_storage, video_player
from server.web.app.api import chat as api_router

app = FastAPI(
    title="MeatLizard AI Platform API",
    description="API for managing AI chat sessions.",
    version="1.0.0",
)

app.include_router(chat.router)
app.include_router(pastebin.router)
app.include_router(url_shortener.router)
app.include_router(file_storage.router)
app.include_router(video_player.router)
app.include_router(api_router.router, prefix="/api")