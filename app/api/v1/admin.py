"""Rotas administrativas."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_admin_user
from app.models.user import User
from app.models.question import Question
from app.models.exam import Exam
from app.models.category import Category
from app.models.grau import Grau

router = APIRouter()


@router.get("/dashboard", response_model=dict)
async def get_admin_dashboard(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Dashboard administrativo."""
    try:
        # Estatísticas gerais
        total_users = db.query(User).count()
        total_questions = db.query(Question).count()
        total_exams = db.query(Exam).count()
        
        # Usuários por role
        users_by_role = dict(
            db.query(User.role, func.count(User.id))
            .group_by(User.role)
            .all()
        )
        
        # Questões por categoria
        questions_by_category = dict(
            db.query(Category.name, func.count(Question.id))
            .join(Question, Category.id == Question.category_id)
            .group_by(Category.name)
            .all()
        )
        
        # Questões por dificuldade
        questions_by_difficulty = dict(
            db.query(Question.difficulty_level, func.count(Question.id))
            .group_by(Question.difficulty_level)
            .all()
        )
        
        # Provas por status
        exams_by_status = dict(
            db.query(Exam.status, func.count(Exam.id))
            .group_by(Exam.status)
            .all()
        )
        
        # Usuários ativos (últimos 30 dias)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users = db.query(User).filter(
            User.last_login >= thirty_days_ago
        ).count()
        
        dashboard_data = {
            "general_stats": {
                "total_users": total_users,
                "total_questions": total_questions,
                "total_exams": total_exams,
                "active_users": active_users
            },
            "users_by_role": {str(k): v for k, v in users_by_role.items()},
            "questions_by_category": questions_by_category,
            "questions_by_difficulty": {str(k): v for k, v in questions_by_difficulty.items()},
            "exams_by_status": {str(k): v for k, v in exams_by_status.items()}
        }
         
        return {
            "success": True,
            "data": dashboard_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao carregar dashboard"
        )


@router.get("/system-info", response_model=dict)
async def get_system_info(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Informações do sistema."""
    try:
        import psutil
        import platform
        from datetime import datetime
        
        system_info = {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor()
            },
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            },
            "cpu": {
                "count": psutil.cpu_count(),
                "percent": psutil.cpu_percent(interval=1)
            },
            "uptime": str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())),
            "python_version": platform.python_version()
        }
        
        return {
            "success": True,
            "data": system_info
        }
        
    except Exception as e:
        # Se psutil não estiver disponível, retorna info básica
        import platform
        
        basic_info = {
            "platform": {
                "system": platform.system(),
                "python_version": platform.python_version()
            }
        }
        
        return {
            "success": True,
            "data": basic_info
        }


@router.post("/maintenance", response_model=dict)
async def toggle_maintenance_mode(
    enabled: bool,
    current_user: User = Depends(get_admin_user)
):
    """Ativa/desativa modo de manutenção."""
    # TODO: Implementar modo de manutenção
    return {
        "success": True,
        "message": f"Modo de manutenção {'ativado' if enabled else 'desativado'}",
        "data": {"maintenance_mode": enabled}
    }

