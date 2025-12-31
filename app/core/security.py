"""
Módulo de segurança central (app/core/security.py).
Gerencia Hashing de senhas, Tokens JWT e Dependências de Autenticação.
"""
from datetime import datetime, timedelta
from typing import Any, Union, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db 
from app.models.user import User, UserRole

# Configuração do Hashing de Senha
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# Define onde o FastAPI deve procurar o token (na URL de login)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ==============================================================================
# 1. FUNÇÕES UTILITÁRIAS (CRIPTOGRAFIA E TOKENS)
# ==============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se uma senha em texto puro bate com o hash salvo."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Gera o hash seguro de uma senha."""
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any], 
    extra_data: dict = None, 
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Cria token de acesso JWT.
    Pode receber dados extras (ex: role, email) para colocar no payload.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
      
    # Cria o payload base
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    
    # Adiciona dados extras se houver
    if extra_data:
        to_encode.update(extra_data)

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(subject: Union[str, Any]) -> str:
    """Cria token de refresh JWT (validade longa)."""
    expire = datetime.utcnow() + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decodifica o token JWT e retorna o payload cru.
    Necessário para o arquivo app/dependencies.py.
    """
    try:
        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return None


# ==============================================================================
# 2. DEPENDÊNCIAS DO FASTAPI (PROTEÇÃO DE ROTAS)
# ==============================================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Decodifica o token, valida e retorna o objeto User do banco.
    Usado em rotas protegidas.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Reutiliza a função decode_token ou faz manualmente
        payload = decode_token(token)
        if payload is None:
            raise credentials_exception
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
        token_type: str = payload.get("type")
        if token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Busca o usuário no banco
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Usuário inativo")
        
    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependência que verifica se o usuário logado é ADMIN.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilégios de administrador necessários"
        )
    return current_user