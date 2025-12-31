"""
Serviços de gerenciamento de usuários (Lógica de Negócio).
Arquivo: app/services/user_service.py
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from fastapi import HTTPException, status

# Imports dos Models e Schemas
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserRoleUpdate
from app.core.security import get_password_hash

class UserService:
    """
    Classe contendo toda a lógica de manipulação de usuários.
    Encapsula o acesso ao banco (SQLAlchemy).
    """
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, current_user: User) -> User:
        """
        Cria novo usuário (Apenas Admin).
        """
        # 1. Verifica duplicidade de email
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email já está em uso"
            )
        
        # 2. Prepara o objeto
        user = User(
            name=user_data.name,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            role=user_data.role or UserRole.STUDENT,
            is_active=user_data.is_active if user_data.is_active is not None else True,
            is_email_verified=True # Assumimos verificado se criado por Admin
        )
        
        # 3. Salva no banco
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def get_users(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None
    ) -> List[User]:
        """
        Lista usuários aplicando filtros de busca.
        """
        query = db.query(User)
        
        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        if role:
            query = query.filter(User.role == role)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Busca usuário por ID."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado"
            )
        return user
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Busca usuário por email (interno)."""
        return db.query(User).filter(User.email == email).first()
      
    @staticmethod
    def update_user(
        db: Session, 
        user_id: int, 
        user_data: UserUpdate,
        current_user: User
    ) -> User:
        """Atualiza dados gerais do usuário."""
        user = UserService.get_user_by_id(db, user_id)
        
        # Converte para dict removendo campos não enviados (None)
        update_data = user_data.dict(exclude_unset=True)
        
        # Validação extra de email duplicado na edição
        if "email" in update_data and update_data["email"] != user.email:
             exists = db.query(User).filter(User.email == update_data["email"]).first()
             if exists:
                 raise HTTPException(status_code=400, detail="Email já em uso.")

        for field, value in update_data.items():
            setattr(user, field, value)
        
        db.commit()
        db.refresh(user)
        
        return user

    @staticmethod
    def update_user_role(
        db: Session,
        user_id: int,
        role_data: UserRoleUpdate,
        current_user: User
    ) -> User:
        """
        Atualiza APENAS o cargo do usuário.
        """
        user = UserService.get_user_by_id(db, user_id)
        
        # Segurança: Admin não pode alterar o próprio cargo por aqui para não se bloquear
        if user.id == current_user.id:
             raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail="Você não pode alterar seu próprio cargo nesta rota."
             )

        user.role = role_data.role
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def delete_user(db: Session, user_id: int, current_user: User) -> User:
        """
        Remove usuário (Soft Delete ou Hard Delete).
        """
        user = UserService.get_user_by_id(db, user_id)
        
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível deletar sua própria conta"
            )
        
        # --- MODO 1: SOFT DELETE (Recomendado para histórico) ---
        user.is_active = False
        db.commit()
        db.refresh(user) # Necessário para retornar o objeto atualizado
        
        # --- MODO 2: HARD DELETE (Apaga mesmo) ---
        # db.delete(user)
        # db.commit()
        
        return user
    
    @staticmethod
    def get_user_stats(db: Session) -> Dict[str, Any]:
        """Gera estatísticas para o dashboard."""
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        
        # Agregação por cargo
        roles_count = db.query(User.role, func.count(User.role)).group_by(User.role).all()
        roles_dict = {role.value: count for role, count in roles_count}
        
        return {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
            "by_role": roles_dict
        }