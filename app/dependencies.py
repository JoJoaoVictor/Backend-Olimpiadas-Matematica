"""
Módulo de Dependências (app/dependencies.py).
Responsável por injetar o usuário atual nas rotas e verificar permissões (Roles).
"""
from typing import List
from fastapi import Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

# Importa o esquema de segurança e o decodificador que configuramos no security.py
from app.core.security import decode_token, oauth2_scheme
from app.database import get_db
from app.models.user import User, UserRole

# ==============================================================================
# 1. OBTER USUÁRIO ATUAL (Core Authentication)
# ==============================================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme), # Usa o esquema OAuth2 para integrar com Swagger
    db: Session = Depends(get_db)
) -> User:
    """
    Valida o Token JWT, verifica se o usuário existe e está ativo.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decodifica o token usando a função do security.py
        payload = decode_token(token)
        
        if payload is None:
            raise credentials_exception
            
        token_type: str = payload.get("type")
        if token_type != "access":
            raise credentials_exception
            
        user_id: str = payload.get("sub")
        if user_id is None:
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


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Alias para get_current_user, caso queira adicionar lógica extra de ativação no futuro."""
    return current_user


# ==============================================================================
# 2. FACTORY DE PERMISSÕES (Role Based Access Control)
# ==============================================================================

def require_roles(allowed_roles: List[UserRole]):
    """
    Cria uma dependência que verifica se o usuário tem um dos papéis permitidos.
    Uso: Depends(require_roles([UserRole.ADMIN, UserRole.PROFESSOR]))
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissões insuficientes. Necessário: {[role.value for role in allowed_roles]}"
            )
        return current_user
    
    return role_checker


# ==============================================================================
# 3. SHORTCUTS PARA ROLES COMUNS
# Facilitam a importação nas rotas: @router.get("/", dependencies=[Depends(get_admin_user)])
# ==============================================================================

def get_admin_user(
    current_user: User = Depends(require_roles([UserRole.ADMIN]))
) -> User:
    """Apenas Administradores."""
    return current_user


def get_professor_user(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.PROFESSOR]))
) -> User:
    """Professores e Administradores."""
    return current_user


def get_professor_or_revisor_user(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.PROFESSOR, UserRole.REVISOR]))
) -> User:
    """Professores, Revisores e Admins (Staff de Conteúdo)."""
    return current_user


def get_any_staff_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Qualquer membro da equipe (Admin, Professor, Revisor).
    Bloqueia apenas STUDENT.
    """
    if current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Estudantes não têm acesso a este recurso."
        )
    return current_user