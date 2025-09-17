"""
Production-ready Discord Client Bot for MeatLizard AI Platform.
Handles AI inference using llama.cpp with Apple Metal acceleration.
"""
import discord
from discord.ext import commands, tasks
import os
import json
import uuid
import asyncio
import logging
import psutil
import subprocess
from datetime import datetime
from typing import Dict, Optional, Any, AsyncIterator
import yaml
import base64
from pathlib import Path

# Import configuration and encryption
from config import ClientBotConfig
from llama_cpp_wrapper import LlamaCppWrapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PayloadEncryptor:
    """Handle AES-256-GCM encryption for bot communication."""
    
    def __init__(self, key_b64: str):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        self.key = base64.b64decode(key_b64)
        self.aesgcm = AESGCM(self.key)
    
    def encrypt(self, data: dict) -> str:
        """Encrypt data to base64 string."""
        plaintext = json.dumps(data).encode('utf-8')
        nonce = os.urandom(12)  # Use random nonce for security
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)
        # Prepend nonce to ciphertext
        encrypted_data = nonce + ciphertext
        return base64.b64encode(encrypted_data).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> dict:
        """Decrypt base64 string to data."""
        encrypted_bytes = base64.b64decode(encrypted_data)
        nonce = encrypted_bytes[:12]
        ciphertext = encrypted_bytes[12:]
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))

class ModelManager:
    """Manage loading and unloading of language models."""
    
    def __init__(self, config: ClientBotConfig):
        self.config = config
        self.models: Dict[str, LlamaCppWrapper] = {}
        self.max_loaded_models = 2
        self.model_usage = {}  # Track usage for LRU
    
    async def get_model(self, alias: str) -> LlamaCppWrapper:
        """Get or load a model by alias."""
        if alias not in self.config.models:
            raise ValueError(f"Unknown model alias: {alias}")
        
        if alias not in self.models:
            if len(self.models) >= self.max_loaded_models:
                await self._unload_lru_model()
            
            await self._load_model(alias)
        
        # Update usage
        self.model_usage[alias] = datetime.utcnow()
        return self.models[alias]
    
    async def _load_model(self, alias: str):
        """Load a model from disk."""
        model_config = self.config.models[alias]
        logger.info(f"Loading model {alias} from {model_config['path']}")
        
        try:
            wrapper = LlamaCppWrapper(
                model_path=model_config["path"],
                n_ctx=self.config.llama_cpp.n_ctx,
                n_threads=self.config.llama_cpp.threads,
                n_gpu_layers=self.config.llama_cpp.n_gpu_layers
            )
            self.models[alias] = wrapper
            self.model_usage[alias] = datetime.utcnow()
            logger.info(f"Successfully loaded model {alias}")
        except Exception as e:
            logger.error(f"Failed to load model {alias}: {e}")
            raise
    
    async def _unload_lru_model(self):
        """Unload the least recently used model."""
        if not self.model_usage:
            return
        
        lru_alias = min(self.model_usage.keys(), key=lambda k: self.model_usage[k])
        logger.info(f"Unloading LRU model: {lru_alias}")
        
        if lru_alias in self.models:
            del self.models[lru_alias]
        del self.model_usage[lru_alias]

class SystemMonitor:
    """Monitor system resources and performance."""
    
    def __init__(self):
        self.start_time = datetime.utcnow()
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # GPU metrics (macOS Metal)
            gpu_metrics = self._get_gpu_metrics()
            
            # Battery (if available)
            battery_metrics = self._get_battery_metrics()
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_total_mb": memory.total / (1024 * 1024),
                "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
                **gpu_metrics,
                **battery_metrics
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {"error": str(e)}
    
    def _get_gpu_metrics(self) -> Dict[str, Any]:
        """Get GPU metrics for Apple Silicon."""
        try:
            # Use system_profiler to get GPU info on macOS
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                # Extract GPU information
                displays = data.get("SPDisplaysDataType", [])
                if displays:
                    gpu_info = displays[0]
                    return {
                        "gpu_name": gpu_info.get("sppci_model", "Unknown"),
                        "gpu_memory_mb": self._parse_memory_string(
                            gpu_info.get("sppci_vram", "0 MB")
                        )
                    }
        except Exception as e:
            logger.debug(f"Could not get GPU metrics: {e}")
        
        return {"gpu_name": "Unknown", "gpu_memory_mb": 0}
    
    def _get_battery_metrics(self) -> Dict[str, Any]:
        """Get battery metrics if available."""
        try:
            battery = psutil.sensors_battery()
            if battery:
                return {
                    "battery_percent": battery.percent,
                    "battery_plugged": battery.power_plugged
                }
        except Exception:
            pass
        
        return {}
    
    def _parse_memory_string(self, memory_str: str) -> float:
        """Parse memory string like '8 GB' to MB."""
        try:
            parts = memory_str.split()
            if len(parts) >= 2:
                value = float(parts[0])
                unit = parts[1].upper()
                if unit == "GB":
                    return value * 1024
                elif unit == "MB":
                    return value
        except Exception:
            pass
        return 0

