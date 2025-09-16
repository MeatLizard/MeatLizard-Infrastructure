
from sqlalchemy.ext.asyncio import AsyncSession

from server.web.app.models import Content

class ModerationService:
    SPAM_KEYWORDS = ["spam", "viagra", "buy now", "free money"]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_content(self, content: Content):
        text_content = ""
        if hasattr(content, 'text'):
            text_content = content.text
        elif hasattr(content, 'content'):
            text_content = content.content

        is_spam = self._is_spam(text_content)
        is_malware = self._scan_for_malware(text_content)

        if is_spam or is_malware:
            content.is_moderated = True
            if is_spam:
                content.meta_data['is_spam'] = True
            if is_malware:
                content.meta_data['is_malware'] = True
            self.db.add(content)
            await self.db.commit()

    def _is_spam(self, text: str) -> bool:
        return any(keyword in text.lower() for keyword in self.SPAM_KEYWORDS)

    def _scan_for_malware(self, text: str) -> bool:
        # Simple malware check
        return "malware" in text.lower()

    async def takedown_content(self, content: Content):
        content.is_active = False
        self.db.add(content)
        await self.db.commit()
