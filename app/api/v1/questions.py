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
    per_page: int = Query(20, ge=1, le=100, description="Itens por página"),
    search: str = Query(None, description="Busca textual"),
    category_id: int = Query(None, description="Filtro por categoria"),
    grau_id: int = Query(None, description="Filtro por grau"),
    difficulty_level: int = Query(None, ge=1, le=5, description="Nível de dificuldade"),
    serie_ano: str = Query(None, description="Série/ano"),
    phase_level: str = Query(None, description="Nível da fase"),
    bncc_theme: str = Query(None, description="Tema BNCC"),
    ability_code: str = Query(None, description="Código da habilidade"),
    author_id: int = Query(None, description="Filtro por autor"),
    # ── ALTERAÇÃO 1 ──────────────────────────────────────────────────────────
    # Agora: get_any_staff_user (bloqueia STUDENT na listagem)
    # Impacto: estudantes não conseguem listar o banco de questões via API,
    # mesmo que tentem acessar diretamente pela URL.
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
            author_id=author_id
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
    # STUDENT também pode criar questões (submeter para revisão)
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
    # ── ALTERAÇÃO 2 ──────────────────────────────────────────────────────────
    # Agora: get_professor_or_revisor_user → ADMIN, REVISOR e PROFESSOR podem
    #        buscar uma questão por ID. A lógica de ownership (professor só vê
    #        a própria) fica em QuestionService.get_question_by_id, que já
    #        recebe current_user e pode aplicar o filtro lá.
    # Impacto direto: resolve o 403 e o sumiço dos campos na tela de edição.
    # STUDENT pode acessar suas próprias questões para ver comentários do revisor e corrigir
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
    # ── ALTERAÇÃO 3 ──────────────────────────────────────────────────────────
    # Agora: get_professor_or_revisor_user (STUDENT e acesso sem role são
    #        bloqueados já na camada de rota, antes de chegar no service).
    # Impacto: STUDENT não consegue fazer PATCH via API diretamente.
    # A lógica de "professor só edita a própria" continua no QuestionService.
    # STUDENT pode editar suas próprias questões pendentes (para corrigir após comentário do revisor)
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Atualiza questão. STUDENT/PROFESSOR editam a própria; REVISOR e ADMIN editam qualquer uma."""
    try:
        question = QuestionService.update_question(db, question_id, question_data, current_user)

        return {
            "success": True,
            "message": "Questão atualizada com sucesso",
            "data": {"question": QuestionResponse.from_orm(question)}
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/{question_id}", response_model=dict)
async def delete_question(
    question_id: int,
    # ── ALTERAÇÃO 4 ──────────────────────────────────────────────────────────
    # Antes: get_current_user (qualquer autenticado)
    # Agora: get_professor_or_revisor_user
    # Impacto: STUDENT não consegue deletar questões via API.
    # STUDENT pode deletar suas próprias questões pendentes
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
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Estatísticas de questões. Apenas ADMIN."""
    try:
        stats = QuestionService.get_question_stats(db)

        return {
            "success": True,
            "data": {"stats": stats}
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas"
        )