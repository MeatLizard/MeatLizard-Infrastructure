"""
Shared utility functions for the AI Chat Discord System.
Common helper functions used across all components.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable, TypeVar, Awaitable
from uuid import UUID
import json
import hashlib
import secrets
from functools import wraps

T = TypeVar('T')


def setup_logging(level: str = "INFO", format_string: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string
        
    Returns:
        Configured logger instance
    """
    if format_string is None:
        format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    return logging.getLogger(__name__)


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def format_timestamp(dt: datetime) -> str:
    """Format datetime as ISO string."""
    return dt.isoformat()


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO timestamp string to datetime."""
    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))


def generate_session_id() -> str:
    """Generate a unique session identifier."""
    return secrets.token_urlsafe(32)


def generate_request_id() -> str:
    """Generate a unique request identifier."""
    return secrets.token_urlsafe(16)


def hash_string(text: str, algorithm: str = "sha256") -> str:
    """
    Hash a string using the specified algorithm.
    
    Args:
        text: String to hash
        algorithm: Hash algorithm (sha256, sha512, md5)
        
    Returns:
        Hexadecimal hash string
    """
    hasher = hashlib.new(algorithm)
    hasher.update(text.encode('utf-8'))
    return hasher.hexdigest()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe storage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Limit length and remove leading/trailing spaces
    filename = filename.strip()[:255]
    
    # Ensure it's not empty
    if not filename:
        filename = f"file_{int(time.time())}"
    
    return filename


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """
    Safely parse JSON string with default fallback.
    
    Args:
        json_str: JSON string to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """
    Safely serialize object to JSON with default fallback.
    
    Args:
        obj: Object to serialize
        default: Default JSON string if serialization fails
        
    Returns:
        JSON string or default value
    """
    try:
        return json.dumps(obj, default=str, separators=(',', ':'))
    except (TypeError, ValueError):
        return default


def retry_async(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch and retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    return decorator


def validate_uuid(uuid_string: str) -> bool:
    """
    Validate UUID string format.
    
    Args:
        uuid_string: UUID string to validate
        
    Returns:
        True if valid UUID format
    """
    try:
        UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False


def format_bytes(bytes_count: int) -> str:
    """
    Format byte count as human-readable string.
    
    Args:
        bytes_count: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} PB"


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds as human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2h 30m 15s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes}m {seconds:.0f}s"
    
    hours = minutes // 60
    minutes = minutes % 60
    
    if hours < 24:
        return f"{hours}h {minutes}m"
    
    days = hours // 24
    hours = hours % 24
    
    return f"{days}d {hours}h"


def chunk_list(lst: list, chunk_size: int) -> list:
    """
    Split list into chunks of specified size.
    
    Args:
        lst: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed for identifier.
        
        Args:
            identifier: Unique identifier (user ID, IP, etc.)
            
        Returns:
            True if request is allowed
        """
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > window_start
            ]
        else:
            self.requests[identifier] = []
        
        # Check if under limit
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(now)
            return True
        
        return False
    
    def get_reset_time(self, identifier: str) -> Optional[float]:
        """
        Get time when rate limit resets for identifier.
        
        Args:
            identifier: Unique identifier
            
        Returns:
            Unix timestamp when limit resets, or None if not limited
        """
        if identifier not in self.requests or not self.requests[identifier]:
            return None
        
        oldest_request = min(self.requests[identifier])
        return oldest_request + self.window_seconds