from sqlalchemy import Column, String, Boolean, Enum, DateTime, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    PROFESSOR = "PROFESSOR"
    REVISOR = "REVISOR"  
    STUDENT = "STUDENT"


class User(BaseModel):
    """Model para usuários do sistema."""
    __tablename__ = "users"
     
    # Informações básicas
    name = Column(String(100), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    
    # OAuth
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Permissões e status
    role = Column(Enum(UserRole), default=UserRole.PROFESSOR, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    
    # Controle de segurança
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    
    # Tokens de recuperação
    email_verification_token = Column(String(255), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # Relacionamentos
    questions = relationship("Question", back_populates="author")
    exams = relationship("Exam", back_populates="author")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"