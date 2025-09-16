
from fastapi import Request, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from starlette.status import HTTP_403_FORBIDDEN, HTTP_401_UNAUTHORIZED
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from server.web.app.db import get_db
from server.web.app.models import User, UserTier
from shared_lib.tier_manager import tier_manager
from shared_lib.security import decode_access_token
from datetime import datetime

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def PermissionChecker(permission: str):
    async def dependency(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
        # Get the user's current tier from the database
        query = select(UserTier).where(
            UserTier.user_id == user.id,
            UserTier.start_date <= datetime.utcnow(),
            (UserTier.end_date == None) | (UserTier.end_date >= datetime.utcnow())
        ).order_by(UserTier.start_date.desc())
        result = await db.execute(query)
        user_tier_record = result.scalars().first()

        if not user_tier_record:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="User tier not found."
            )

        has_permission = tier_manager.get_permission(user_tier_record.tier, permission)
        if not has_permission:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action."
            )
    return dependency
