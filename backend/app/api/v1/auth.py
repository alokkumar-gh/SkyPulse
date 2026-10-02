import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.audit import log_audit_event
from app.models.user import User
from app.models.enums import UserRole, AuditActionType
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserInToken,
    RegisterResponse,
    MeResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Check if email exists
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "EMAIL_ALREADY_EXISTS",
                "message": f"A user with email {data.email} already exists",
                "details": {"email": data.email},
            },
        )

    user = User(
        email=data.email.lower(),
        password_hash=get_password_hash(data.password),
        display_name=data.display_name,
        phone_number=data.phone_number,
        role=UserRole.CITIZEN.value,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    await log_audit_event(
        db=db,
        action_type=AuditActionType.CREATE.value,
        entity_type="User",
        entity_id=user.id,
        user_id=user.id,
        new_value={"email": user.email, "role": user.role},
        request=request,
    )
    await db.commit()
    await db.refresh(user)

    return RegisterResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalars().first()

    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "INVALID_CREDENTIALS",
                "message": "Invalid email or password",
                "details": {},
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "ACCOUNT_INACTIVE",
                "message": "This account has been deactivated",
                "details": {},
            },
        )

    user.last_login_at = datetime.now(timezone.utc)
    await log_audit_event(
        db=db,
        action_type=AuditActionType.LOGIN.value,
        entity_type="User",
        entity_id=user.id,
        user_id=user.id,
        request=request,
    )
    await db.commit()

    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
    }
    access_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserInToken(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role=user.role,
        ),
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await log_audit_event(
        db=db,
        action_type=AuditActionType.LOGOUT.value,
        entity_type="User",
        entity_id=current_user.id,
        user_id=current_user.id,
        request=request,
    )
    await db.commit()
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        display_name=current_user.display_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )
