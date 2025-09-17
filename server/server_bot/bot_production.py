"""
Production-ready Discord Server Bot for MeatLizard AI Platform.
Handles session management, Discord integration, and bot coordination.
"""
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import asyncio
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import base64

# Import shared libraries
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from server.shared_lib.encryption import PayloadEncryptor
from server.shared_lib.config import ServerBotConfig
from server.web.app.models import (
    User, AIChatSession, AIChatMessage, SystemMetrics, 
    UptimeRecord, BackupLog
)
from server.web.app.db import get_async_session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MeatLizardServerBot(commands.Bot):
    """Production Discord Server Bot for MeatLizard AI Platform."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        
        super().__init__(
            command_prefix="!ml",
            intents=intents,
            help_command=None
        )
        
        # Configuration
        self.config = ServerBotConfig()
        self.encryptor = PayloadEncryptor(self.config.PAYLOAD_ENCRYPTION_KEY)
        
        # State management
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.client_bot_id: Optional[int] = None
        self.guild: Optional[discord.Guild] = None
        
        # Message queues for FastAPI communication
        self.message_queue: Optional[asyncio.Queue] = None
        self.response_queues: Dict[str, asyncio.Queue] = {}
        
        # Database session
        self.db_session: Optional[AsyncSession] = None
    
    async def setup_hook(self):
        """Initialize bot components."""
        logger.info("Setting up MeatLizard Server Bot...")
        
        # Setup database
        await self._setup_database()
        
        # Load cogs
        await self._load_cogs()
        
        # Start background tasks
        self.health_monitor.start()
        self.session_cleanup.start()
        self.metrics_collector.start()
        
        # Sync commands
        await self._sync_commands()
        
        logger.info("Server Bot setup complete")
    
    async def _setup_database(self):
        """Setup database connection."""
        try:
            self.db_session = get_async_session()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to setup database: {e}")
            raise
    
    async def _load_cogs(self):
        """Load bot command cogs."""
        cogs = [
            'server.server_bot.cogs.admin',
            'server.server_bot.cogs.chat',
            'server.server_bot.cogs.moderation',
            'server.server_bot.cogs.metrics'
        ]
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}")
    
    async def _sync_commands(self):
        """Sync slash commands."""
        try:
            if self.config.GUILD_ID:
                guild = discord.Object(id=self.config.GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Commands synced to guild {self.config.GUILD_ID}")
            else:
                await self.tree.sync()
                logger.info("Commands synced globally")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Bot ready event handler."""
        logger.info(f"Bot logged in as {self.user}")
        
        # Get guild and client bot
        if self.config.GUILD_ID:
            self.guild = self.get_guild(self.config.GUILD_ID)
            if not self.guild:
                logger.error(f"Guild {self.config.GUILD_ID} not found")
                return
        
        # Find client bot
        if self.config.CLIENT_BOT_ID:
            client_bot = self.guild.get_member(self.config.CLIENT_BOT_ID)
            if client_bot:
                self.client_bot_id = client_bot.id
                logger.info(f"Client bot found: {client_bot.name}")
            else:
                logger.warning(f"Client bot {self.config.CLIENT_BOT_ID} not found in guild")
        
        # Start message processing
        self.loop.create_task(self._process_message_queue())
        
        logger.info("Server Bot is ready and operational")
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        if message.author == self.user:
            return
        
        # Handle client bot responses
        if (message.author.id == self.client_bot_id and 
            message.channel.name.startswith("session-")):
            await self._handle_client_response(message)
        
        # Handle metrics messages
        elif (message.channel.name == "ai-metrics" and 
              message.author.id == self.client_bot_id):
            await self._handle_metrics_message(message)
        
        # Process commands
        await self.process_commands(message)
    
    async def _handle_client_response(self, message: discord.Message):
        """Handle response from client bot."""
        try:
            session_id = message.channel.name.replace("session-", "")
            
            if session_id not in self.response_queues:
                logger.warning(f"No response queue for session {session_id}")
                return
            
            # Decrypt response
            decrypted_data = self.encryptor.decrypt(message.content)
            
            # Put response in queue
            await self.response_queues[session_id].put(decrypted_data["response"])
            
            # Log to database
            await self._log_ai_message(session_id, decrypted_data)
            
        except Exception as e:
            logger.error(f"Error handling client response: {e}")
    
    async def _handle_metrics_message(self, message: discord.Message):
        """Handle metrics from client bot."""
        try:
            decrypted_data = self.encryptor.decrypt(message.content)
            
            # Store metrics in database
            async with self.db_session() as db:
                metric = SystemMetrics(
                    client_bot_id=str(message.author.id),
                    timestamp=datetime.utcnow(),
                    data=decrypted_data
                )
                db.add(metric)
                await db.commit()
            
            logger.info("Stored client bot metrics")
            
        except Exception as e:
            logger.error(f"Error handling metrics: {e}")
    
    async def _process_message_queue(self):
        """Process messages from FastAPI web server."""
        while True:
            try:
                if self.message_queue:
                    message = await self.message_queue.get()
                    await self._handle_web_message(message)
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error processing message queue: {e}")
                await asyncio.sleep(5)
    
    async def _handle_web_message(self, message: Dict[str, Any]):
        """Handle message from web server."""
        action = message.get("action")
        
        if action == "create_session":
            await self._create_session(message)
        elif action == "send_message":
            await self._send_ai_request(message)
        elif action == "close_session":
            await self._close_session(message)
        else:
            logger.warning(f"Unknown action: {action}")
    
    async def _create_session(self, message: Dict[str, Any]):
        """Create a new AI chat session."""
        try:
            session_id = message["session_id"]
            user_id = message.get("user_id")
            
            # Create Discord channel
            channel = await self._create_session_channel(session_id)
            
            # Store session info
            self.active_sessions[session_id] = {
                "channel_id": channel.id,
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "message_count": 0
            }
            
            # Create response queue
            self.response_queues[session_id] = asyncio.Queue()
            
            # Log to database
            await self._log_session_creation(session_id, channel.id, user_id)
            
            logger.info(f"Created session {session_id} in channel {channel.name}")
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
    
    async def _create_session_channel(self, session_id: str) -> discord.TextChannel:
        """Create a private Discord channel for the session."""
        if not self.guild:
            raise RuntimeError("Guild not available")
        
        # Get or create category
        category_name = "AI Chat Sessions"
        category = discord.utils.get(self.guild.categories, name=category_name)
        if not category:
            category = await self.guild.create_category(category_name)
        
        # Set permissions
        overwrites = {
            self.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            self.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add client bot permissions
        if self.client_bot_id:
            client_bot = self.guild.get_member(self.client_bot_id)
            if client_bot:
                overwrites[client_bot] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )
        
        # Add admin permissions
        for role_id in self.config.ADMIN_ROLES:
            role = self.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True)
        
        # Create channel
        channel = await self.guild.create_text_channel(
            name=f"session-{session_id[:8]}",
            category=category,
            overwrites=overwrites,
            topic=f"AI Chat Session {session_id}"
        )
        
        return channel
    
    async def _send_ai_request(self, message: Dict[str, Any]):
        """Send AI inference request to client bot."""
        try:
            session_id = message["session_id"]
            prompt = message["prompt"]
            request_id = message["request_id"]
            options = message.get("options", {})
            
            if session_id not in self.active_sessions:
                logger.error(f"Session {session_id} not found")
                return
            
            # Get channel
            channel_id = self.active_sessions[session_id]["channel_id"]
            channel = self.guild.get_channel(channel_id)
            
            if not channel:
                logger.error(f"Channel {channel_id} not found")
                return
            
            # Prepare request data
            request_data = {
                "session_id": session_id,
                "request_id": request_id,
                "prompt": prompt,
                "temperature": options.get("temperature", 0.7),
                "max_tokens": options.get("max_tokens", 2048),
                "model_alias": options.get("model_alias", "default"),
                "stream": options.get("stream", True)
            }
            
            # Encrypt and send
            encrypted_request = self.encryptor.encrypt(request_data)
            await channel.send(encrypted_request)
            
            # Update session stats
            self.active_sessions[session_id]["message_count"] += 1
            
            logger.info(f"Sent AI request for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error sending AI request: {e}")
    
    async def _close_session(self, message: Dict[str, Any]):
        """Close an AI chat session."""
        try:
            session_id = message["session_id"]
            reason = message.get("reason", "user_disconnect")
            
            if session_id not in self.active_sessions:
                logger.warning(f"Session {session_id} not found for closure")
                return
            
            # Get channel
            channel_id = self.active_sessions[session_id]["channel_id"]
            channel = self.guild.get_channel(channel_id)
            
            # Archive transcript
            if channel:
                await self._archive_transcript(session_id, channel)
                await channel.delete(reason=f"Session ended: {reason}")
            
            # Clean up
            if session_id in self.response_queues:
                del self.response_queues[session_id]
            
            del self.active_sessions[session_id]
            
            # Log closure
            await self._log_session_closure(session_id, reason)
            
            logger.info(f"Closed session {session_id}")
            
        except Exception as e:
            logger.error(f"Error closing session: {e}")
    
    async def _archive_transcript(self, session_id: str, channel: discord.TextChannel):
        """Archive session transcript to S3."""
        try:
            messages = []
            async for message in channel.history(limit=None, oldest_first=True):
                if not message.author.bot:
                    continue
                
                messages.append({
                    "timestamp": message.created_at.isoformat(),
                    "author": str(message.author),
                    "content": message.content,
                    "message_id": str(message.id)
                })
            
            transcript = {
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
                "message_count": len(messages),
                "messages": messages
            }
            
            # TODO: Upload to S3
            # For now, just log
            logger.info(f"Archived transcript for session {session_id} ({len(messages)} messages)")
            
        except Exception as e:
            logger.error(f"Error archiving transcript: {e}")
    
    async def _log_session_creation(self, session_id: str, channel_id: int, user_id: Optional[str]):
        """Log session creation to database."""
        try:
            async with self.db_session() as db:
                session = AIChatSession(
                    id=uuid.UUID(session_id),
                    user_id=uuid.UUID(user_id) if user_id else None,
                    discord_channel_id=channel_id,
                    content_type="aichat"
                )
                db.add(session)
                await db.commit()
        except Exception as e:
            logger.error(f"Error logging session creation: {e}")
    
    async def _log_session_closure(self, session_id: str, reason: str):
        """Log session closure to database."""
        try:
            async with self.db_session() as db:
                result = await db.execute(
                    select(AIChatSession).where(AIChatSession.id == uuid.UUID(session_id))
                )
                session = result.scalar_one_or_none()
                if session:
                    session.ended_at = datetime.utcnow()
                    await db.commit()
        except Exception as e:
            logger.error(f"Error logging session closure: {e}")
    
    async def _log_ai_message(self, session_id: str, message_data: Dict[str, Any]):
        """Log AI message to database."""
        try:
            async with self.db_session() as db:
                message = AIChatMessage(
                    session_id=uuid.UUID(session_id),
                    request_id=uuid.UUID(message_data.get("request_id", str(uuid.uuid4()))),
                    role="assistant",
                    content=message_data["response"],
                    timestamp=datetime.utcnow()
                )
                db.add(message)
                await db.commit()
        except Exception as e:
            logger.error(f"Error logging AI message: {e}")
    
    @tasks.loop(minutes=5)
    async def health_monitor(self):
        """Monitor system health."""
        try:
            # Record uptime
            async with self.db_session() as db:
                uptime_record = UptimeRecord(
                    service_name="server_bot",
                    is_online=True,
                    timestamp=datetime.utcnow(),
                    details=f"Active sessions: {len(self.active_sessions)}"
                )
                db.add(uptime_record)
                await db.commit()
        except Exception as e:
            logger.error(f"Error in health monitor: {e}")
    
    @tasks.loop(hours=1)
    async def session_cleanup(self):
        """Clean up stale sessions."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            stale_sessions = []
            
            for session_id, session_data in self.active_sessions.items():
                if session_data["created_at"] < cutoff_time:
                    stale_sessions.append(session_id)
            
            for session_id in stale_sessions:
                await self._close_session({
                    "session_id": session_id,
                    "reason": "timeout"
                })
            
            if stale_sessions:
                logger.info(f"Cleaned up {len(stale_sessions)} stale sessions")
                
        except Exception as e:
            logger.error(f"Error in session cleanup: {e}")
    
    @tasks.loop(minutes=30)
    async def metrics_collector(self):
        """Collect and aggregate metrics."""
        try:
            metrics = {
                "active_sessions": len(self.active_sessions),
                "total_channels": len([c for c in self.guild.channels if c.name.startswith("session-")]),
                "uptime": datetime.utcnow().isoformat(),
                "guild_member_count": self.guild.member_count if self.guild else 0
            }
            
            async with self.db_session() as db:
                metric_record = SystemMetrics(
                    client_bot_id="server_bot",
                    timestamp=datetime.utcnow(),
                    data=metrics
                )
                db.add(metric_record)
                await db.commit()
                
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
    
    def set_message_queue(self, queue: asyncio.Queue):
        """Set the message queue for FastAPI communication."""
        self.message_queue = queue
    
    def get_response_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        """Get response queue for a session."""
        return self.response_queues.get(session_id)

# Global bot instance
bot = MeatLizardServerBot()

def run_server_bot():
    """Run the server bot."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN not found in environment")
        return
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to run server bot: {e}")

if __name__ == "__main__":
    run_server_bot()