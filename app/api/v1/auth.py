"""Rotas de autenticação."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    UserRegister, UserLogin, TokenResponse, TokenRefresh,
    PasswordReset, PasswordResetConfirm, EmailVerification
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.core.exceptions import AppException

router = APIRouter()


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """Registra novo usuário."""
    try:
        user = AuthService.register_user(db, user_data)
        
        # Gera tokens para login automático
        _, tokens = AuthService.authenticate_user(db, UserLogin(
            email=user_data.email,
            password=user_data.password
        ))
        
        return {
            "success": True,
            "message": "Usuário registrado com sucesso",
            "data": {
                "user": UserResponse.from_orm(user),
                "tokens": tokens
            }
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/login", response_model=dict)
async def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """Autentica usuário."""
    try:
        user, tokens = AuthService.authenticate_user(db, credentials)
        
        return {
            "success": True,
            "message": "Login realizado com sucesso",
            "data": {
                "user": UserResponse.from_orm(user),
                "tokens": tokens
            }
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/refresh-token", response_model=dict)
async def refresh_access_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """Renova access token."""
    try:
        tokens = AuthService.refresh_access_token(db, token_data.refresh_token)
        
        return {
            "success": True,
            "message": "Token renovado com sucesso",
            "data": {"tokens": tokens}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/profile", response_model=dict)
async def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Retorna perfil do usuário atual."""
    return {
        "success": True,
        "data": {"user": UserResponse.from_orm(current_user)}
    }


@router.patch("/profile", response_model=dict)
async def update_user_profile(
    profile_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Atualiza perfil do usuário."""
    try:
        # Atualiza campos permitidos
        allowed_fields = {'name', 'avatar_url'}
        update_data = {k: v for k, v in profile_data.items() if k in allowed_fields}
        
        for field, value in update_data.items():
            setattr(current_user, field, value)
        
        db.commit()
        db.refresh(current_user)
        
        return {
            "success": True,
            "message": "Perfil atualizado com sucesso",
            "data": {"user": UserResponse.from_orm(current_user)}
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar perfil"
        )


@router.post("/forgot-password", response_model=dict)
async def forgot_password(
    password_data: PasswordReset,
    db: Session = Depends(get_db)
):
    """Solicita reset de senha."""
    try:
        AuthService.request_password_reset(db, password_data.email)
        
        return {
            "success": True,
            "message": "Se o email estiver cadastrado, você receberá as instruções de recuperação"
        }
        
    except Exception:
        # Por segurança, sempre retorna sucesso
        return {
            "success": True,
            "message": "Se o email estiver cadastrado, você receberá as instruções de recuperação"
        }


@router.post("/reset-password/{token}", response_model=dict)
async def reset_password(
    token: str,
    password_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """Reseta senha do usuário."""
    try:
        AuthService.reset_password(db, token, password_data.new_password)
        
        return {
            "success": True,
            "message": "Senha redefinida com sucesso"
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/verify-email/{token}", response_model=dict)
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """Verifica email do usuário."""
    try:
        user = AuthService.verify_email(db, token)
        
        return {
            "success": True,
            "message": "Email verificado com sucesso",
            "data": {"user": UserResponse.from_orm(user)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/logout", response_model=dict)
async def logout_user(
    current_user: User = Depends(get_current_user)
):
    """Logout do usuário (invalidação de token no frontend)."""
    return {
        "success": True,
        "message": "Logout realizado com sucesso"
    }

