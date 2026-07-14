"""
Rotas de autenticação da aplicação.
Inclui:
- Registro
- Login
- Refresh token
- Perfil
- Reset de senha
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.services.email_service import EmailService

# Core & Database
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserStatus
from app.models.user_profile import UserProfile
from app.services.auth_service import AuthService
from app.core.exceptions import AppException
from app.core.config import settings
from sqlalchemy.exc import IntegrityError
import logging

# Schemas
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenRefresh,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.schemas.user import UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# =========================
# REGISTRO
# =========================
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    background_tasks: BackgroundTasks,  
    db: Session = Depends(get_db),
):
    """Registra novo usuário e dispara e-mail de aviso em segundo plano."""
    try:
        user = AuthService.register_user(db, user_data)

        # 4. DISPARA O E-MAIL EM SEGUNDO PLANO
        # O FastAPI vai responder a requisição primeiro e enviar o e-mail logo depois.
        # Ajuste "EmailService.send_pending_approval_email" para o nome exato da função que você criar.
        background_tasks.add_task(
            EmailService.send_pending_approval_email,
            email=user.email,
            name=user.name
        )

        return {
            "success": True,
            "message": "Registo realizado com sucesso! A sua conta está em análise. Enviámos um email com mais detalhes.",
            "data": {
                "user": UserResponse.from_orm(user),
            },
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        db.rollback()
        logger.error(f"Erro inesperado no registro: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao registrar usuário."
        )
## =========================
# LOGIN EMAIL + SENHA
# =========================
@router.post("/login")
async def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    """Autentica usuário via email e senha e verifica aprovação."""
    try:
        # 1. O AuthService verifica se o e-mail existe e a senha está correta
        user, tokens = AuthService.authenticate_user(db, credentials)

        # 2. 🚨 A CATRACA DE SEGURANÇA AQUI 🚨
        if user.status == UserStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sua conta está aguardando aprovação de um administrador. Você não pode fazer login ainda."
            )
            
        if user.status == UserStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="O acesso para esta conta foi negado pelo administrador."
            )

        # 3. Se passou pelas travas, devolve o token e libera o acesso!
        return {
            "success": True,
            "message": "Login realizado com sucesso",
            "data": {
                "user": UserResponse.from_orm(user),
                "tokens": tokens,
            },
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# =========================
# REFRESH TOKEN
# =========================
@router.post("/refresh-token")
async def refresh_access_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db),
):
    """Renova access token usando refresh token."""
    try:
        tokens = AuthService.refresh_access_token(
            db,
            token_data.refresh_token,
        )

        return {
            "success": True,
            "message": "Token renovado com sucesso",
            "data": {"tokens": tokens},
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# =========================
# PERFIL
# =========================
@router.get("/me")
@router.get("/profile")
async def get_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Retorna perfil do usuário autenticado."""
    return {
        "success": True,
        "data": {"user": UserResponse.from_orm(current_user)},
    }


@router.patch("/profile")
async def update_user_profile(
    profile_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza nome e avatar do usuário."""
    try:
        allowed_fields = {"name", "avatar_url"}
        for field, value in profile_data.items():
            if field in allowed_fields:
                setattr(current_user, field, value)

        db.commit()
        db.refresh(current_user)

        return {
            "success": True,
            "message": "Perfil atualizado com sucesso",
            "data": {"user": UserResponse.from_orm(current_user)},
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Erro ao atualizar perfil",
        )


# =========================
# RESET DE SENHA
# =========================
@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Solicita link de reset de senha."""
    await AuthService.forgot_password(db, data.email)

    return {
        "success": True,
        "message": "Se o email estiver cadastrado, você receberá instruções.",
    }


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Reseta a senha do usuário usando o token."""
    try:
        AuthService.reset_password(
            db,
            data.token,
            data.new_password,
        )

        return {
            "success": True,
            "message": "Senha redefinida com sucesso. Faça login novamente.",
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# =========================
# LOGOUT
# =========================
@router.post("/logout")
async def logout_user():
    """Logout controlado no frontend. Endpoint para compatibilidade futura."""
    return {
        "success": True,
        "message": "Logout realizado com sucesso",
    }