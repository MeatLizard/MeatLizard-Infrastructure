
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from shared_lib.config import get_config

settings = get_config()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.security.jwt_secret, algorithm=settings.security.jwt_algorithm)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.security.jwt_secret, algorithms=[settings.security.jwt_algorithm])
        return payload
    except JWTError:
        return None
