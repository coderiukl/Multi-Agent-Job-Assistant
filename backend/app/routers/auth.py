from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()

    existing_user = await db.scalar(select(User).where(User.email == email))
    if existing_user:
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")

    user = User(
        email=email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        is_active=True,
        is_verified=False,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()

    user = await db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khóa",
        )

    raw_refresh_token, hashed_refresh_token = create_refresh_token()

    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hashed_refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    db.add(refresh_token)
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=raw_refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    hashed_token = hash_refresh_token(body.refresh_token)

    token_record = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hashed_token)
    )

    if not token_record:
        raise HTTPException(status_code=401, detail="Refresh token không hợp lệ")

    if token_record.revoked_at is not None:
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == token_record.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Refresh token đã bị thu hồi")

    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        raise HTTPException(status_code=401, detail="Refresh token đã hết hạn")

    token_record.revoked_at = now

    raw_refresh_token, hashed_refresh_token = create_refresh_token()
    new_refresh = RefreshToken(
        user_id=token_record.user_id,
        token_hash=hashed_refresh_token,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=token_record.user_agent,
        ip_address=token_record.ip_address,
    )

    db.add(new_refresh)
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(str(token_record.user_id)),
        refresh_token=raw_refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hashed_token = hash_refresh_token(body.refresh_token)

    token_record = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hashed_token,
            RefreshToken.user_id == current_user.id,
        )
    )

    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = datetime.now(timezone.utc)
        await db.commit()


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user