class MeatLizardClientBot(commands.Bot):
    """Production Discord Client Bot for AI inference."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        
        super().__init__(
            command_prefix="!client",
            intents=intents,
            help_command=None
        )
        
        # Load configuration
        self.config = ClientBotConfig()
        self.encryptor = PayloadEncryptor(self.config.payload_encryption_key)
        
        # Initialize components
        self.model_manager = ModelManager(self.config)
        self.system_monitor = SystemMonitor()
        
        # State
        self.server_bot_id: Optional[int] = None
        self.guild: Optional[discord.Guild] = None
        self.metrics_channel: Optional[discord.TextChannel] = None
        
        # Performance tracking
        self.inference_count = 0
        self.total_inference_time = 0.0
        self.error_count = 0
    
    async def setup_hook(self):
        """Initialize bot components."""
        logger.info("Setting up MeatLizard Client Bot...")
        
        # Start background tasks
        self.health_reporter.start()
        self.performance_monitor.start()
        
        logger.info("Client Bot setup complete")
    
    async def on_ready(self):
        """Bot ready event handler."""
        logger.info(f"Client Bot logged in as {self.user}")
        
        # Find server bot and guild
        for guild in self.guilds:
            server_bot = guild.get_member(self.config.server_bot_id)
            if server_bot:
                self.server_bot_id = server_bot.id
                self.guild = guild
                logger.info(f"Found server bot in guild: {guild.name}")
                break
        
        if not self.guild:
            logger.error("Could not find server bot in any guild")
            return
        
        # Find metrics channel
        self.metrics_channel = discord.utils.get(
            self.guild.channels, name="ai-metrics"
        )
        if not self.metrics_channel:
            logger.warning("ai-metrics channel not found")
        
        logger.info("Client Bot is ready for inference requests")
    
    async def on_message(self, message: discord.Message):
        """Handle incoming messages."""
        if message.author == self.user:
            return
        
        # Only process messages from server bot in session channels
        if (message.author.id == self.server_bot_id and 
            message.channel.name.startswith("session-")):
            await self._handle_inference_request(message)
        
        await self.process_commands(message)
    
    async def _handle_inference_request(self, message: discord.Message):
        """Handle AI inference request from server bot."""
        try:
            # Decrypt request
            request_data = self.encryptor.decrypt(message.content)
            
            session_id = request_data["session_id"]
            request_id = request_data["request_id"]
            prompt = request_data["prompt"]
            
            logger.info(f"Processing inference request {request_id} for session {session_id}")
            
            # Get model
            model_alias = request_data.get("model_alias", "default")
            model = await self.model_manager.get_model(model_alias)
            
            # Perform inference
            start_time = datetime.utcnow()
            
            if request_data.get("stream", True):
                await self._stream_inference(message.channel, request_data, model)
            else:
                await self._batch_inference(message.channel, request_data, model)
            
            # Update performance metrics
            inference_time = (datetime.utcnow() - start_time).total_seconds()
            self.inference_count += 1
            self.total_inference_time += inference_time
            
            logger.info(f"Completed inference request {request_id} in {inference_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error handling inference request: {e}")
            self.error_count += 1
            await self._send_error_response(message.channel, request_data, str(e))
    
    async def _stream_inference(self, channel: discord.TextChannel, request_data: Dict, model: LlamaCppWrapper):
        """Perform streaming inference."""
        session_id = request_data["session_id"]
        request_id = request_data["request_id"]
        
        try:
            response_chunks = []
            token_count = 0
            
            async for chunk in model.generate_stream(
                prompt=request_data["prompt"],
                temperature=request_data.get("temperature", 0.7),
                max_tokens=request_data.get("max_tokens", 2048)
            ):
                response_chunks.append(chunk)
                token_count += 1
                
                # Send chunk
                response_data = {
                    "session_id": session_id,
                    "request_id": request_id,
                    "response": chunk,
                    "is_complete": False,
                    "metrics": {
                        "tokens_generated": token_count
                    }
                }
                
                encrypted_response = self.encryptor.encrypt(response_data)
                await channel.send(encrypted_response)
            
            # Send completion marker
            final_response = {
                "session_id": session_id,
                "request_id": request_id,
                "response": "",
                "is_complete": True,
                "metrics": {
                    "total_tokens": token_count,
                    "full_response": "".join(response_chunks)
                }
            }
            
            encrypted_final = self.encryptor.encrypt(final_response)
            await channel.send(encrypted_final)
            
        except Exception as e:
            logger.error(f"Error in streaming inference: {e}")
            await self._send_error_response(channel, request_data, str(e))
    
    async def _batch_inference(self, channel: discord.TextChannel, request_data: Dict, model: LlamaCppWrapper):
        """Perform batch inference."""
        session_id = request_data["session_id"]
        request_id = request_data["request_id"]
        
        try:
            response_text = await model.generate(
                prompt=request_data["prompt"],
                temperature=request_data.get("temperature", 0.7),
                max_tokens=request_data.get("max_tokens", 2048)
            )
            
            response_data = {
                "session_id": session_id,
                "request_id": request_id,
                "response": response_text,
                "is_complete": True,
                "metrics": {
                    "total_tokens": len(response_text.split()),
                    "inference_time_ms": 0  # TODO: Track actual time
                }
            }
            
            encrypted_response = self.encryptor.encrypt(response_data)
            await channel.send(encrypted_response)
            
        except Exception as e:
            logger.error(f"Error in batch inference: {e}")
            await self._send_error_response(channel, request_data, str(e))
    
    async def _send_error_response(self, channel: discord.TextChannel, request_data: Dict, error_message: str):
        """Send error response."""
        try:
            error_response = {
                "session_id": request_data.get("session_id", "unknown"),
                "request_id": request_data.get("request_id", "unknown"),
                "error_type": "inference_error",
                "error_message": error_message,
                "is_complete": True
            }
            
            encrypted_error = self.encryptor.encrypt(error_response)
            await channel.send(encrypted_error)
            
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")
    
    @tasks.loop(seconds=30)
    async def health_reporter(self):
        """Report health metrics to server bot."""
        try:
            if not self.metrics_channel:
                return
            
            metrics = self.system_monitor.get_system_metrics()
            metrics.update({
                "type": "health_check",
                "status": "healthy",
                "inference_count": self.inference_count,
                "error_count": self.error_count,
                "avg_inference_time": (
                    self.total_inference_time / self.inference_count 
                    if self.inference_count > 0 else 0
                ),
                "models_loaded": list(self.model_manager.models.keys())
            })
            
            encrypted_metrics = self.encryptor.encrypt(metrics)
            await self.metrics_channel.send(encrypted_metrics)
            
        except Exception as e:
            logger.error(f"Error reporting health metrics: {e}")
    
    @tasks.loop(minutes=5)
    async def performance_monitor(self):
        """Monitor performance and log issues."""
        try:
            metrics = self.system_monitor.get_system_metrics()
            
            # Check for performance issues
            if metrics.get("cpu_usage_percent", 0) > 90:
                logger.warning(f"High CPU usage: {metrics['cpu_usage_percent']:.1f}%")
            
            if metrics.get("memory_usage_percent", 0) > 90:
                logger.warning(f"High memory usage: {metrics['memory_usage_percent']:.1f}%")
            
            # Check battery level
            battery_percent = metrics.get("battery_percent")
            if battery_percent and battery_percent < 20:
                logger.warning(f"Low battery: {battery_percent}%")
            
        except Exception as e:
            logger.error(f"Error in performance monitor: {e}")

# Global bot instance
bot = MeatLizardClientBot()

def run_client_bot():
    """Run the client bot."""
    token = os.getenv("DISCORD_CLIENT_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_CLIENT_BOT_TOKEN not found in environment")
        return
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to run client bot: {e}")

if __name__ == "__main__":
    run_client_bot()