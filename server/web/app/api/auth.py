
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from server.web.app.db import get_db
from server.web.app.models import User
from shared_lib.security import get_password_hash, verify_password, create_access_token

router = APIRouter()

class UserCreate(BaseModel):
    email: str
    password: str
    display_label: str

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/api/auth/register")
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        display_label=user_data.display_label
    )
    db.add(new_user)
    await db.commit()
    return {"message": "User registered successfully"}

@router.post("/api/auth/login")
async def login_for_access_token(form_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}
