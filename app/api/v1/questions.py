"""Rotas de questões."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_admin_user,
    get_professor_user,
    get_professor_or_revisor_user,
    get_any_staff_user
)
from app.models.user import User
from app.schemas.question import (
    QuestionCreate, QuestionUpdate, QuestionResponse,
    QuestionListResponse, QuestionFilters
)
from app.services.question_service import QuestionService
from app.core.exceptions import AppException

router = APIRouter()


@router.get("", response_model=dict)
async def list_questions(
    page: int = Query(1, ge=1, description="Página"),
    # 🌟 CORREÇÃO 1: Alterado le=100 para le=1000
    per_page: int = Query(20, ge=1, le=1000, description="Itens por página"),
    search: str = Query(None, description="Busca textual"),
    category_id: int = Query(None, description="Filtro por categoria"),
    grau_id: int = Query(None, description="Filtro por grau"),
    difficulty_level: int = Query(None, ge=1, le=5, description="Nível de dificuldade"),
    serie_ano: str = Query(None, description="Série/ano"),
    phase_level: str = Query(None, description="Nível da fase"),
    bncc_theme: str = Query(None, description="Tema BNCC"),
    ability_code: str = Query(None, description="Código da habilidade"),
    author_id: int = Query(None, description="Filtro por autor"),
    # 🌟 CORREÇÃO 2: Adicionado o novo parâmetro enviado pelo Frontend
    only_approved_applied: bool = Query(None, description="Filtrar apenas aprovadas e aplicadas"),
    
    current_user: User = Depends(get_current_user),  
    db: Session = Depends(get_db)
):
    """Lista questões com filtros."""
    try:
        filters = QuestionFilters(
            page=page,
            per_page=per_page,
            search=search,
            category_id=category_id,
            grau_id=grau_id,
            difficulty_level=difficulty_level,
            serie_ano=serie_ano,
            phase_level=phase_level,
            bncc_theme=bncc_theme,
            ability_code=ability_code,
            author_id=author_id,
            # 🌟 CORREÇÃO 3: Injetado no schema que vai para o Service
            only_approved_applied=only_approved_applied
        )

        result = QuestionService.get_questions(db, filters, current_user)

        return {
            "success": True,
            "data": result
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_question(
    question_data: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cria nova questão. Qualquer usuário autenticado pode submeter."""
    try:
        question = QuestionService.create_question(db, question_data, current_user)

        return {
            "success": True,
            "message": "Questão criada com sucesso",
            "data": {"question": QuestionResponse.from_orm(question)}
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/{question_id}", response_model=dict)
async def get_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Busca questão por ID. STUDENT vê a própria; REVISOR e ADMIN veem qualquer uma."""
    try:
        question = QuestionService.get_question_by_id(db, question_id, current_user)

        return {
            "success": True,
            "data": {"question": QuestionResponse.from_orm(question)}
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/{question_id}", response_model=dict)
async def update_question(
    question_id: int,
    question_data: QuestionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Atualiza questão. STUDENT/PROFESSOR editam a própria; REVISOR e ADMIN editam qualquer uma."""
    try:
        question = QuestionService.update_question(db, question_id, question_data, current_user)

        return {
            "success": True,
            "message": "Questão updated com sucesso",
            "data": {"question": QuestionResponse.from_orm(question)}
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/{question_id}", response_model=dict)
async def delete_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove questão. STUDENT/PROFESSOR removem a própria; REVISOR e ADMIN removem qualquer uma."""
    try:
        QuestionService.delete_question(db, question_id, current_user)

        return {
            "success": True,
            "message": "Questão removida com sucesso"
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/{question_id}/approve", response_model=dict)
async def approve_question(
    question_id: int,
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    """Aprova questão. Apenas REVISOR, PROFESSOR e ADMIN."""
    try:
        question = QuestionService.approve_question(db, question_id, current_user)

        return {
            "success": True,
            "message": "Questão aprovada com sucesso",
            "data": {"question": QuestionResponse.from_orm(question)}
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/stats/summary", response_model=dict)
async def get_question_stats(
    current_user: User = Depends(get_any_staff_user),
    db: Session = Depends(get_db)
):
    """Estatísticas de questões filtradas por permissão."""
    try:
        stats = QuestionService.get_question_stats(db, current_user)

        return {
            "success": True,
            "data": {"stats": stats}
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas"
        )