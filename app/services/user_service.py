"""
Serviços de gerenciamento de usuários (Lógica de Negócio).
Este arquivo contém as funções que acessam o banco de dados diretamente.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserRoleUpdate
from app.core.security import get_password_hash
from app.core.exceptions import NotFoundException, ConflictException

class UserService:
    """Classe contendo toda a lógica de manipulação de usuários."""
    
    @staticmethod
    def create_user(db: Session, user_data: UserCreate, current_user: User) -> User:
        """
        Cria novo usuário (Apenas Admin).
        Verifica se o email já existe antes de criar.
        """
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ConflictException("Email já está em uso")
        
        user = User(
            name=user_data.name,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role,
            is_active=user_data.is_active,
            is_email_verified=True # Assumimos verificado se criado por Admin
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
        """
        Lista usuários aplicando filtros de busca.
        - Se is_active for True: Traz apenas os ativos.
        - Se is_active for False: Traz apenas os inativos (excluídos).
        - Se is_active for None: Traz TODOS.
        """
        query = db.query(User)
        
        # Filtro de busca (Nome ou Email)
        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        # Filtro de Cargo
        if role:
            query = query.filter(User.role == role)
        
        # Filtro de Status (Ativo/Inativo)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Busca usuário por ID ou lança erro 404 se não achar."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundException("Usuário não encontrado")
        return user
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Busca usuário por email (usado no login)."""
        return db.query(User).filter(User.email == email).first()
      
    @staticmethod
    def update_user(
        db: Session, 
        user_id: int, 
        user_data: UserUpdate,
        current_user: User
    ) -> User:
        """Atualiza dados gerais do usuário (Nome, Email, etc)."""
        user = UserService.get_user_by_id(db, user_id)
        
        # Converte o schema para dict, ignorando campos que não foram enviados
        update_data = user_data.dict(exclude_unset=True)
        
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
        Segurança: Admin não pode rebaixar a si mesmo.
        """
        user = UserService.get_user_by_id(db, user_id)
        
        # Evita que o admin mude o próprio cargo e perca acesso acidentalmente
        if user.id == current_user.id:
             raise ConflictException("Você não pode alterar seu próprio cargo nesta rota.")

        user.role = role_data.role
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def delete_user(db: Session, user_id: int, current_user: User) -> User:
        """
        Remove usuário.
        CONFIGURAÇÃO ATUAL: HARD DELETE (Apaga do Banco).
        """
        user = UserService.get_user_by_id(db, user_id)
        
        # Segurança: Ninguém pode deletar a si mesmo
        if user.id == current_user.id:
            raise ConflictException("Não é possível deletar sua própria conta")
        
        # --- MUDANÇA FEITA AQUI ---
        
        # 1. Soft Delete (Desativado)
        # user.is_active = False 
        
        # 2. Hard Delete (ATIVADO)
        db.delete(user) 
        
        # --------------------------
        
        db.commit()
        
        return user
    
    @staticmethod
    def get_user_stats(db: Session) -> dict:
        """Gera estatísticas para o dashboard administrativo."""
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