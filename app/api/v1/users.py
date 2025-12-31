"""
Rotas de usuários (Endpoints).
Arquivo: app/api/v1/users.py
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

# --- DEPENDÊNCIAS E UTILS ---
from app.database import get_db
from app.core.security import verify_password, get_password_hash
from app.dependencies import get_current_user, get_admin_user, get_current_active_user

# --- MODELS E SCHEMAS ---
from app.models.user import User, UserRole
from app.schemas.user import (
    UserCreate, 
    UserUpdate, 
    UserResponse, 
    UserRoleUpdate, 
    UserUpdateProfile, 
    ChangePassword
)

router = APIRouter()

# ==============================================================================
# ROTAS DO PRÓPRIO USUÁRIO (PERFIL & SEGURANÇA)
# ==============================================================================

@router.get("/me", response_model=dict)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Retorna os dados do usuário logado atualmente.
    """
    return {
        "success": True,
        "data": UserResponse.from_orm(current_user)
    }

@router.put("/me", response_model=dict)
async def update_user_me(
    user_data: UserUpdateProfile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Atualiza dados básicos do próprio usuário (Nome e Avatar).
    """
    try:
        if user_data.name:
            current_user.name = user_data.name
        if user_data.avatar_url:
            current_user.avatar_url = user_data.avatar_url
        
        db.commit()
        db.refresh(current_user)
        
        return {
            "success": True,
            "message": "Perfil atualizado com sucesso",
            "data": UserResponse.from_orm(current_user)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Erro ao atualizar perfil: {str(e)}"
        )

@router.post("/change-password", response_model=dict)
async def change_password(
    password_data: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Permite que o usuário logado altere sua própria senha.
    CORRIGIDO: Usa 'password_hash' para corresponder ao Model do SQLAlchemy.
    """
    
    # 1. Verifica se o usuário tem senha (usuários Google podem não ter)
    # E verifica se a senha atual informada bate com o hash no banco
    if current_user.password_hash:
        if not password_data.current_password:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Por favor, informe sua senha atual."
            )
            
        if not verify_password(password_data.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="A senha atual está incorreta."
            )
        
        # 2. Verifica se a nova senha é igual à antiga
        if password_data.current_password == password_data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="A nova senha deve ser diferente da atual."
            )

    # 3. Criptografa e salva a nova senha no campo CORRETO
    current_user.password_hash = get_password_hash(password_data.new_password)
    
    db.add(current_user) # Garante que o SQLAlchemy rastreie a mudança
    db.commit()
    db.refresh(current_user)
    
    return {
        "success": True,
        "message": "Senha definida com sucesso."
    }

# ==============================================================================
# ROTAS ADMINISTRATIVAS (GERENCIAMENTO)
# ==============================================================================

@router.get("", response_model=dict)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_admin_user), # Apenas Admin
    db: Session = Depends(get_db)
):
    """Lista usuários com paginação e filtros (Apenas Admin)."""
    
    query = db.query(User)

    # Filtros
    if search:
        query = query.filter(User.email.contains(search) | User.name.contains(search))
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    # Contagem total
    total = query.count()

    # Paginação
    users = query.offset(skip).limit(limit).all()

    return {
        "success": True,
        "data": {
            "users": [UserResponse.from_orm(user) for user in users],
            "total": total,
            "skip": skip,
            "limit": limit
        }
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Cria novo usuário manualmente (Apenas Admin)."""
    
    # Verifica duplicidade
    user_exists = db.query(User).filter(User.email == user_data.email).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="Este email já está cadastrado.")

    # Cria objeto User
    # CORRIGIDO: hashed_password -> password_hash no construtor
    new_user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=get_password_hash(user_data.password), # <--- CORREÇÃO AQUI
        role=user_data.role or UserRole.STUDENT,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "success": True,
        "message": "Usuário criado com sucesso",
        "data": {"user": UserResponse.from_orm(new_user)}
    }


@router.get("/stats/summary", response_model=dict)
async def get_user_stats(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Retorna estatísticas gerais (Apenas Admin)."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # Contagem por Role
    roles_count = db.query(User.role, func.count(User.role)).group_by(User.role).all()
    roles_dict = {role.value: count for role, count in roles_count}

    return {
        "success": True,
        "data": {
            "stats": {
                "total": total_users,
                "active": active_users,
                "by_role": roles_dict
            }
        }
    }


@router.get("/{user_id}", response_model=dict)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Busca usuário por ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
    return {
        "success": True,
        "data": {"user": UserResponse.from_orm(user)}
    }


@router.patch("/{user_id}", response_model=dict)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Atualiza dados gerais (Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Atualiza campos se existirem no payload
    if user_data.name is not None:
        user.name = user_data.name
    if user_data.email is not None:
        # Validação extra se mudar email
        if user_data.email != user.email:
             exists = db.query(User).filter(User.email == user_data.email).first()
             if exists:
                 raise HTTPException(status_code=400, detail="Email já em uso por outro usuário.")
        user.email = user_data.email
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.role is not None:
        user.role = user_data.role

    db.commit()
    db.refresh(user)

    return {
        "success": True,
        "message": "Usuário atualizado com sucesso",
        "data": {"user": UserResponse.from_orm(user)}
    }


@router.put("/{user_id}/role", response_model=dict)
async def change_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Altera especificamente o cargo."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    user.role = role_data.role
    db.commit()
    db.refresh(user)
    
    return {
        "success": True,
        "message": "Cargo atualizado com sucesso",
        "data": {"user": UserResponse.from_orm(user)}
    }


@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Soft Delete (desativa usuário)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    
    # Soft delete
    user.is_active = False
    db.commit()
    
    return {
        "success": True,
        "message": "Usuário desativado com sucesso",
        "data": {"user": UserResponse.from_orm(user)}
    }