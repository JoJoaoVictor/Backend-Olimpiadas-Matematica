"""Serviços de gerenciamento de usuários."""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash
from app.core.exceptions import NotFoundException, ConflictException


class UserService:
    """Serviços de usuários."""
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, current_user: User) -> User:
        """Cria novo usuário (apenas admin)."""
        # Verifica se email já existe
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ConflictException("Email já está em uso")
        
        user = User(
            name=user_data.name,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role,
            is_active=user_data.is_active,
            is_email_verified=True  # Admin pode criar verificado
        )
        
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
        """Lista usuários com filtros."""
        query = db.query(User)
        
        # Filtro de busca
        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        # Filtro por role
        if role:
            query = query.filter(User.role == role)
        
        # Filtro por status
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Busca usuário por ID."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundException("Usuário não encontrado")
        return user
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Busca usuário por email."""
        return db.query(User).filter(User.email == email).first()
      
    @staticmethod
    def update_user(
        db: Session, 
        user_id: int, 
        user_data: UserUpdate,
        current_user: User
    ) -> User:
        """Atualiza usuário."""
        user = UserService.get_user_by_id(db, user_id)
        
        # Atualiza campos fornecidos
        update_data = user_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def delete_user(db: Session, user_id: int, current_user: User) -> User:
        """Remove usuário (soft delete)."""
        user = UserService.get_user_by_id(db, user_id)
        
        # Não permite deletar própria conta
        if user.id == current_user.id:
            raise ConflictException("Não é possível deletar sua própria conta")
        
        user.is_active = False
        db.commit()
        
        return user
    
    @staticmethod
    def get_user_stats(db: Session) -> dict:
        """Estatísticas de usuários."""
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        admins = db.query(User).filter(User.role == UserRole.ADMIN).count()
        professors = db.query(User).filter(User.role == UserRole.PROFESSOR).count()
        students = db.query(User).filter(User.role == UserRole.STUDENT).count()
        verified_emails = db.query(User).filter(User.is_email_verified == True).count()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "roles": {
                "admins": admins,
                "professors": professors,
                "students": students
            },
            "verified_emails": verified_emails,
            "unverified_emails": total_users - verified_emails
        }

