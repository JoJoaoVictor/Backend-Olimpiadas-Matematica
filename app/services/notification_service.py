"""
Serviços de gerenciamento de notificações
Arquivo: app/services/notification_service.py
Responsável pela lógica de criação e manipulação de notificações.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.notification import Notification, NotificationType, EntityType
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.core.exceptions import NotFoundException


class NotificationService:
    """Serviços de notificações."""

    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        entity_type: EntityType,
        entity_id: int,
        triggered_by_user_id: int = None
    ) -> Notification:
        """
        Cria uma nova notificação.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário destinatário
            notification_type: Tipo da notificação (enum)
            title: Título da notificação
            message: Mensagem detalhada
            entity_type: Tipo de entidade (QUESTION ou EXAM)
            entity_id: ID da entidade relacionada
            triggered_by_user_id: ID do usuário que disparou a notificação (opcional)
        
        Returns:
            Notification: A notificação criada
        """
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            triggered_by_user_id=triggered_by_user_id,
            is_read=False
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        return notification

    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Obtém notificações do usuário com as não lidas primeiro.
        
        Args:
            db: Sessão do banco de dados
            user_id: ID do usuário
            limit: Limite de notificações a retornar
            offset: Número de notificações a pular
        
        Returns:
            Dict com lista de notificações, contagem de não lidas e total
        """
        # Conta total de notificações não lidas
        unread_count = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()
        
        # Conta total de notificações
        total_count = db.query(Notification).filter(
            Notification.user_id == user_id
        ).count()
        
        # Obtém notificações ordenadas: não lidas primeiro, depois por data desc
        notifications = db.query(Notification).filter(
            Notification.user_id == user_id
        ).order_by(
            Notification.is_read.asc(),  # False (0) vem antes de True (1)
            desc(Notification.created_at)
        ).offset(offset).limit(limit).all()
        
        # Converte para schema
        notifications_data = [
            NotificationResponse.from_orm(n) for n in notifications
        ]
        
        return {
            "notifications": notifications_data,
            "unread_count": unread_count,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }

    @staticmethod
    def mark_notification_as_read(
        db: Session,
        notification_id: int,
        current_user: User
    ) -> Notification:
        """
        Marca uma notificação como lida.
        
        Args:
            db: Sessão do banco de dados
            notification_id: ID da notificação
            current_user: Usuário logado (validação de ownership)
        
        Returns:
            Notification: A notificação atualizada
        
        Raises:
            NotFoundException: Se notificação não existir ou não pertencer ao usuário
        """
        notification = db.query(Notification).filter(
            Notification.id == notification_id
        ).first()
        
        if not notification:
            raise NotFoundException("Notificação não encontrada")
        
        # Valida se a notificação pertence ao usuário logado
        if notification.user_id != current_user.id:
            raise NotFoundException("Notificação não encontrada")
        
        notification.is_read = True
        db.commit()
        db.refresh(notification)
        
        return notification

    @staticmethod
    def mark_all_notifications_as_read(
        db: Session,
        current_user: User
    ) -> int:
        """
        Marca todas as notificações do usuário como lidas.
        
        Args:
            db: Sessão do banco de dados
            current_user: Usuário logado
        
        Returns:
            int: Número de notificações marcadas como lidas
        """
        # Atualiza todas as notificações não lidas do usuário
        result = db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        ).update({Notification.is_read: True})
        
        db.commit()
        
        return result

    @staticmethod
    def delete_notification(
        db: Session,
        notification_id: int,
        current_user: User
    ) -> bool:
        """
        Deleta uma notificação.
        
        Args:
            db: Sessão do banco de dados
            notification_id: ID da notificação
            current_user: Usuário logado (validação de ownership)
        
        Returns:
            bool: True se deletado, False caso contrário
        
        Raises:
            NotFoundException: Se notificação não existir ou não pertencer ao usuário
        """
        notification = db.query(Notification).filter(
            Notification.id == notification_id
        ).first()
        
        if not notification:
            raise NotFoundException("Notificação não encontrada")
        
        # Valida se a notificação pertence ao usuário logado
        if notification.user_id != current_user.id:
            raise NotFoundException("Notificação não encontrada")
        
        db.delete(notification)
        db.commit()
        
        return True
