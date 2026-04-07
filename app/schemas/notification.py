"""
Schemas para Notificações
Arquivo: app/schemas/notification.py
DTOs para requisições e respostas de notificações.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.notification import NotificationType, EntityType
from app.schemas.base import TimestampedSchema


class NotificationBase(BaseModel):
    """Schema base para notificação."""
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)
    entity_type: EntityType
    entity_id: int = Field(..., gt=0)
    is_read: bool = Field(default=False)


class NotificationCreate(BaseModel):
    """Schema para criar notificação (uso interno)."""
    user_id: int = Field(..., gt=0)
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)
    entity_type: EntityType
    entity_id: int = Field(..., gt=0)


class NotificationResponse(TimestampedSchema):
    """Schema para resposta de notificação."""
    user_id: int
    type: NotificationType
    title: str
    message: str
    entity_type: EntityType
    entity_id: int
    is_read: bool


class NotificationListResponse(BaseModel):
    """Schema para listagem de notificações."""
    notifications: list[NotificationResponse]
    unread_count: int
    total_count: int
