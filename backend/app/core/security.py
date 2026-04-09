from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from jose import JWTError, jwt
import secrets
import hashlib
from typing import Optional

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# hashmap password
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# kiểm tra password trước và sau khi hash có khớp với nhau không
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

def create_refresh_token() -> tuple[str, str]:
    """Trả về  (raw_token, hashed_token). Lưu hash vào DB, gửi raw cho client."""
    raw = secrets.token_hex(64)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def decode_access_token(token: str) -> Optional[str]:
    """Trả về user_id nếu token hợp lệ, None nếu không"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None