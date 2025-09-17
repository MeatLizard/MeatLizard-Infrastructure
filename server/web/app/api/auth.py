"""
Authentication API endpoints for user registration and login.
"""
from datetime import datetime, timedelta
from typing import Optional
import uuid
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from server.web.app.dependencies import get_db
from server.web.app.models import User, UserTier, UserTierEnum
from server.web.app.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer()
settings = get_settings()

class UserRegistration(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    created_at: datetime
    tier: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(user_id: str) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(days=30),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get the current authenticated user."""
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.post("/register", response_model=TokenResponse)
async def register_user(
    registration: UserRegistration,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user with username and password."""
    # Check if username already exists
    result = await db.execute(select(User).where(User.display_label == registration.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email already exists (if provided)
    if registration.email:
        result = await db.execute(select(User).where(User.email == registration.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create new user
    user = User(
        id=uuid.uuid4(),
        display_label=registration.username,
        email=registration.email,
        password_hash=hash_password(registration.password),
        created_at=datetime.utcnow(),
        is_active=True
    )
    
    db.add(user)
    
    # Create default user tier
    user_tier = UserTier(
        user_id=user.id,
        tier=UserTierEnum.free,
        start_date=datetime.utcnow()
    )
    db.add(user_tier)
    
    await db.commit()
    await db.refresh(user)
    
    # Create access token
    access_token = create_access_token(str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            username=user.display_label,
            email=user.email,
            created_at=user.created_at,
            tier="free"
        )
    )

@router.post("/login", response_model=TokenResponse)
async def login_user(
    login: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login with username and password."""
    # Find user by username
    result = await db.execute(select(User).where(User.display_label == login.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")
    
    # Get user tier
    tier_result = await db.execute(
        select(UserTier).where(
            UserTier.user_id == user.id,
            UserTier.end_date.is_(None)
        )
    )
    user_tier = tier_result.scalar_one_or_none()
    tier_name = user_tier.tier.value if user_tier else "free"
    
    # Create access token
    access_token = create_access_token(str(user.id))
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            username=user.display_label,
            email=user.email,
            created_at=user.created_at,
            tier=tier_name
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user information."""
    # Get user tier
    tier_result = await db.execute(
        select(UserTier).where(
            UserTier.user_id == current_user.id,
            UserTier.end_date.is_(None)
        )
    )
    user_tier = tier_result.scalar_one_or_none()
    tier_name = user_tier.tier.value if user_tier else "free"
    
    return UserResponse(
        id=str(current_user.id),
        username=current_user.display_label,
        email=current_user.email,
        created_at=current_user.created_at,
        tier=tier_name
    )

@router.post("/logout")
async def logout_user():
    """Logout user (client should discard token)."""
    return {"message": "Successfully logged out"}