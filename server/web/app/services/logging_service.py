"""
Logging Service for Video Platform
Provides structured logging with JSON format, correlation IDs, and integration with log aggregation systems.
"""

import json
import logging
import logging.config
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
from pathlib import Path

# Context variables for request correlation
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar('session_id', default=None)

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Base log data
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName,
        }
        
        # Add context variables if available
        if request_id_var.get():
            log_data['request_id'] = request_id_var.get()
        
        if user_id_var.get():
            log_data['user_id'] = user_id_var.get()
        
        if session_id_var.get():
            log_data['session_id'] = session_id_var.get()
        
        # Add exception information if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                extra_fields[key] = value
        
        if extra_fields:
            log_data['extra'] = extra_fields
        
        return json.dumps(log_data, default=str, ensure_ascii=False)

class VideoLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for video platform specific logging"""
    
    def __init__(self, logger: logging.Logger, extra: Dict[str, Any] = None):
        super().__init__(logger, extra or {})
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message and add extra context"""
        extra = kwargs.get('extra', {})
        
        # Add default extra fields
        if self.extra:
            extra.update(self.extra)
        
        # Add context from ContextVars
        if request_id_var.get():
            extra['request_id'] = request_id_var.get()
        
        if user_id_var.get():
            extra['user_id'] = user_id_var.get()
        
        if session_id_var.get():
            extra['session_id'] = session_id_var.get()
        
        kwargs['extra'] = extra
        return msg, kwargs
    
    def log_video_event(self, level: int, event_type: str, video_id: str = None, 
                       message: str = "", **kwargs):
        """Log video-specific events"""
        extra = {
            'event_type': event_type,
            'video_id': video_id,
            **kwargs
        }
        self.log(level, message, extra=extra)
    
    def log_transcoding_event(self, level: int, job_id: str, video_id: str, 
                             quality: str, status: str, message: str = "", **kwargs):
        """Log transcoding-specific events"""
        extra = {
            'event_type': 'transcoding',
            'job_id': job_id,
            'video_id': video_id,
            'quality': quality,
            'status': status,
            **kwargs
        }
        self.log(level, message, extra=extra)
    
    def log_import_event(self, level: int, import_id: str, source_url: str, 
                        platform: str, status: str, message: str = "", **kwargs):
        """Log import-specific events"""
        extra = {
            'event_type': 'import',
            'import_id': import_id,
            'source_url': source_url,
            'platform': platform,
            'status': status,
            **kwargs
        }
        self.log(level, message, extra=extra)
    
    def log_api_request(self, method: str, endpoint: str, status_code: int, 
                       duration_ms: float, user_id: str = None, **kwargs):
        """Log API request events"""
        extra = {
            'event_type': 'api_request',
            'method': method,
            'endpoint': endpoint,
            'status_code': status_code,
            'duration_ms': duration_ms,
            'user_id': user_id,
            **kwargs
        }
        self.info(f"{method} {endpoint} - {status_code} ({duration_ms}ms)", extra=extra)

class LoggingService:
    """Service for managing application logging"""
    
    def __init__(self):
        self.loggers: Dict[str, VideoLoggerAdapter] = {}
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        # Create logs directory
        log_dir = Path("/app/logs")
        log_dir.mkdir(exist_ok=True)
        
        # Logging configuration
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'json': {
                    '()': JSONFormatter,
                },
                'simple': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'INFO',
                    'formatter': 'json',
                    'stream': sys.stdout
                },
                'file_all': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'DEBUG',
                    'formatter': 'json',
                    'filename': str(log_dir / 'application.log'),
                    'maxBytes': 100 * 1024 * 1024,  # 100MB
                    'backupCount': 10
                },
                'file_error': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'ERROR',
                    'formatter': 'json',
                    'filename': str(log_dir / 'error.log'),
                    'maxBytes': 50 * 1024 * 1024,  # 50MB
                    'backupCount': 5
                },
                'file_transcoding': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'INFO',
                    'formatter': 'json',
                    'filename': str(log_dir / 'transcoding.log'),
                    'maxBytes': 50 * 1024 * 1024,  # 50MB
                    'backupCount': 5
                },
                'file_import': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'INFO',
                    'formatter': 'json',
                    'filename': str(log_dir / 'import.log'),
                    'maxBytes': 50 * 1024 * 1024,  # 50MB
                    'backupCount': 5
                },
                'file_api': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'INFO',
                    'formatter': 'json',
                    'filename': str(log_dir / 'api.log'),
                    'maxBytes': 100 * 1024 * 1024,  # 100MB
                    'backupCount': 10
                }
            },
            'loggers': {
                'video_platform': {
                    'level': 'DEBUG',
                    'handlers': ['console', 'file_all', 'file_error'],
                    'propagate': False
                },
                'video_platform.transcoding': {
                    'level': 'INFO',
                    'handlers': ['console', 'file_transcoding', 'file_error'],
                    'propagate': False
                },
                'video_platform.import': {
                    'level': 'INFO',
                    'handlers': ['console', 'file_import', 'file_error'],
                    'propagate': False
                },
                'video_platform.api': {
                    'level': 'INFO',
                    'handlers': ['console', 'file_api', 'file_error'],
                    'propagate': False
                },
                'uvicorn': {
                    'level': 'INFO',
                    'handlers': ['console', 'file_all'],
                    'propagate': False
                },
                'sqlalchemy': {
                    'level': 'WARNING',
                    'handlers': ['console', 'file_all'],
                    'propagate': False
                }
            },
            'root': {
                'level': 'INFO',
                'handlers': ['console', 'file_all']
            }
        }
        
        logging.config.dictConfig(config)
    
    def get_logger(self, name: str, extra: Dict[str, Any] = None) -> VideoLoggerAdapter:
        """Get or create a logger with the given name"""
        if name not in self.loggers:
            base_logger = logging.getLogger(f"video_platform.{name}")
            self.loggers[name] = VideoLoggerAdapter(base_logger, extra)
        
        return self.loggers[name]
    
    def set_request_context(self, request_id: str, user_id: str = None, session_id: str = None):
        """Set request context for logging"""
        request_id_var.set(request_id)
        if user_id:
            user_id_var.set(user_id)
        if session_id:
            session_id_var.set(session_id)
    
    def clear_request_context(self):
        """Clear request context"""
        request_id_var.set(None)
        user_id_var.set(None)
        session_id_var.set(None)

