"""
Rotas de Notificações
Arquivo: app/api/v1/notifications.py
Endpoints para gerenciar notificações do usuário.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.notification_service import NotificationService
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.core.exceptions import AppException

router = APIRouter()


@router.get("", response_model=dict)
async def list_notifications(
    limit: int = Query(50, ge=1, le=100, description="Limite de notificações"),
    offset: int = Query(0, ge=0, description="Offset para paginação"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista notificações do usuário logado.
    Notificações não lidas aparecem primeiro, ordenadas por data descendente.
    """
    try:
        result = NotificationService.get_user_notifications(
            db=db,
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        
        return {
            "success": True,
            "data": result
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar notificações: {str(e)}"
        )


@router.patch("/{notification_id}/read", response_model=dict)
async def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marca uma notificação como lida.
    """
    try:
        notification = NotificationService.mark_notification_as_read(
            db=db,
            notification_id=notification_id,
            current_user=current_user
        )
        
        return {
            "success": True,
            "message": "Notificação marcada como lida",
            "data": {"notification": NotificationResponse.from_orm(notification)}
        }
    
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao marcar notificação como lida: {str(e)}"
        )


@router.patch("/read-all", response_model=dict)
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marca todas as notificações do usuário como lidas.
    """
    try:
        count = NotificationService.mark_all_notifications_as_read(
            db=db,
            current_user=current_user
        )
        
        return {
            "success": True,
            "message": f"{count} notificação(ões) marcada(s) como lida(s)",
            "data": {"count": count}
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao marcar notificações como lidas: {str(e)}"
        )
