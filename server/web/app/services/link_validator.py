"""
URL validation service for the URL shortener.
Provides validation and anti-open-redirect protection.
"""
import re
import urllib.parse
from typing import Optional, Tuple
from urllib.parse import urlparse


class LinkValidator:
    """Validates URLs and provides security checks."""
    
    # Dangerous protocols that should be blocked
    BLOCKED_PROTOCOLS = {
        'javascript', 'data', 'vbscript', 'file', 'ftp',
        'gopher', 'ldap', 'dict', 'imap', 'pop3', 'smtp'
    }
    
    # Suspicious domains/patterns
    SUSPICIOUS_PATTERNS = [
        r'bit\.ly',
        r'tinyurl\.com',
        r'short\.link',
        r'localhost',
        r'127\.0\.0\.1',
        r'0\.0\.0\.0',
        r'192\.168\.',
        r'10\.',
        r'172\.(1[6-9]|2[0-9]|3[01])\.',
    ]
    
    # Maximum URL length
    MAX_URL_LENGTH = 2048
    
    def __init__(self):
        self.suspicious_regex = re.compile('|'.join(self.SUSPICIOUS_PATTERNS), re.IGNORECASE)
    
    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate a URL for shortening.
        Returns (is_valid, error_message, normalized_url).
        """
        if not url or not isinstance(url, str):
            return False, "URL is required", None
        
        # Check length
        if len(url) > self.MAX_URL_LENGTH:
            return False, f"URL too long (max {self.MAX_URL_LENGTH} characters)", None
        
        # Normalize URL (add protocol if missing)
        normalized_url = self._normalize_url(url)
        
        # Parse URL
        try:
            parsed = urlparse(normalized_url)
        except Exception:
            return False, "Invalid URL format", None
        
        # Check for valid scheme
        if not parsed.scheme:
            return False, "URL must include a protocol (http:// or https://)", None
        
        if parsed.scheme.lower() not in ['http', 'https']:
            return False, "Only HTTP and HTTPS URLs are allowed", None
        
        # Check for blocked protocols
        if parsed.scheme.lower() in self.BLOCKED_PROTOCOLS:
            return False, f"Protocol '{parsed.scheme}' is not allowed", None
        
        # Check for valid hostname
        if not parsed.netloc:
            return False, "URL must include a valid domain", None
        
        # Check for suspicious patterns
        if self._is_suspicious_url(normalized_url):
            return False, "URL appears to be suspicious or potentially harmful", None
        
        # Check for self-referential URLs (prevent loops)
        if self._is_self_referential(parsed):
            return False, "Cannot shorten URLs that point to this service", None
        
        # Additional security checks
        security_check, security_error = self._security_checks(parsed)
        if not security_check:
            return False, security_error, None
        
        return True, None, normalized_url
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL by adding protocol if missing."""
        url = url.strip()
        
        # Only add https:// if there's no protocol at all
        if '://' not in url:
            # Default to https for security
            url = 'https://' + url
        
        return url
    
    def _is_suspicious_url(self, url: str) -> bool:
        """Check if URL matches suspicious patterns."""
        return bool(self.suspicious_regex.search(url))
    
    def _is_self_referential(self, parsed_url) -> bool:
        """Check if URL points to this service (prevent loops)."""
        # List of domains this service runs on
        service_domains = [
            'meatlizard.org',
            'localhost',
            '127.0.0.1',
            '0.0.0.0'
        ]
        
        hostname = parsed_url.netloc.lower()
        # Remove port if present
        if ':' in hostname:
            hostname = hostname.split(':')[0]
        
        return hostname in service_domains
    
    def _security_checks(self, parsed_url) -> Tuple[bool, Optional[str]]:
        """Additional security checks for the URL."""
        
        # Check for IP addresses (potential bypass attempts)
        hostname = parsed_url.netloc.lower()
        if ':' in hostname:
            hostname = hostname.split(':')[0]
        
        # Simple IP address pattern check
        ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        if ip_pattern.match(hostname):
            # Allow public IPs but block private ranges
            octets = [int(x) for x in hostname.split('.')]
            
            # Private IP ranges
            if (octets[0] == 10 or
                (octets[0] == 172 and 16 <= octets[1] <= 31) or
                (octets[0] == 192 and octets[1] == 168) or
                (octets[0] == 127) or
                (octets[0] == 0)):
                return False, "Private IP addresses are not allowed"
        
        # Check for suspicious ports
        if parsed_url.port:
            suspicious_ports = {22, 23, 25, 53, 110, 143, 993, 995}
            if parsed_url.port in suspicious_ports:
                return False, f"Port {parsed_url.port} is not allowed"
        
        # Check for excessively long paths (potential attack)
        if len(parsed_url.path) > 1000:
            return False, "URL path is too long"
        
        return True, None
    
    def extract_title_from_url(self, url: str) -> Optional[str]:
        """Extract a potential title from URL for display purposes."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # If there's a path, use the last segment
            if parsed.path and parsed.path != '/':
                path_parts = [p for p in parsed.path.split('/') if p]
                if path_parts:
                    last_part = path_parts[-1]
                    # Remove file extension
                    if '.' in last_part:
                        last_part = last_part.rsplit('.', 1)[0]
                    # Replace hyphens/underscores with spaces and title case
                    title = last_part.replace('-', ' ').replace('_', ' ').title()
                    return f"{title} - {domain}"
            
            return domain
        except Exception:
            return None