"""
Serviços de autenticação e gerenciamento de usuários.

Responsável por:
- Registro de usuários
- Login com email/senha
- Geração e renovação de tokens JWT
- Recuperação de Senha com envio de Email
"""

from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy.orm import Session
import secrets

from app.models.user_profile import UserProfile
from app.models.user import User, UserRole
from app.schemas.auth import UserRegister, UserLogin
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from app.core.exceptions import (
    UnauthorizedException,
    ConflictException,
    NotFoundException
)
from app.core.config import settings
from app.core.mail import send_reset_password_email


class AuthService:

    # =========================
    # REGISTRO DE USUÁRIO
    # =========================

    @staticmethod
    def register_user(db: Session, user_data: UserRegister) -> User:
        """
        Registra um novo usuário com email e senha e cria o perfil vinculado.
        Tudo em uma única transação no banco.
        """
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ConflictException("Email já está em uso")

        if hasattr(user_data, 'cpf') and user_data.cpf:
            existing_cpf = db.query(UserProfile).filter(UserProfile.cpf == user_data.cpf).first()
            if existing_cpf:
                raise ConflictException("Este CPF já está cadastrado no sistema")

        email_token = secrets.token_urlsafe(32)

        user = User(
            name=user_data.name,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role,
            email_verification_token=email_token,
            is_active=True,
            is_email_verified=False,
        )

        db.add(user)
        db.flush()

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

        try:
            db.commit()
            db.refresh(user)
            return user
        except Exception:
            db.rollback()
            raise ConflictException("Erro de integridade ao salvar usuário e perfil.")

    # =========================
    # LOGIN TRADICIONAL
    # =========================

    @staticmethod
    def authenticate_user(db: Session, credentials: UserLogin) -> Tuple[User, dict]:
        """Autentica usuário via email e senha."""
        user = db.query(User).filter(User.email == credentials.email).first()

        if not user or not verify_password(credentials.password, user.password_hash):
            raise UnauthorizedException("Credenciais inválidas")

        tokens = AuthService._generate_tokens(user)
        return user, tokens

    # =========================
    # REFRESH TOKEN
    # =========================

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> dict:
        """Gera novos tokens a partir de um refresh token válido."""
        payload = decode_token(refresh_token)
        user_id = payload.get("sub")

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise UnauthorizedException("Usuário inválido")

        return AuthService._generate_tokens(user)

    # =========================
    # RECUPERAÇÃO DE SENHA
    # =========================

    @staticmethod
    async def forgot_password(db: Session, email: str) -> None:
        """Gera token de recuperação e envia o email."""
        user = db.query(User).filter(User.email == email).first()

        if not user:
            return

        token = secrets.token_urlsafe(32)

        user.password_reset_token = token
        user.password_reset_expires = datetime.utcnow() + timedelta(minutes=30)
        db.commit()

        link_recuperacao = f"{settings.FRONTEND_URL}/reset-password?token={token}"

        try:
            await send_reset_password_email(email, link_recuperacao)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Erro ao enviar email de recuperação: {e}")

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> None:
        """Valida o token e atualiza a senha do usuário."""
        user = db.query(User).filter(User.password_reset_token == token).first()

        if not user:
            raise UnauthorizedException("Token inválido.")

        if user.password_reset_expires < datetime.utcnow():
            raise UnauthorizedException("Token expirado. Solicite novamente.")

        user.password_hash = get_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None

        db.commit()

    # =========================
    # AUXILIAR – GERA TOKENS
    # =========================

    @staticmethod
    def _generate_tokens(user: User) -> dict:
        """Gera access token e refresh token JWT."""
        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "expires_in": 50 * 60,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "avatar_url": user.avatar_url
            }
        }