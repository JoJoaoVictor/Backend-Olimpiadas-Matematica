"""
Modelo de Dados: Usuário
Arquivo: app/models/user.py
Responsável por definir a tabela 'users' no banco de dados.
"""

from sqlalchemy import Column, String, Boolean, Enum, DateTime, Integer
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class UserRole(str, enum.Enum):
    """Define os níveis de acesso do sistema."""
    ADMIN     = "ADMIN"
    PROFESSOR = "PROFESSOR"
    REVISOR   = "REVISOR"
    STUDENT   = "STUDENT"


class User(BaseModel):
    __tablename__ = "users"
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    # ==========================
    # INFORMAÇÕES BÁSICAS
    # ==========================
    name          = Column(String(100), nullable=False, index=True)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)

    # ==========================
    # INTEGRAÇÃO OAUTH (GOOGLE)
    # ==========================
    google_id  = Column(String(255), unique=True, nullable=True, index=True)
    avatar_url = Column(String(500), nullable=True)

    # ==========================
    # PERMISSÕES E ESTADOS
    # ==========================
    role              = Column(Enum(UserRole), default=UserRole.PROFESSOR, nullable=False)
    is_active         = Column(Boolean, default=True,  nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)

    # ==========================
    # SEGURANÇA E LOGIN
    # ==========================
    login_attempts = Column(Integer,  default=0)
    locked_until   = Column(DateTime, nullable=True)
    last_login     = Column(DateTime, nullable=True)

    # ==========================
    # TOKENS DE RECUPERAÇÃO
    # ==========================
    email_verification_token = Column(String(255), nullable=True)
    password_reset_token     = Column(String(255), nullable=True)
    password_reset_expires   = Column(DateTime,    nullable=True)

    # ==========================
    # RELACIONAMENTOS
    # ==========================

    # ── questions ────────────────────────────────────────────────────────────
    # ANTES: relationship("Question", back_populates="author")
    # PROBLEMA: com a nova coluna reviewed_by_id também apontando para users.id,
    # o SQLAlchemy não sabe qual das duas FKs usar para este relacionamento e
    # levanta AmbiguousForeignKeysError ao iniciar o servidor.
    # CORREÇÃO: foreign_keys explícito usando string — resolve a ambiguidade
    # sem precisar importar Question diretamente (evita import circular).
    questions = relationship(
        "Question",
        foreign_keys="Question.author_id",
        back_populates="author"
    )

    # ── reviewed_questions ────────────────────────────────────────────────────
    # NOVO: questões que este usuário revisou (reviewed_by_id = self.id).
    # Usado pelo question_service para filtrar a listagem do REVISOR:
    # cada revisor vê apenas as questões que ele próprio tocou.
    reviewed_questions = relationship(
        "Question",
        foreign_keys="Question.reviewed_by_id",
        back_populates="reviewer"
    )

    # ── exams ─────────────────────────────────────────────────────────────────
    exams = relationship("Exam", back_populates="author")

    # ── notifications ─────────────────────────────────────────────────────────
    # Mantido exatamente como estava no seu arquivo original.
    notifications = relationship(
        "Notification",
        foreign_keys="Notification.user_id",
        cascade="all, delete-orphan"
    )

    # ── profile ───────────────────────────────────────────────────────────────
    # Relacionamento 1:1 com UserProfile (campus, CPF, matrícula, etc).
    # uselist=False garante que user.profile retorne um objeto, não uma lista.
    # cascade="all, delete-orphan" apaga o perfil quando o usuário for removido.
    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined"
    )

    # ==========================
    # PROPRIEDADES VIRTUAIS
    # ==========================

    @property
    def has_password(self) -> bool:
        """True se o usuário tiver senha local (não apenas Google)."""
        return bool(self.password_hash)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"