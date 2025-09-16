
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from server.web.app.models import User, Content, ContentTypeEnum

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_profile(self, user_id: str):
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(joinedload(User.content))
        )
        user = result.unique().scalar_one_or_none()

        if not user:
            return None

        content_by_type = {
            ContentTypeEnum.url: [],
            ContentTypeEnum.paste: [],
            ContentTypeEnum.media: [],
            ContentTypeEnum.aichat: [],
        }
        for item in user.content:
            content_by_type[item.content_type].append(item)

        return {
            "user": user,
            "stats": {
                "reputation": user.reputation_score,
                "xp": user.experience_points,
            },
            "content": content_by_type
        }
