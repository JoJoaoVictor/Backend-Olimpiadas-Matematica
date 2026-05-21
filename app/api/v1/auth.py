"""
Rotas de autenticação da aplicação.
Inclui:
- Registro
- Login
- Refresh token
- Perfil
- Reset de senha
- Login com Google (JWT credential)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Google Auth
from google.oauth2 import id_token
from google.auth.transport import requests

# Core & Database
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.user_profile import UserProfile       
from app.services.auth_service import AuthService
from app.core.exceptions import AppException
from app.core.config import settings

# Schemas
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenRefresh,
    ForgotPasswordRequest, # <--- Nome Atualizado
    ResetPasswordRequest,  # <--- Nome Atualizado
)
# Mantivemos o UserResponse vindo de .user pois você o usa para formatar o objeto User
from app.schemas.user import UserResponse 

router = APIRouter()


# =========================
# REGISTRO
# =========================
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    """Registra novo usuário, cria perfil acadêmico e faz login automático."""
    try:
        user = AuthService.register_user(db, user_data)

        # ── Cria o perfil acadêmico vinculado ao usuário ──────────────
        # Os campos novos chegam via UserRegister (ver auth_schema_patch.py)
        profile = UserProfile(
            user_id   = user.id,
            cpf       = user_data.cpf       or None,
            telefone  = user_data.telefone  or None,
            campus    = user_data.campus    or None,
            cidade    = user_data.cidade    or None,
            matricula = user_data.matricula or None,
            curso     = user_data.curso     or None,
        )
        db.add(profile)
        db.commit()
        db.refresh(user)
        # ─────────────────────────────────────────────────────────────

        # Login automático após registro
        _, tokens = AuthService.authenticate_user(
            db,
            UserLogin(email=user_data.email, password=user_data.password),
        )

        return {
            "success": True,
            "message": "Usuário registrado com sucesso",
            "data": {
                "user": UserResponse.from_orm(user),
                "tokens": tokens,
            },
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# =========================
# LOGIN EMAIL + SENHA
# =========================
@router.post("/login")
async def login_user(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    """Autentica usuário via email e senha."""
    try:
        user, tokens = AuthService.authenticate_user(db, credentials)

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
# LOGIN COM GOOGLE (JWT)
# =========================
@router.options("/google")
async def options_google():
    """Responde ao preflight CORS para a rota Google OAuth."""
    return {"message": "OK"}
@router.options("/google")
async def options_google():
    """Responde ao preflight CORS para o endpoint Google OAuth."""
    return {"message": "OK"}

@router.post("/google")
async def login_with_google(payload: dict, db: Session = Depends(get_db)):
    credential = payload.get("credential")
    if not credential:
        raise HTTPException(status_code=400, detail="Token do Google não enviado")

    try:
        user, tokens = AuthService.authenticate_google_user(db, credential)

        return {
            "success": True,
            "data": {
                "user": UserResponse.from_orm(user),
                "tokens": tokens,
            },
        }
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        print(f"Erro Google: {e}")
        raise HTTPException(status_code=400, detail="Falha na autenticação Google")

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
    data: ForgotPasswordRequest, # Schema atualizado
    db: Session = Depends(get_db),
):
    """Solicita link de reset de senha."""
    await AuthService.forgot_password(db, data.email)

    return {
        "success": True,
        "message": "Se o email estiver cadastrado, você receberá instruções.",
    }


@router.post("/reset-password") # Removido {token} da URL, pois vem no body agora
async def reset_password(
    data: ResetPasswordRequest, # Este schema contém 'token' e 'new_password'
    db: Session = Depends(get_db),
):
    """Reseta a senha do usuário usando o token."""
    try:
        # Chama o método correto com os dados do corpo
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
    """
    Logout é controlado no frontend (remoção do token).
    Endpoint apenas para compatibilidade ou invalidação futura.
    """
    return {
        "success": True,
        "message": "Logout realizado com sucesso",
    }