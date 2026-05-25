"""
Rotas de usuários (Endpoints).
Arquivo: app/api/v1/users.py
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

# --- DEPENDÊNCIAS E UTILS ---
from app.core.security import get_password_hash, verify_password
from app.database import get_db
from app.dependencies import (
    get_admin_user,
    get_current_active_user,
    get_current_user,
)
# --- MODELS E SCHEMAS ---
from app.models.user import User, UserRole
from app.models.user_profile import UserProfile
from app.models.question import Question  # 🌟 Importado para calcular as estatísticas reais

# Nota: Se o seu modelo de Provas estiver em outro local, ajuste o import abaixo.
try:
    from app.models.exam import Exam  # 🌟 Ajuste o caminho se necessário
except ImportError:
    Exam = None

from app.schemas.user import (
    ChangePassword,
    UserCreate,
    UserResponse,
    UserRoleUpdate,
    UserUpdate,
    UserUpdateProfile,
)
from app.services.user_service import UserService

router = APIRouter()

# ==============================================================================
# ROTAS DO PRÓPRIO USUÁRIO (PERFIL & SEGURANÇA)
# ==============================================================================

@router.get("/me", response_model=dict)
async def read_users_me(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Retorna os dados do usuário logado atualmente com o perfil carregado."""
    user_with_profile = (
        db.query(User)
        .options(joinedload(User.profile))
        .filter(User.id == current_user.id)
        .first()
    )

    return {
        "success": True,
        "data": UserResponse.from_orm(user_with_profile or current_user),
    }


@router.put("/me", response_model=dict)
async def update_user_me(
    user_data: dict,  # Aceita o JSON flexível enviado pelo React
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Atualiza dados básicos (nome, avatar) e dados do perfil acadêmico de forma íntegra.
    Delega a geolocalização do Campus -> Cidade para a camada de serviço.
    """
    user_updated = UserService.update_user_profile(
        db=db, user_id=current_user.id, user_data=user_data
    )

    return {
        "success": True,
        "message": "Perfil updated com sucesso",
        "data": UserResponse.from_orm(user_updated),
    }


@router.post("/change-password", response_model=dict)
async def change_password(
    password_data: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Permite que o usuário logado altere sua própria senha."""
    if current_user.password_hash:
        if not password_data.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Por favor, informe sua senha atual.",
            )

        if not verify_password(
            password_data.current_password, current_user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A senha atual está incorreta.",
            )

        if password_data.current_password == password_data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A nova senha deve ser diferente da atual.",
            )

    current_user.password_hash = get_password_hash(password_data.new_password)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {"success": True, "message": "Senha definida com sucesso."}

#=============================================================================
# ROTA PARA ACEITAR TERMOS DE USO (LGPD)
#=============================================================================

@router.post("/accept-terms", response_model=dict)
async def accept_user_terms(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Registra que o usuário aceitou os Termos de Uso e Política de Privacidade.
    Garante a conformidade com a LGPD e impede que o overlay apareça novamente.
    """
    # Se o campo estiver direto na tabela User:
    current_user.accepted_terms = True
    
    # Se o campo estiver na tabela UserProfile, descomente a linha abaixo:
    # if current_user.profile:
    #     current_user.profile.accepted_terms = True

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "message": "Termos aceitos com sucesso.",
        "data": {
            "accepted_terms": True
        }
    }

# ==============================================================================
# ROTAS ADMINISTRATIVAS (GERENCIAMENTO)
# ==============================================================================

@router.get("", response_model=dict)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_admin_user),  # Apenas Admin
    db: Session = Depends(get_db),
):
    """Lista usuários com paginação e filtros (Apenas Admin)."""
    query = db.query(User).options(joinedload(User.profile))

    if search:
        query = query.filter(
            User.email.contains(search) | User.name.contains(search)
        )
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    total = query.count()
    users = query.offset(skip).limit(limit).all()

    return {
        "success": True,
        "data": {
            "users": [UserResponse.from_orm(user) for user in users],
            "total": total,
            "skip": skip,
            "limit": limit,
        },
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Cria novo usuário manualmente (Apenas Admin)."""
    user_exists = db.query(User).filter(User.email == user_data.email).first()
    if user_exists:
        raise HTTPException(
            status_code=400, detail="Este email já está cadastrado."
        )

    new_user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=get_password_hash(user_data.password),
        role=user_data.role or UserRole.STUDENT,
        is_active=True,
    )

    db.add(new_user)
    db.commit()

    db.refresh(new_user)
    user_with_profile = (
        db.query(User)
        .options(joinedload(User.profile))
        .filter(User.id == new_user.id)
        .first()
    )

    return {
        "success": True,
        "message": "Usuário criado com sucesso",
        "data": {"user": UserResponse.from_orm(user_with_profile or new_user)},
    }


