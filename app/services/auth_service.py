"""
Serviços de autenticação e gerenciamento de usuários.

Responsável por:
- Registro de usuários
- Login com email/senha
- Login com Google (Google Identity Services)
- Geração e renovação de tokens JWT
- Recuperação de Senha (Esqueci minha senha) com envio de Email real
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional
from sqlalchemy.orm import Session
import secrets

# Google Identity Services (JWT)
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

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

# IMPORTAÇÃO DE ENVIO DE EMAIL (Utilitário criado anteriormente)
from app.core.mail import send_reset_password_email

class AuthService:
    """
    Classe responsável por todas as regras de negócio
    relacionadas à autenticação e autorização.
    """

    # =========================
    # REGISTRO DE USUÁRIO
    # =========================

    @staticmethod
    def register_user(db: Session, user_data: UserRegister) -> User:
        """
        Registra um novo usuário com email e senha.
        """
        # Verifica se email já está em uso
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ConflictException("Email já está em uso")

        # Token para verificação de email (caso implemente futuramente)
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
        db.commit()
        db.refresh(user)

        return user

    # =========================
    # LOGIN TRADICIONAL
    # =========================

    @staticmethod
    def authenticate_user(db: Session, credentials: UserLogin) -> Tuple[User, dict]:
        """
        Autentica usuário via email e senha.
        """
        user = db.query(User).filter(User.email == credentials.email).first()

        if not user or not verify_password(credentials.password, user.password_hash):
            raise UnauthorizedException("Credenciais inválidas")

        tokens = AuthService._generate_tokens(user)
        return user, tokens

    # =========================
    # LOGIN COM GOOGLE (JWT)
    # =========================

    @staticmethod
    def authenticate_google_user(db: Session, credential: str) -> Tuple[User, dict]:
        """
        Autentica usuário via Google Identity Services.
        Se o usuário não existir, cria automaticamente com cargo STUDENT.
        """

        try:
            # 1. Valida o token JWT com o Google
            google_payload = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
        except ValueError:
            raise UnauthorizedException("Token do Google inválido")

        # 2. Extrai dados do usuário
        email = google_payload.get("email")
        name = google_payload.get("name")
        picture = google_payload.get("picture")
        # 'sub' é o ID único do usuário no Google
        google_sub = google_payload.get("sub") 

        if not email:
            raise UnauthorizedException("Email não encontrado no token do Google")

        # 3. Verifica se usuário já existe
        user = db.query(User).filter(User.email == email).first()

        # 4. Cria usuário automaticamente se não existir
        if not user:
            user = User(
                name=name,
                email=email,
                google_id=google_sub, 
                password_hash="", # Usuário Google não tem senha
                
                # --- REQUISITO: Google = STUDENT ---
                role=UserRole.STUDENT,
                # -----------------------------------
                
                is_active=True,
                is_email_verified=True, # Google já verifica o email
                avatar_url=picture,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
 
        # 5. Gera tokens JWT da aplicação
        tokens = AuthService._generate_tokens(user)

        return user, tokens

    # =========================
    # REFRESH TOKEN
    # =========================

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> dict:
        """
        Gera novos tokens a partir de um refresh token válido.
        """
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
        """
        Gera token de recuperação e ENVIA O EMAIL DE VERDADE.
        OBS: Este método deve ser chamado com 'await'.
        """
        user = db.query(User).filter(User.email == email).first()
        
        # Se usuário não existe, retornamos silenciosamente para segurança (Security through obscurity)
        if not user:
            return

        # 1. Gerar Token Único Seguro
        token = secrets.token_urlsafe(32)
        
        # 2. Salvar no Banco (Validade: 30 minutos)
        user.password_reset_token = token
        user.password_reset_expires = datetime.utcnow() + timedelta(minutes=30)
        db.commit()

        # 3. Gerar Link (Apontando para o Frontend)
        # Nota: Idealmente use settings.FRONTEND_URL, aqui estamos usando localhost fixo
        link_recuperacao = f"http://localhost:5173/reset-password?token={token}"
        
        # 4. Enviar Email (Async)
        try:
            print(f"Enviando email de recuperação para {email}...")
            await send_reset_password_email(email, link_recuperacao)
            print("Email enviado com sucesso!")
        except Exception as e:
            # Logamos o erro mas não quebramos a requisição para o usuário não ver stack trace
            print(f"ERRO CRÍTICO AO ENVIAR EMAIL: {e}")
            # Em produção, usar logger.error(e)

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> None:
        """
        Valida o token e atualiza a senha do usuário.
        """
        # Busca usuário pelo token
        user = db.query(User).filter(User.password_reset_token == token).first()

        if not user:
            raise UnauthorizedException("Token inválido.")

        # Verifica expiração
        if user.password_reset_expires < datetime.utcnow():
            raise UnauthorizedException("Token expirado. Solicite novamente.")

        # Atualiza a senha e limpa o token
        user.password_hash = get_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        
        db.commit()

    # =========================
    # AUXILIAR – GERA TOKENS
    # =========================

    @staticmethod
    def _generate_tokens(user: User) -> dict:
        """
        Gera access token e refresh token JWT.
        """
        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "expires_in": 15 * 60,  # 15 minutos
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "avatar_url": user.avatar_url
            }
        }