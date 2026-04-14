"""
Modelo de Dados: Notificação
Arquivo: app/models/notification.py
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class NotificationType(str, enum.Enum):
    QUESTION_REVISED   = "QUESTION_REVISED"
    EXAM_REVISED       = "EXAM_REVISED"
    QUESTION_APPROVED  = "QUESTION_APPROVED"
    QUESTION_COMMENTED = "QUESTION_COMMENTED"
    EXAM_COMMENTED     = "EXAM_COMMENTED"


class EntityType(str, enum.Enum):
    QUESTION = "QUESTION"
    EXAM     = "EXAM"


class Notification(BaseModel):
    __tablename__ = "notifications"

    # CASCADE: quando o destinatário é deletado, suas notificações somem junto.
    # Notificações são pessoais — sem o usuário não fazem sentido.
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user = relationship("User", foreign_keys=[user_id])

    # SET NULL: se quem disparou a notificação for deletado, o campo vira NULL
    # mas a notificação permanece visível para o destinatário.
    triggered_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    triggered_by_user = relationship("User", foreign_keys=[triggered_by_user_id])

    type        = Column(SQLEnum(NotificationType), nullable=False, index=True)
    title       = Column(String(200), nullable=False)
    message     = Column(Text,        nullable=False)
    entity_type = Column(SQLEnum(EntityType), nullable=False, index=True)
    entity_id   = Column(Integer, nullable=False, index=True)
    is_read     = Column(Boolean, default=False, nullable=False, index=True)

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type='{self.type.value}')>"