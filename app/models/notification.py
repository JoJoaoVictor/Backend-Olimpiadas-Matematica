"""
Modelo de Dados: Notificação
Arquivo: app/models/notification.py
Responsável por definir a tabela 'notifications' no banco de dados.
Armazena notificações para usuários sobre alterações em questões e provas.
"""

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class NotificationType(str, enum.Enum):
    """Tipos de notificações disponíveis."""
    QUESTION_REVISED = "QUESTION_REVISED"       # Questão foi revisada por REVISOR/ADMIN
    EXAM_REVISED = "EXAM_REVISED"               # Prova foi revisada por REVISOR/ADMIN
    QUESTION_APPROVED = "QUESTION_APPROVED"     # Questão foi aprovada
    QUESTION_COMMENTED = "QUESTION_COMMENTED"  # Questão recebeu comentário de revisão
    EXAM_COMMENTED = "EXAM_COMMENTED"          # Prova recebeu comentário de revisão


class EntityType(str, enum.Enum):
    """Tipo de entidade associada à notificação."""
    QUESTION = "QUESTION"
    EXAM = "EXAM"


class Notification(BaseModel):
    """
    Model que representa a tabela de notificações no banco de dados.
    Armazena notificações para notificar usuários sobre alterações.
    """
    __tablename__ = "notifications"

    # ==========================
    # RELACIONAMENTO
    # ==========================
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User", foreign_keys=[user_id])
    
    triggered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    triggered_by_user = relationship("User", foreign_keys=[triggered_by_user_id])

    # ==========================
    # CONTEÚDO DA NOTIFICAÇÃO
    # ==========================
    type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # ==========================
    # ENTIDADE RELACIONADA
    # ==========================
    entity_type = Column(SQLEnum(EntityType), nullable=False, index=True)  # QUESTION ou EXAM
    entity_id = Column(Integer, nullable=False, index=True)  # ID da questão ou prova

    # ==========================
    # STATUS
    # ==========================
    is_read = Column(Boolean, default=False, nullable=False, index=True)

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type='{self.type.value}')>"
