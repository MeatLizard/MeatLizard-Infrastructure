"""
Discord Import Service for handling media imports via Discord bot commands.
"""
import asyncio
import logging
import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

from .media_import_service import MediaImportService, ImportConfig, MediaExtractionError
from .import_job_queue import ImportJobQueue
from ..models import User, ImportJob

logger = logging.getLogger(__name__)

class DiscordImportService:
    """Service for handling Discord-based media imports"""
    
    def __init__(self, bot: discord.Bot, db_session_factory, import_channel_id: int):
        self.bot = bot
        self.db_session_factory = db_session_factory
        self.import_channel_id = import_channel_id
        self.media_import_service = None
        self.job_queue = None
        
        # URL patterns for detecting media links
        self.url_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://youtu\.be/[\w-]+',
            r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+',
            r'https?://(?:www\.)?instagram\.com/p/[\w-]+',
            r'https?://(?:www\.)?twitter\.com/\w+/status/\d+',
            r'https?://(?:www\.)?x\.com/\w+/status/\d+',
            r'https?://(?:www\.)?vimeo\.com/\d+',
            r'https?://(?:www\.)?dailymotion\.com/video/[\w-]+',
            r'https?://(?:www\.)?twitch\.tv/videos/\d+',
            r'https?://(?:www\.)?reddit\.com/r/\w+/comments/[\w/]+',
            r'https?://(?:www\.)?facebook\.com/\w+/videos/\d+'
        ]
        
        # Reaction emojis for import options
        self.reaction_options = {
            '🎬': {'name': 'Standard Quality', 'config': {'max_height': 720, 'max_fps': 30}},
            '📺': {'name': 'High Quality', 'config': {'max_height': 1080, 'max_fps': 30}},
            '🎵': {'name': 'Audio Only', 'config': {'audio_only': True, 'audio_format': 'mp3'}},
            '⚡': {'name': 'Fast/Low Quality', 'config': {'max_height': 480, 'max_fps': 30}},
            '🚫': {'name': 'Cancel', 'config': None}
        }
    
    async def initialize(self):
        """Initialize the service with database session"""
        async with self.db_session_factory() as db:
            self.media_import_service = MediaImportService(db)
            self.job_queue = ImportJobQueue(db)
    
    async def handle_message(self, message: discord.Message) -> None:
        """Process messages in the import channel for URLs"""
        if message.channel.id != self.import_channel_id:
            return
        
        if message.author.bot:
            return
        
        # Check if user has admin permissions
        if not await self._is_admin_user(message.author):
            await message.reply("❌ Only administrators can use the import feature.")
            return
        
        # Extract URLs from message
        urls = self._extract_urls(message.content)
        
        if not urls:
            return
        
        # Process each URL
        for url in urls:
            if await self._is_supported_url(url):
                try:
                    await self._handle_import_url(message, url)
                except Exception as e:
                    logger.error(f"Failed to handle import URL {url}: {str(e)}")
                    await message.reply(f"❌ Failed to process URL: {str(e)}")
    
    async def handle_reaction(self, reaction: discord.Reaction, user: discord.User) -> None:
        """Process import option reactions from administrators"""
        if user.bot:
            return
        
        if not await self._is_admin_user(user):
            return
        
        # Check if this is an import options message
        if not self._is_import_options_message(reaction.message):
            return
        
        emoji = str(reaction.emoji)
        if emoji not in self.reaction_options:
            return
        
        option = self.reaction_options[emoji]
        
        if option['config'] is None:  # Cancel option
            await reaction.message.edit(content="❌ Import cancelled.", embed=None)
            await reaction.message.clear_reactions()
            return
        
        # Extract URL from the embed
        url = self._extract_url_from_embed(reaction.message.embeds[0])
        if not url:
            await reaction.message.reply("❌ Could not find URL in message.")
            return
        
        try:
            await self._initiate_import(reaction.message, url, option['config'], user)
        except Exception as e:
            logger.error(f"Failed to initiate import: {str(e)}")
            await reaction.message.reply(f"❌ Failed to start import: {str(e)}")
    
    async def _handle_import_url(self, message: discord.Message, url: str):
        """Handle a detected import URL"""
        try:
            # Extract media info
            async with self.db_session_factory() as db:
                service = MediaImportService(db)
                media_info = await service.extract_media_info(url)
            
            # Create import options embed
            embed = await self._create_import_options_embed(media_info, url)
            
            # Send message with options
            import_message = await message.reply(embed=embed)
            
            # Add reaction options
            for emoji in self.reaction_options.keys():
                await import_message.add_reaction(emoji)
                
        except MediaExtractionError as e:
            await message.reply(f"❌ Failed to extract media info: {str(e)}")
        except Exception as e:
            logger.error(f"Error handling import URL {url}: {str(e)}")
            await message.reply(f"❌ Error processing URL: {str(e)}")
    
    async def _create_import_options_embed(self, media_info, url: str) -> discord.Embed:
        """Create Discord embed with import options"""
        embed = discord.Embed(
            title="🎬 Media Import Options",
            description=f"**{media_info.title}**\n\nChoose import quality:",
            color=0x007bff
        )
        
        # Add media info fields
        embed.add_field(
            name="📺 Platform",
            value=media_info.platform,
            inline=True
        )
        
        embed.add_field(
            name="👤 Uploader",
            value=media_info.uploader,
            inline=True
        )
        
        if media_info.duration:
            duration = self._format_duration(media_info.duration)
            embed.add_field(
                name="⏱️ Duration",
                value=duration,
                inline=True
            )
        
        if media_info.view_count:
            views = self._format_number(media_info.view_count)
            embed.add_field(
                name="👁️ Views",
                value=views,
                inline=True
            )
        
        # Add options
        options_text = "\n".join([
            f"{emoji} {option['name']}" 
            for emoji, option in self.reaction_options.items()
        ])
        
        embed.add_field(
            name="Import Options",
            value=options_text,
            inline=False
        )
        
        # Add thumbnail if available
        if media_info.thumbnail_url:
            embed.set_thumbnail(url=media_info.thumbnail_url)
        
        # Store URL in footer for extraction later
        embed.set_footer(text=f"Source: {url}")
        
        return embed
    
    async def _initiate_import(self, message: discord.Message, url: str, 
                             config_override: Dict[str, Any], user: discord.User):
        """Initiate the import process"""
        try:
            # Get or create user record
            async with self.db_session_factory() as db:
                # For now, use a default admin user ID
                # In a real implementation, you'd map Discord users to system users
                admin_user_id = "00000000-0000-0000-0000-000000000001"  # Default admin
                
                # Create import config
                config = ImportConfig(
                    max_height=config_override.get('max_height'),
                    max_fps=config_override.get('max_fps'),
                    audio_only=config_override.get('audio_only', False),
                    audio_format=config_override.get('audio_format', 'mp3'),
                    quality_presets=['720p_30fps'],  # Default preset
                    preserve_metadata=True,
                    auto_publish=False
                )
                
                # Create import job
                service = MediaImportService(db)
                job = await service.create_import_job(
                    url=url,
                    config=config,
                    user_id=admin_user_id,
                    discord_channel_id=str(message.channel.id),
                    discord_message_id=str(message.id)
                )
                
                # Queue job for processing
                job_queue = ImportJobQueue(db)
                await job_queue.queue_job(str(job.id))
                
                # Update message
                embed = discord.Embed(
                    title="✅ Import Started",
                    description=f"Import job created successfully!\n\n**Job ID:** `{job.id}`",
                    color=0x28a745
                )
                
                embed.add_field(
                    name="Status",
                    value="Queued for processing",
                    inline=True
                )
                
                embed.add_field(
                    name="Configuration",
                    value=self._format_config(config_override),
                    inline=True
                )
                
                await message.edit(embed=embed)
                await message.clear_reactions()
                
                # Start monitoring job progress
                asyncio.create_task(self._monitor_job_progress(job.id, message))
                
        except Exception as e:
            logger.error(f"Failed to initiate import: {str(e)}")
            raise
    
    async def _monitor_job_progress(self, job_id: str, message: discord.Message):
        """Monitor import job progress and update Discord message"""
        try:
            while True:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                async with self.db_session_factory() as db:
                    service = MediaImportService(db)
                    jobs = await service.get_import_jobs(limit=1)
                    job = next((j for j in jobs if str(j.id) == job_id), None)
                    
                    if not job:
                        break
                    
                    # Update embed based on status
                    if job.status in ['completed', 'failed']:
                        await self._update_final_status(message, job)
                        break
                    else:
                        await self._update_progress_status(message, job)
                        
        except Exception as e:
            logger.error(f"Error monitoring job progress: {str(e)}")
    
    async def _update_progress_status(self, message: discord.Message, job: ImportJob):
        """Update message with current progress"""
        try:
            status_colors = {
                'queued': 0x6c757d,
                'downloading': 0x007bff,
                'processing': 0xffc107
            }
            
            embed = discord.Embed(
                title=f"🔄 Import {job.status.title()}",
                description=f"**{job.original_title or 'Untitled'}**",
                color=status_colors.get(job.status, 0x6c757d)
            )
            
            embed.add_field(
                name="Progress",
                value=f"{job.progress_percent}%",
                inline=True
            )
            
            embed.add_field(
                name="Status",
                value=job.status.title(),
                inline=True
            )
            
            embed.add_field(
                name="Job ID",
                value=f"`{job.id}`",
                inline=True
            )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to update progress status: {str(e)}")
    
    async def _update_final_status(self, message: discord.Message, job: ImportJob):
        """Update message with final status"""
        try:
            if job.status == 'completed':
                embed = discord.Embed(
                    title="✅ Import Completed",
                    description=f"**{job.original_title or 'Untitled'}**\n\nImport completed successfully!",
                    color=0x28a745
                )
                
                if job.video_id:
                    embed.add_field(
                        name="Video",
                        value=f"[View Video](/video/{job.video_id})",
                        inline=True
                    )
            else:
                embed = discord.Embed(
                    title="❌ Import Failed",
                    description=f"**{job.original_title or 'Untitled'}**\n\nImport failed.",
                    color=0xdc3545
                )
                
                if job.error_message:
                    embed.add_field(
                        name="Error",
                        value=job.error_message[:1000],  # Limit length
                        inline=False
                    )
            
            embed.add_field(
                name="Job ID",
                value=f"`{job.id}`",
                inline=True
            )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to update final status: {str(e)}")
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from message text"""
        urls = []
        for pattern in self.url_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            urls.extend(matches)
        return list(set(urls))  # Remove duplicates
    
    async def _is_supported_url(self, url: str) -> bool:
        """Check if URL is from a supported platform"""
        async with self.db_session_factory() as db:
            service = MediaImportService(db)
            return service.is_supported_url(url)
    
    async def _is_admin_user(self, user: discord.User) -> bool:
        """Check if user has admin permissions"""
        # In a real implementation, you'd check against a database of admin users
        # For now, check if user has administrator permissions in the guild
        if hasattr(user, 'guild_permissions'):
            return user.guild_permissions.administrator
        return False
    
    def _is_import_options_message(self, message: discord.Message) -> bool:
        """Check if message is an import options message"""
        if not message.embeds:
            return False
        
        embed = message.embeds[0]
        return embed.title and "Media Import Options" in embed.title
    
    def _extract_url_from_embed(self, embed: discord.Embed) -> Optional[str]:
        """Extract URL from embed footer"""
        if embed.footer and embed.footer.text:
            if embed.footer.text.startswith("Source: "):
                return embed.footer.text[8:]  # Remove "Source: " prefix
        return None
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def _format_number(self, num: int) -> str:
        """Format large numbers with K/M suffixes"""
        if num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        else:
            return str(num)
    
    def _format_config(self, config: Dict[str, Any]) -> str:
        """Format import configuration for display"""
        parts = []
        
        if config.get('max_height'):
            parts.append(f"{config['max_height']}p")
        
        if config.get('max_fps'):
            parts.append(f"{config['max_fps']}fps")
        
        if config.get('audio_only'):
            parts.append("Audio Only")
        
        return " • ".join(parts) if parts else "Default"


# Note: The DiscordImportBot class has been removed as media import functionality
# is now integrated into the main server bot as a cog (server/server_bot/cogs/media_import.py)