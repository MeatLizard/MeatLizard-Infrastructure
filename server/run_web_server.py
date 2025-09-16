#!/usr/bin/env python3
"""
Development server runner for the AI Chat System web interface.
"""

import uvicorn
import os
import sys

# Add the server directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    # Set environment variables for development
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/ai_chat_system")
    
    print("🚀 Starting AI Chat System Web Server...")
    print("📍 Landing page: http://localhost:8000")
    print("💬 Chat interface: http://localhost:8000/chat")
    print("🔧 API docs: http://localhost:8000/docs")
    print("❤️  Health check: http://localhost:8000/health")
    print("\n" + "="*50)
    
    uvicorn.run(
        "web.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )