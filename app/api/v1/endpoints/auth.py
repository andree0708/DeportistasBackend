"""Endpoints de autenticación."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.dependencies import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, RefreshTokenRequest

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": str(user.id), "email": user.email, "message": "Cuenta creada exitosamente"}


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.is_active == True).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    db.add(AuditLog(
        user_id=user.id,
        action="login",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", ""),
    ))
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError("Token inválido")
        user_id = data["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.add(AuditLog(user_id=current_user.id, action="logout"))
    db.commit()
    return {"message": "Sesión cerrada"}


@router.get("/me", response_model=dict)
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_verified": current_user.is_verified,
    }
