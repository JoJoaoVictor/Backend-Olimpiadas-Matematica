from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole
from app.core.config import settings

# Security scheme
security = HTTPBearer(auto_error=False)

 
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Dependency para obter usuário atual autenticado."""
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Decodifica o token
        payload = decode_token(credentials.credentials)
        
        # Verifica se é token de acesso
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tipo de token inválido"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
         
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Busca o usuário no banco
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário inativo"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency para usuário ativo (alias para get_current_user)."""
    return current_user


def require_roles(*roles: UserRole):
    """Dependency factory para exigir roles específicos."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissões insuficientes"
            )
        return current_user
    
    return role_checker


# Convenience dependencies para roles comuns
def get_admin_user(current_user: User = Depends(require_roles(UserRole.ADMIN))) -> User:
    """Dependency para usuários admin."""
    return current_user


def get_professor_user(
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROFESSOR))
) -> User:
    """Dependency para professores e admins."""
    return current_user

def get_professor_or_revisor_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency para professores e revisores."""
    if current_user.role not in [UserRole.PROFESSOR, UserRole.REVISOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas professores e revisores podem acessar este recurso"
        )
    return current_user


def get_professor_or_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency para professores e admins."""
    if current_user.role not in [UserRole.PROFESSOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas professores e administradores podem acessar este recurso"
        )
    return current_user


def get_revisor_or_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency para revisores e admins."""
    if current_user.role not in [UserRole.REVISOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas revisores e administradores podem acessar este recurso"
        )
    return current_user


def get_any_staff_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Dependency para qualquer membro da equipe (não estudantes)."""
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas membros da equipe podem acessar este recurso"
        )
    return current_user