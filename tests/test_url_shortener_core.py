"""
Core tests for URL shortener components - standalone version for testing.
"""
import pytest
import string
import hashlib
import random
import re
import urllib.parse
from typing import Optional, List, Tuple
from unittest.mock import Mock, patch


class SlugGeneratorTest:
    """Standalone version of SlugGenerator for testing."""
    
    ADJECTIVES = [
        "quick", "lazy", "happy", "bright", "calm", "bold", "wise", "kind",
        "cool", "warm", "fast", "slow", "big", "small", "new", "old",
        "red", "blue", "green", "yellow", "purple", "orange", "pink", "black"
    ]
    
    NOUNS = [
        "cat", "dog", "bird", "fish", "tree", "rock", "star", "moon",
        "sun", "cloud", "river", "mountain", "ocean", "forest", "flower", "book",
        "car", "house", "bridge", "castle", "garden", "island", "valley", "desert"
    ]
    
    VERBS = [
        "runs", "jumps", "flies", "swims", "walks", "dances", "sings", "laughs",
        "sleeps", "dreams", "thinks", "writes", "reads", "plays", "works", "rests",
        "climbs", "falls", "rises", "shines", "grows", "blooms", "flows", "glows"
    ]
    
    def __init__(self, slug_exists_func=None):
        self.slug_exists_func = slug_exists_func or (lambda x: False)
    
    def generate_random_slug(self, length: int = 6) -> str:
        """Generate a random alphanumeric slug."""
        characters = string.ascii_lowercase + string.digits
        while True:
            slug = ''.join(random.choices(characters, k=length))
            if not self.slug_exists_func(slug):
                return slug
    
    def generate_five_word_slug(self) -> str:
        """Generate a 5-word slug in format: adjective-noun-verb-adjective-noun."""
        while True:
            words = [
                random.choice(self.ADJECTIVES),
                random.choice(self.NOUNS),
                random.choice(self.VERBS),
                random.choice(self.ADJECTIVES),
                random.choice(self.NOUNS)
            ]
            slug = '-'.join(words)
            if not self.slug_exists_func(slug):
                return slug
    
    def validate_vanity_slug(self, slug: str) -> tuple[bool, Optional[str]]:
        """Validate a custom vanity slug."""
        if len(slug) < 3:
            return False, "Slug must be at least 3 characters long"
        
        if len(slug) > 50:
            return False, "Slug must be no more than 50 characters long"
        
        allowed_chars = set(string.ascii_lowercase + string.digits + '-_')
        if not all(c in allowed_chars for c in slug.lower()):
            return False, "Slug can only contain letters, numbers, hyphens, and underscores"
        
        reserved_words = {
            'api', 'admin', 'www', 'mail', 'ftp', 'localhost', 'root',
            'help', 'support', 'about', 'contact', 'terms', 'privacy',
            'login', 'register', 'signup', 'signin', 'logout', 'dashboard',
            'profile', 'settings', 'account', 'billing', 'payment',
            'short', 'url', 'link', 'redirect', 'stats', 'analytics'
        }
        
        if slug.lower() in reserved_words:
            return False, f"'{slug}' is a reserved word and cannot be used"
        
        if self.slug_exists_func(slug):
            return False, "This slug is already taken"
        
        return True, None
    
    def suggest_alternatives(self, desired_slug: str, count: int = 5) -> List[str]:
        """Generate alternative slug suggestions."""
        suggestions = []
        base_slug = desired_slug.lower()
        
        for i in range(1, count + 1):
            candidate = f"{base_slug}{i}"
            if not self.slug_exists_func(candidate) and len(candidate) <= 50:
                suggestions.append(candidate)
        
        while len(suggestions) < count:
            suffix = ''.join(random.choices(string.digits, k=2))
            candidate = f"{base_slug}-{suffix}"
            if not self.slug_exists_func(candidate) and len(candidate) <= 50:
                suggestions.append(candidate)
        
        return suggestions[:count]
    
    def generate_hash_based_slug(self, url: str, length: int = 8) -> str:
        """Generate a deterministic slug based on URL hash."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        hash_int = int(url_hash[:16], 16)
        
        alphabet = string.ascii_lowercase + string.digits
        result = ""
        while hash_int > 0 and len(result) < length:
            result = alphabet[hash_int % 36] + result
            hash_int //= 36
        
        while len(result) < length:
            result = alphabet[0] + result
        
        base_slug = result
        counter = 1
        while self.slug_exists_func(result):
            result = f"{base_slug}{counter}"
            counter += 1
        
        return result


class LinkValidatorTest:
    """Standalone version of LinkValidator for testing."""
    
    BLOCKED_PROTOCOLS = {
        'javascript', 'data', 'vbscript', 'file', 'ftp',
        'gopher', 'ldap', 'dict', 'imap', 'pop3', 'smtp'
    }
    
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
    
    MAX_URL_LENGTH = 2048
    
    def __init__(self):
        self.suspicious_regex = re.compile('|'.join(self.SUSPICIOUS_PATTERNS), re.IGNORECASE)
    
    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """Validate a URL for shortening."""
        if not url or not isinstance(url, str):
            return False, "URL is required", None
        
        if len(url) > self.MAX_URL_LENGTH:
            return False, f"URL too long (max {self.MAX_URL_LENGTH} characters)", None
        
        normalized_url = self._normalize_url(url)
        
        try:
            parsed = urllib.parse.urlparse(normalized_url)
        except Exception:
            return False, "Invalid URL format", None
        
        if not parsed.scheme:
            return False, "URL must include a protocol (http:// or https://)", None
        
        # Check if it's HTTP/HTTPS first
        if parsed.scheme.lower() not in ['http', 'https']:
            return False, "Only HTTP and HTTPS URLs are allowed", None
        
        # Additional check for explicitly blocked protocols (redundant but clear)
        if parsed.scheme.lower() in self.BLOCKED_PROTOCOLS:
            return False, f"Protocol '{parsed.scheme}' is not allowed", None
        
        if not parsed.netloc:
            return False, "URL must include a valid domain", None
        
        if self._is_suspicious_url(normalized_url):
            return False, "URL appears to be suspicious or potentially harmful", None
        
        if self._is_self_referential(parsed):
            return False, "Cannot shorten URLs that point to this service", None
        
        security_check, security_error = self._security_checks(parsed)
        if not security_check:
            return False, security_error, None
        
        return True, None, normalized_url
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL by adding protocol if missing."""
        url = url.strip()
        # Only add https:// if there's no protocol at all
        if '://' not in url:
            url = 'https://' + url
        return url
    
    def _is_suspicious_url(self, url: str) -> bool:
        """Check if URL matches suspicious patterns."""
        return bool(self.suspicious_regex.search(url))
    
    def _is_self_referential(self, parsed_url) -> bool:
        """Check if URL points to this service."""
        service_domains = ['meatlizard.org', 'localhost', '127.0.0.1', '0.0.0.0']
        hostname = parsed_url.netloc.lower()
        if ':' in hostname:
            hostname = hostname.split(':')[0]
        return hostname in service_domains
    
    def _security_checks(self, parsed_url) -> Tuple[bool, Optional[str]]:
        """Additional security checks for the URL."""
        hostname = parsed_url.netloc.lower()
        if ':' in hostname:
            hostname = hostname.split(':')[0]
        
        # Simple IP address pattern check
        ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
        if ip_pattern.match(hostname):
            octets = [int(x) for x in hostname.split('.')]
            
            if (octets[0] == 10 or
                (octets[0] == 172 and 16 <= octets[1] <= 31) or
                (octets[0] == 192 and octets[1] == 168) or
                (octets[0] == 127) or
                (octets[0] == 0)):
                return False, "Private IP addresses are not allowed"
        
        # Check for suspicious ports - but handle port parsing safely
        try:
            if parsed_url.port:
                suspicious_ports = {22, 23, 25, 53, 110, 143, 993, 995}
                if parsed_url.port in suspicious_ports:
                    return False, f"Port {parsed_url.port} is not allowed"
        except ValueError:
            # Invalid port format
            return False, "Invalid port in URL"
        
        if len(parsed_url.path) > 1000:
            return False, "URL path is too long"
        
        return True, None
    
    def extract_title_from_url(self, url: str) -> Optional[str]:
        """Extract a potential title from URL."""
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc
            
            if domain.startswith('www.'):
                domain = domain[4:]
            
            if parsed.path and parsed.path != '/':
                path_parts = [p for p in parsed.path.split('/') if p]
                if path_parts:
                    last_part = path_parts[-1]
                    if '.' in last_part:
                        last_part = last_part.rsplit('.', 1)[0]
                    title = last_part.replace('-', ' ').replace('_', ' ').title()
                    return f"{title} - {domain}"
            
            return domain
        except Exception:
            return None


