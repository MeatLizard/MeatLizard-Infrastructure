"""
Slug generation service for URL shortener.
Supports random, vanity, and 5-word slug generation.
"""
import random
import string
import hashlib
from typing import Optional, List
from sqlalchemy.orm import Session
# Import will be handled by the service that uses this class


class SlugGenerator:
    """Generates unique slugs for shortened URLs."""
    
    # Five-word generator word lists
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
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def generate_random_slug(self, length: int = 6) -> str:
        """Generate a random alphanumeric slug."""
        characters = string.ascii_lowercase + string.digits
        while True:
            slug = ''.join(random.choices(characters, k=length))
            if not self._slug_exists(slug):
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
            if not self._slug_exists(slug):
                return slug
    
    def validate_vanity_slug(self, slug: str) -> tuple[bool, Optional[str]]:
        """
        Validate a custom vanity slug.
        Returns (is_valid, error_message).
        """
        # Check length
        if len(slug) < 3:
            return False, "Slug must be at least 3 characters long"
        
        if len(slug) > 50:
            return False, "Slug must be no more than 50 characters long"
        
        # Check allowed characters (alphanumeric, hyphens, underscores)
        allowed_chars = set(string.ascii_lowercase + string.digits + '-_')
        if not all(c in allowed_chars for c in slug.lower()):
            return False, "Slug can only contain letters, numbers, hyphens, and underscores"
        
        # Check for reserved words
        reserved_words = {
            'api', 'admin', 'www', 'mail', 'ftp', 'localhost', 'root',
            'help', 'support', 'about', 'contact', 'terms', 'privacy',
            'login', 'register', 'signup', 'signin', 'logout', 'dashboard',
            'profile', 'settings', 'account', 'billing', 'payment',
            'short', 'url', 'link', 'redirect', 'stats', 'analytics'
        }
        
        if slug.lower() in reserved_words:
            return False, f"'{slug}' is a reserved word and cannot be used"
        
        # Check if slug already exists
        if self._slug_exists(slug):
            return False, "This slug is already taken"
        
        return True, None
    
    def suggest_alternatives(self, desired_slug: str, count: int = 5) -> List[str]:
        """Generate alternative slug suggestions based on desired slug."""
        suggestions = []
        base_slug = desired_slug.lower()
        
        # Try with numbers
        for i in range(1, count + 1):
            candidate = f"{base_slug}{i}"
            if not self._slug_exists(candidate) and len(candidate) <= 50:
                suggestions.append(candidate)
        
        # Try with random suffixes
        while len(suggestions) < count:
            suffix = ''.join(random.choices(string.digits, k=2))
            candidate = f"{base_slug}-{suffix}"
            if not self._slug_exists(candidate) and len(candidate) <= 50:
                suggestions.append(candidate)
        
        return suggestions[:count]
    
    def generate_hash_based_slug(self, url: str, length: int = 8) -> str:
        """Generate a deterministic slug based on URL hash."""
        # Create hash of URL
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        # Convert to base36 (alphanumeric)
        hash_int = int(url_hash[:16], 16)  # Use first 16 chars of hash
        
        # Convert to base36
        alphabet = string.ascii_lowercase + string.digits
        result = ""
        while hash_int > 0 and len(result) < length:
            result = alphabet[hash_int % 36] + result
            hash_int //= 36
        
        # Pad if necessary
        while len(result) < length:
            result = alphabet[0] + result
        
        # Check if exists, if so add random suffix
        base_slug = result
        counter = 1
        while self._slug_exists(result):
            result = f"{base_slug}{counter}"
            counter += 1
        
        return result
    
    def _slug_exists(self, slug: str) -> bool:
        """Check if a slug already exists in the database."""
        # Import here to avoid circular imports
        from ..models import ShortUrl
        return self.db.query(ShortUrl).filter(ShortUrl.slug == slug).first() is not None