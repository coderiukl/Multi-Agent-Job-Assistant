from datetime import datetime,timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

from app.core.config import settings
from app.db.models import RefreshToken, User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # check exist email
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")
    
    user = User(
        email = body.email,
        full_name = body.full_name,
        password_hash = hash_password(body.password),
    )

    db.add(user)
    await db.flush() # để lấy được user.id trước khi commit
    return user

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=401, 
            detail="Email hoặc mật khẩu không đúng"
        )
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")
    
    raw_refresh, hashed_refresh = create_refresh_token()

    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    db.add(refresh_token)

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=raw_refresh,
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    hashed = hash_refresh_token(body.refresh_token)
    now = datetime.now(timezone.utc)

    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hashed))
    token_record = result.scalar_one_or_none()

    if not token_record:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")
    
    if token_record.revoked_at is not None:
        # Token đã bị revoke -> có thể đang bị replay attack, revoke toàn bộ session
        await db.execute(select(RefreshToken).where((RefreshToken.user_id == token_record.user_id), RefreshToken.revoked_at.is_(None),))
        raise HTTPException(status_code=401, detail="Refresh token đã bị thu hồi")
    
    if token_record.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=401, detail="Refresh token đã hết hạn")
    
    # Revoke token old
    token_record.revoked_at = now

    # Create new token pair
    raw_refresh, hashed_refresh = create_refresh_token()
    new_refresh = RefreshToken(
        user_id=token_record.user_id,
        token_hash=hashed_refresh,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=token_record.user_agent,
        ip_address=token_record.ip_address,
    )

    db.add(new_refresh)

    return TokenResponse(
        access_token=create_access_token(str(token_record.user_id)),
        refresh_token=raw_refresh,
    )

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    hashed = hash_refresh_token(body.refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hashed, RefreshToken.user_id == current_user.id)
    )

    token_record = result.scalar_one_or_none()

    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = datetime.now(timezone.utc)

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user