# Global logging service instance
logging_service = LoggingService()

# Convenience functions for getting loggers
def get_logger(name: str, extra: Dict[str, Any] = None) -> VideoLoggerAdapter:
    """Get a logger for the given component"""
    return logging_service.get_logger(name, extra)

def get_api_logger() -> VideoLoggerAdapter:
    """Get API logger"""
    return logging_service.get_logger("api")

def get_transcoding_logger() -> VideoLoggerAdapter:
    """Get transcoding logger"""
    return logging_service.get_logger("transcoding")

def get_import_logger() -> VideoLoggerAdapter:
    """Get import logger"""
    return logging_service.get_logger("import")

def get_video_logger() -> VideoLoggerAdapter:
    """Get video logger"""
    return logging_service.get_logger("video")

# Middleware for request logging
class LoggingMiddleware:
    """Middleware for request/response logging"""
    
    def __init__(self, app):
        self.app = app
        self.logger = get_api_logger()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Set request context
        logging_service.set_request_context(request_id)
        
        # Add request_id to scope for access in endpoints
        scope["request_id"] = request_id
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                # Log the request
                self.logger.log_api_request(
                    method=scope["method"],
                    endpoint=scope["path"],
                    status_code=message["status"],
                    duration_ms=duration_ms,
                    request_id=request_id
                )
            
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Clear request context
            logging_service.clear_request_context()

# Utility functions for structured logging
def log_video_upload_started(video_id: str, filename: str, file_size: int, user_id: str = None):
    """Log video upload start event"""
    logger = get_video_logger()
    logger.log_video_event(
        logging.INFO, 
        "upload_started", 
        video_id=video_id,
        message=f"Video upload started: {filename}",
        filename=filename,
        file_size=file_size,
        user_id=user_id
    )

def log_video_upload_completed(video_id: str, filename: str, duration_seconds: float):
    """Log video upload completion event"""
    logger = get_video_logger()
    logger.log_video_event(
        logging.INFO,
        "upload_completed",
        video_id=video_id,
        message=f"Video upload completed: {filename}",
        filename=filename,
        duration_seconds=duration_seconds
    )

def log_transcoding_started(job_id: str, video_id: str, quality: str, input_file: str):
    """Log transcoding start event"""
    logger = get_transcoding_logger()
    logger.log_transcoding_event(
        logging.INFO,
        job_id=job_id,
        video_id=video_id,
        quality=quality,
        status="started",
        message=f"Transcoding started for {quality}",
        input_file=input_file
    )

def log_transcoding_completed(job_id: str, video_id: str, quality: str, 
                            output_file: str, duration_seconds: float):
    """Log transcoding completion event"""
    logger = get_transcoding_logger()
    logger.log_transcoding_event(
        logging.INFO,
        job_id=job_id,
        video_id=video_id,
        quality=quality,
        status="completed",
        message=f"Transcoding completed for {quality}",
        output_file=output_file,
        duration_seconds=duration_seconds
    )

def log_transcoding_failed(job_id: str, video_id: str, quality: str, error: str):
    """Log transcoding failure event"""
    logger = get_transcoding_logger()
    logger.log_transcoding_event(
        logging.ERROR,
        job_id=job_id,
        video_id=video_id,
        quality=quality,
        status="failed",
        message=f"Transcoding failed for {quality}: {error}",
        error=error
    )

def log_import_started(import_id: str, source_url: str, platform: str):
    """Log import start event"""
    logger = get_import_logger()
    logger.log_import_event(
        logging.INFO,
        import_id=import_id,
        source_url=source_url,
        platform=platform,
        status="started",
        message=f"Import started from {platform}"
    )

def log_import_completed(import_id: str, source_url: str, platform: str, 
                        video_id: str, duration_seconds: float):
    """Log import completion event"""
    logger = get_import_logger()
    logger.log_import_event(
        logging.INFO,
        import_id=import_id,
        source_url=source_url,
        platform=platform,
        status="completed",
        message=f"Import completed from {platform}",
        video_id=video_id,
        duration_seconds=duration_seconds
    )

def log_import_failed(import_id: str, source_url: str, platform: str, error: str):
    """Log import failure event"""
    logger = get_import_logger()
    logger.log_import_event(
        logging.ERROR,
        import_id=import_id,
        source_url=source_url,
        platform=platform,
        status="failed",
        message=f"Import failed from {platform}: {error}",
        error=error
    )