@router.get("/stats/summary", response_model=dict)
async def get_user_stats(
    current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)
):
    """Retorna estatísticas gerais do sistema (Apenas Admin)."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()

    roles_count = (
        db.query(User.role, func.count(User.role)).group_by(User.role).all()
    )
    roles_dict = {role.value: count for role, count in roles_count}

    return {
        "success": True,
        "data": {
            "stats": {
                "total": total_users,
                "active": active_users,
                "by_role": roles_dict,
            }
        },
    }


@router.get("/{user_id}/stats", response_model=dict)
async def get_individual_user_stats(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
     NOVA ROTA: Retorna a produção real isolada de um único usuário.
    """
    user_exists = db.query(User).filter(User.id == user_id).first()
    if not user_exists:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Filtra estritamente pelo ID do autor da questão
    questions_count = db.query(Question).filter(Question.author_id == user_id).count()

    # Filtra estritamente pelo criador das provas (Exam)
    exams_count = 0
    if Exam is not None:
        try:
            # Se no seu modelo Exam o campo criador for 'author_id' ou 'user_id', ajuste aqui:
            exams_count = db.query(Exam).filter(Exam.author_id == user_id).count()
        except Exception:
            exams_count = 0

    return {
        "success": True,
        "data": {
            "questionsTotal": questions_count,
            "examsTotal": exams_count
        }
    }


@router.get("/{user_id}", response_model=dict)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Busca usuário por ID."""
    user = (
        db.query(User)
        .options(joinedload(User.profile))
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return {"success": True, "data": {"user": UserResponse.from_orm(user)}}


@router.patch("/{user_id}", response_model=dict)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Atualiza dados gerais de um usuário específico (Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if user_data.name is not None:
        user.name = user_data.name
    if user_data.email is not None:
        if user_data.email != user.email:
            exists = (
                db.query(User).filter(User.email == user_data.email).first()
            )
            if exists:
                raise HTTPException(
                    status_code=400, detail="Email já em uso por outro usuário."
                )
        user.email = user_data.email
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.role is not None:
        user.role = user_data.role

    db.commit()

    user_updated = (
        db.query(User)
        .options(joinedload(User.profile))
        .filter(User.id == user_id)
        .first()
    )

    return {
        "success": True,
        "message": "Usuário atualizado com sucesso",
        "data": {"user": UserResponse.from_orm(user_updated)},
    }


@router.put("/{user_id}/role", response_model=dict)
async def change_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Altera especificamente o cargo de um usuário (Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    user.role = role_data.role
    db.commit()

    user_updated = (
        db.query(User)
        .options(joinedload(User.profile))
        .filter(User.id == user_id)
        .first()
    )

    return {
        "success": True,
        "message": "Cargo atualizado com sucesso",
        "data": {"user": UserResponse.from_orm(user_updated)},
    }


@router.delete("/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Hard Delete: Remove o registro do banco de dados definitivamente."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    try:
        db.delete(user)
        db.commit()

        return {
            "success": True,
            "message": "Usuário removido permanentemente do sistema.",
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "Não é possível apagar este usuário pois ele possui registros vinculados "
                "(questões, exames, etc). Remova os vínculos antes de apagar."
            ),
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"Erro ao tentar remover usuário: {str(e)}"
        )