"""Rotas de usuários."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.user_service import UserService
from app.core.exceptions import AppException

router = APIRouter()


@router.get("", response_model=dict)
async def list_users(
    skip: int = Query(0, ge=0, description="Número de registros para pular"),
    limit: int = Query(100, ge=1, le=1000, description="Limite de registros"),
    search: Optional[str] = Query(None, description="Busca por nome ou email"),
    role: Optional[UserRole] = Query(None, description="Filtro por role"),
    is_active: Optional[bool] = Query(None, description="Filtro por status ativo"),
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Lista usuários (apenas admin)."""
    try:
        users = UserService.get_users(
            db, skip=skip, limit=limit, search=search, 
            role=role, is_active=is_active
        )
        
        return {
            "success": True,
            "data": {
                "users": [UserResponse.from_orm(user) for user in users],
                "total": len(users),
                "skip": skip,
                "limit": limit
            }
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Cria novo usuário (apenas admin)."""
    try:
        user = UserService.create_user(db, user_data, current_user)
        
        return {
            "success": True,
            "message": "Usuário criado com sucesso",
            "data": {"user": UserResponse.from_orm(user)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/{user_id}", response_model=dict)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Busca usuário por ID (apenas admin)."""
    try:
        user = UserService.get_user_by_id(db, user_id)
        
        return {
            "success": True,
            "data": {"user": UserResponse.from_orm(user)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/{user_id}", response_model=dict)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Atualiza usuário (apenas admin)."""
    try:
        user = UserService.update_user(db, user_id, user_data, current_user)
        
        return {
            "success": True,
            "message": "Usuário atualizado com sucesso",
            "data": {"user": UserResponse.from_orm(user)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Remove usuário (soft delete - apenas admin)."""
    try:
        user = UserService.delete_user(db, user_id, current_user)
        
        return {
            "success": True,
            "message": "Usuário removido com sucesso",
            "data": {"user": UserResponse.from_orm(user)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/stats/summary", response_model=dict)
async def get_user_stats(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Estatísticas de usuários (apenas admin)."""
    try:
        stats = UserService.get_user_stats(db)
        
        return {
            "success": True,
            "data": {"stats": stats}
        }
         
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas"
        )