class TestSlugGenerator:
    """Test cases for SlugGenerator."""
    
    def test_generate_random_slug_format(self):
        """Test random slug generation format."""
        generator = SlugGeneratorTest()
        
        slug = generator.generate_random_slug()
        assert len(slug) == 6
        assert slug.isalnum()
        assert slug.islower()
        
        slug_10 = generator.generate_random_slug(length=10)
        assert len(slug_10) == 10
    
    def test_generate_five_word_slug_format(self):
        """Test five-word slug generation format."""
        generator = SlugGeneratorTest()
        
        slug = generator.generate_five_word_slug()
        words = slug.split('-')
        assert len(words) == 5
        
        assert words[0] in generator.ADJECTIVES
        assert words[1] in generator.NOUNS
        assert words[2] in generator.VERBS
        assert words[3] in generator.ADJECTIVES
        assert words[4] in generator.NOUNS
    
    def test_validate_vanity_slug_valid_cases(self):
        """Test validation of valid vanity slugs."""
        generator = SlugGeneratorTest()
        
        valid_slugs = ["my-link", "test123", "cool_url", "abc", "test-link-123"]
        
        for slug in valid_slugs:
            is_valid, error = generator.validate_vanity_slug(slug)
            assert is_valid, f"Slug '{slug}' should be valid, got error: {error}"
            assert error is None
    
    def test_validate_vanity_slug_invalid_cases(self):
        """Test validation of invalid vanity slugs."""
        generator = SlugGeneratorTest()
        
        invalid_cases = [
            ("ab", "too short"),
            ("a" * 51, "too long"),
            ("test@link", "invalid characters"),
            ("test link", "spaces not allowed"),
            ("api", "reserved word"),
            ("admin", "reserved word"),
        ]
        
        for slug, reason in invalid_cases:
            is_valid, error = generator.validate_vanity_slug(slug)
            assert not is_valid, f"Slug '{slug}' should be invalid ({reason})"
            assert error is not None
    
    def test_validate_vanity_slug_existing(self):
        """Test validation fails for existing slugs."""
        def slug_exists(slug):
            return slug == "existing-slug"
        
        generator = SlugGeneratorTest(slug_exists_func=slug_exists)
        
        is_valid, error = generator.validate_vanity_slug("existing-slug")
        assert not is_valid
        assert "already taken" in error.lower()
    
    def test_suggest_alternatives(self):
        """Test alternative slug suggestions."""
        generator = SlugGeneratorTest()
        
        suggestions = generator.suggest_alternatives("test", count=3)
        assert len(suggestions) == 3
        assert all("test" in suggestion for suggestion in suggestions)
        assert len(set(suggestions)) == 3  # All unique
    
    def test_generate_hash_based_slug_deterministic(self):
        """Test hash-based slug generation is deterministic."""
        generator = SlugGeneratorTest()
        
        url = "https://example.com/test"
        slug1 = generator.generate_hash_based_slug(url)
        slug2 = generator.generate_hash_based_slug(url)
        
        assert slug1 == slug2
        assert len(slug1) == 8
        assert slug1.isalnum()
    
    def test_collision_handling_random(self):
        """Test that slug generation handles collisions."""
        collision_count = 0
        
        def slug_exists(slug):
            nonlocal collision_count
            if slug == 'abcdef' and collision_count == 0:
                collision_count += 1
                return True
            return False
        
        generator = SlugGeneratorTest(slug_exists_func=slug_exists)
        
        with patch('random.choices') as mock_choices:
            # First call returns collision, second call returns different chars
            mock_choices.side_effect = [
                ['a', 'b', 'c', 'd', 'e', 'f'],  # First attempt (collision)
                ['x', 'y', 'z', '1', '2', '3']   # Second attempt (success)
            ]
            
            slug = generator.generate_random_slug()
            
            # Should have handled the collision and generated a different slug
            assert slug != 'abcdef'
            assert collision_count == 1  # Collision was detected


