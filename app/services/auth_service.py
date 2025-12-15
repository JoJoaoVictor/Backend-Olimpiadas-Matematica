"""Serviços de autenticação e gerenciamento de usuários."""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import secrets
import hashlib

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
    NotFoundException,
    ValidationException
)
 

class AuthService:
    """Serviços de autenticação."""
    
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_HOURS = 2
    
    @staticmethod
    def register_user(db: Session, user_data: UserRegister) -> User:
        """Registra novo usuário."""
        # Verifica se email já existe
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ConflictException("Email já está em uso")
        
        # Cria token de verificação de email
        email_token = secrets.token_urlsafe(32)
        
        # Cria usuário
        user = User(
            name=user_data.name,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role,
            email_verification_token=email_token,
            is_active=True
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # TODO: Enviar email de verificação
        # email_service.send_verification_email(user.email, email_token)
        
        return user
    
    @staticmethod
    def authenticate_user(db: Session, credentials: UserLogin) -> Tuple[User, dict]:
        """Autentica usuário e retorna tokens."""
        # Busca usuário
        user = db.query(User).filter(User.email == credentials.email).first()
        if not user:
            raise UnauthorizedException("Credenciais inválidas")
        
        # Verifica se conta está bloqueada
        if AuthService._is_account_locked(user):
            raise UnauthorizedException(
                f"Conta bloqueada até {user.locked_until.strftime('%H:%M:%S')} "
                f"devido a múltiplas tentativas de login"
            )
        
        # Verifica senha
        if not verify_password(credentials.password, user.password_hash):
            AuthService._handle_failed_login(db, user)
            raise UnauthorizedException("Credenciais inválidas")
        
        # Verifica se usuário está ativo
        if not user.is_active:
            raise UnauthorizedException("Conta desativada")
        
        # Login bem-sucedido - reset tentativas
        if user.login_attempts > 0:
            user.login_attempts = 0
            user.locked_until = None
        
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Gera tokens
        tokens = AuthService._generate_tokens(user)
        
        return user, tokens
    
    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> dict:
        """Renova access token usando refresh token."""
        try:
            payload = decode_token(refresh_token)
            
            if payload.get("type") != "refresh":
                raise UnauthorizedException("Token de refresh inválido")
            
            user_id = payload.get("sub")
            user = db.query(User).filter(User.id == int(user_id)).first()
            
            if not user or not user.is_active:
                raise UnauthorizedException("Usuário não encontrado ou inativo")
            
            # Gera novos tokens
            return AuthService._generate_tokens(user)
            
        except Exception:
            raise UnauthorizedException("Token de refresh inválido ou expirado")
    
    @staticmethod
    def verify_email(db: Session, token: str) -> User:
        """Verifica email do usuário."""
        user = db.query(User).filter(User.email_verification_token == token).first()
        if not user:
            raise NotFoundException("Token de verificação inválido")
        
        user.is_email_verified = True
        user.email_verification_token = None
        db.commit()
        
        return user
    
    @staticmethod
    def request_password_reset(db: Session, email: str) -> Optional[User]:
        """Solicita reset de senha."""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            # Por segurança, não revelamos se email existe
            return None
        
        # Gera token de reset
        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        
        user.password_reset_token = token_hash
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        
        # TODO: Enviar email com token
        # email_service.send_password_reset_email(user.email, reset_token)
        
        return user
    
    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> User:
        """Reseta senha do usuário."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        user = db.query(User).filter(
            User.password_reset_token == token_hash,
            User.password_reset_expires > datetime.utcnow()
        ).first()
        
        if not user:
            raise ValidationException("Token inválido ou expirado")
        
        # Atualiza senha
        user.password_hash = get_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.login_attempts = 0  # Reset tentativas
        user.locked_until = None
        
        db.commit()
        return user
    
    @staticmethod
    def _is_account_locked(user: User) -> bool:
        """Verifica se conta está bloqueada."""
        return (
            user.locked_until is not None and 
            user.locked_until > datetime.utcnow()
        )
    
    @staticmethod
    def _handle_failed_login(db: Session, user: User):
        """Processa tentativa de login falhada."""
        user.login_attempts += 1
        
        if user.login_attempts >= AuthService.MAX_LOGIN_ATTEMPTS:
            user.locked_until = (
                datetime.utcnow() + 
                timedelta(hours=AuthService.LOCKOUT_DURATION_HOURS)
            )
        
        db.commit()
    
    @staticmethod
    def _generate_tokens(user: User) -> dict:
        """Gera access e refresh tokens."""
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 15 * 60  # 15 minutos em segundos
        }

