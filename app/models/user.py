"""
Modelo de Dados: Usuário
Arquivo: app/models/user.py
Responsável por definir a tabela 'users' no banco de dados.
"""

from sqlalchemy import Column, String, Boolean, Enum, DateTime, Integer
from sqlalchemy.orm import relationship
import enum

# Importa a classe base (que geralmente contém id, created_at, updated_at)
from app.models.base import BaseModel

class UserRole(str, enum.Enum):
    """Define os níveis de acesso do sistema."""
    ADMIN = "ADMIN"
    PROFESSOR = "PROFESSOR"
    REVISOR = "REVISOR"   
    STUDENT = "STUDENT"

class User(BaseModel):
    """
    Model que representa a tabela de usuários no banco de dados.
    Herda de BaseModel (id, created_at, updated_at).
    """
    __tablename__ = "users"
      
    # ==========================
    # INFORMAÇÕES BÁSICAS
    # ==========================
    name = Column(String(100), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    
    # Armazena o hash da senha (pode ser NULL se o login for via Google)
    password_hash = Column(String(255), nullable=True)
    
    # ==========================
    # INTEGRAÇÃO OAUTH (GOOGLE)
    # ==========================
    # ID único retornado pelo Google
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    avatar_url = Column(String(500), nullable=True)
    
    # ==========================
    # PERMISSÕES E ESTADOS
    # ==========================
    # Define o papel do usuário. Cuidado com o default (aqui está PROFESSOR, mas geralmente é STUDENT)
    role = Column(Enum(UserRole), default=UserRole.PROFESSOR, nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)       # Para Soft Delete ou banimento
    is_email_verified = Column(Boolean, default=False, nullable=False) # Confirmação de email
    
    # ==========================
    # SEGURANÇA E LOGIN
    # ==========================
    login_attempts = Column(Integer, default=0)       # Contador para bloquear força bruta
    locked_until = Column(DateTime, nullable=True)    # Data/hora até quando a conta está bloqueada
    last_login = Column(DateTime, nullable=True)      # Último acesso registrado
    
    # ==========================
    # TOKENS DE RECUPERAÇÃO
    # ==========================
    email_verification_token = Column(String(255), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # ==========================
    # RELACIONAMENTOS (SQLAlchemy)
    # ==========================
    # string "Question" e "Exam" são usadas para evitar erros de importação circular
    questions = relationship("Question", back_populates="author")
    exams = relationship("Exam", back_populates="author")
    
    # ==========================
    # PROPRIEDADES VIRTUAIS (Helpers)
    # ==========================
    
    @property
    def has_password(self) -> bool:
        """
        Retorna True se o usuário tiver uma senha definida localmente.
        Retorna False se for usuário apenas Google (sem senha).
        Utilizado pelo Frontend para ocultar o campo 'Senha Atual'.
        """
        return bool(self.password_hash)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"