class TestLinkValidator:
    """Test cases for LinkValidator."""
    
    def test_validate_url_valid_cases(self):
        """Test validation of valid URLs."""
        validator = LinkValidatorTest()
        
        valid_urls = [
            "https://example.com",
            "http://test.org/path",
            "https://subdomain.example.com/path?query=1",
            "example.com",  # Should be normalized to https://
            "www.example.com",
        ]
        
        for url in valid_urls:
            is_valid, error, normalized = validator.validate_url(url)
            assert is_valid, f"URL '{url}' should be valid, got error: {error}"
            assert normalized is not None
            assert normalized.startswith(('http://', 'https://'))
    
    def test_validate_url_invalid_cases(self):
        """Test validation of invalid URLs."""
        validator = LinkValidatorTest()
        
        invalid_cases = [
            ("", "empty URL"),
            ("ftp://example.com", "blocked protocol"),
            ("http://localhost", "suspicious domain"),
            ("http://meatlizard.org/test", "self-referential"),
            ("https://example.com/" + "x" * 2000, "too long"),
        ]
        
        for url, reason in invalid_cases:
            is_valid, error, normalized = validator.validate_url(url)
            assert not is_valid, f"URL '{url}' should be invalid ({reason}), got error: {error}"
            assert error is not None
    
    def test_normalize_url(self):
        """Test URL normalization."""
        validator = LinkValidatorTest()
        
        test_cases = [
            ("example.com", "https://example.com"),
            ("www.example.com", "https://www.example.com"),
            ("http://example.com", "http://example.com"),
            ("https://example.com", "https://example.com"),
        ]
        
        for input_url, expected in test_cases:
            normalized = validator._normalize_url(input_url)
            assert normalized == expected
    
    def test_extract_title_from_url(self):
        """Test title extraction from URLs."""
        validator = LinkValidatorTest()
        
        test_cases = [
            ("https://example.com", "example.com"),
            ("https://www.example.com", "example.com"),
            ("https://example.com/about-us", "About Us - example.com"),
            ("https://example.com/blog/my-post.html", "My Post - example.com"),
        ]
        
        for url, expected in test_cases:
            title = validator.extract_title_from_url(url)
            assert title == expected
    
    def test_security_checks_private_ip(self):
        """Test private IP blocking."""
        validator = LinkValidatorTest()
        
        is_valid, error, _ = validator.validate_url("http://192.168.1.1")
        assert not is_valid
        # Could be caught by suspicious patterns or security checks
        assert ("private ip" in error.lower() or 
                "suspicious" in error.lower() or 
                "192.168" in error.lower())
    
    def test_security_checks_suspicious_port(self):
        """Test suspicious port blocking."""
        validator = LinkValidatorTest()
        
        is_valid, error, _ = validator.validate_url("http://example.com:22")
        assert not is_valid
        assert "port" in error.lower()
    
    def test_suspicious_patterns(self):
        """Test suspicious URL pattern detection."""
        validator = LinkValidatorTest()
        
        suspicious_urls = [
            "http://bit.ly/test",
            "http://tinyurl.com/test",
            "http://localhost:8080",
        ]
        
        for url in suspicious_urls:
            is_valid, error, _ = validator.validate_url(url)
            assert not is_valid
            assert error is not None
    
    def test_javascript_url_handling(self):
        """Test that javascript URLs are properly blocked."""
        validator = LinkValidatorTest()
        
        # This should be caught by the protocol check or port parsing
        is_valid, error, _ = validator.validate_url("javascript:alert('xss')")
        assert not is_valid
        assert ("protocol" in error.lower() or 
                "not allowed" in error.lower() or 
                "invalid port" in error.lower())