#!/usr/bin/env python3
"""
Development server runner for the AI Chat System web interface.
"""

import uvicorn
import os
import sys
import asyncio
import threading
from dotenv import load_dotenv

# Add the server directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from server_bot.bot import run_bot_with_queue

def run_bot(queue, response_queues, token):
    # Run the bot in a new event loop in a separate thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    run_bot_with_queue(queue, response_queues, token)

if __name__ == "__main__":
    load_dotenv()
    # Set environment variables for development
    os.environ.setdefault("DATABASE_URL", os.getenv("DATABASE_URL"))
    
    print("🚀 Starting AI Chat System Web Server...")
    
    # Create a queue for communication between web server and bot
    message_queue = asyncio.Queue()
    response_queues = {}
    
    # Start the bot in a separate thread
    bot_token = os.getenv("SERVER_BOT_TOKEN")
    if not bot_token:
        print("🚨 SERVER_BOT_TOKEN environment variable not set. Bot will not be started.")
    else:
        bot_thread = threading.Thread(target=run_bot, args=(message_queue, response_queues, bot_token))
        bot_thread.daemon = True
        bot_thread.start()

    # Inject the queue into the FastAPI app state
    from web.app.main import app
    app.state.message_queue = message_queue
    app.state.response_queues = response_queues

    print("📍 Landing page: http://localhost:8000")
    print("💬 Chat interface: http://localhost:8000/chat")
    print("🔧 API docs: http://localhost:8000/docs")
    print("❤️  Health check: http://localhost:8000/health")
    print("\n" + "="*50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
