
import random
import string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from server.web.app.models import URLShortener, User

class URLShortenerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_short_url(self, target_url: str, user: User, custom_slug: str = None) -> URLShortener:
        if custom_slug:
            if not await self._is_slug_available(custom_slug):
                raise ValueError("Custom slug is already in use.")
            slug = custom_slug
        else:
            slug = await self._generate_unique_slug()

        short_url = URLShortener(
            target_url=target_url,
            slug=slug,
            user_id=user.id
        )
        self.db.add(short_url)
        await self.db.commit()
        return short_url

    async def _generate_unique_slug(self, length: int = 6) -> str:
        while True:
            slug = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
            if await self._is_slug_available(slug):
                return slug

    async def _is_slug_available(self, slug: str) -> bool:
        result = await self.db.execute(select(URLShortener).where(URLShortener.slug == slug))
        return result.scalar_one_or_none() is None

    async def get_url_by_slug(self, slug: str) -> URLShortener:
        result = await self.db.execute(select(URLShortener).where(URLShortener.slug == slug))
        return result.scalar_one_or_none()

    def is_valid_url(self, url: str) -> bool:
        # Basic URL validation. In a real app, you'd want a more robust check.
        return url.startswith("http://") or url.startswith("https://")
