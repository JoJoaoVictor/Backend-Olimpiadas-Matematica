"""Rotas de provas."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user, get_professor_user
from app.models.user import User
from app.models.exam import ExamStatus
from app.schemas.exam import (
    ExamCreate, ExamUpdate, ExamResponse, ExamListResponse,
    ExamFilters, ExamQuestionUpdate, ExamPDFRequest
)
from app.services.exam_service import ExamService
from app.services.pdf_service import PDFService
from app.core.exceptions import AppException

router = APIRouter()
 

@router.get("", response_model=dict)
async def list_exams(
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(20, ge=1, le=100, description="Itens por página"),
    search: str = Query(None, description="Busca textual"),
    status: ExamStatus = Query(None, description="Filtro por status"),
    fase: str = Query(None, description="Filtro por fase"),
    anos: list = Query(None, description="Filtro por anos"),
    author_id: int = Query(None, description="Filtro por autor (admin apenas)"),
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Lista provas com filtros."""
    try:
        filters = ExamFilters(
            page=page,
            per_page=per_page,
            search=search,
            status=status,
            fase=fase,
            anos=anos,
            author_id=author_id
        )
        
        result = ExamService.get_exams(db, filters, current_user)
        
        return {
            "success": True,
            "data": result
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Cria nova prova."""
    try:
        exam = ExamService.create_exam(db, exam_data, current_user)
        
        return {
            "success": True,
            "message": "Prova criada com sucesso",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/{exam_id}", response_model=dict)
async def get_exam(
    exam_id: int,
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Busca prova por ID."""
    try:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        return {
            "success": True,
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/{exam_id}", response_model=dict)
async def update_exam(
    exam_id: int,
    exam_data: ExamUpdate,
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Atualiza prova."""
    try:
        exam = ExamService.update_exam(db, exam_id, exam_data, current_user)
        
        return {
            "success": True,
            "message": "Prova atualizada com sucesso",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/{exam_id}/questions", response_model=dict)
async def update_exam_questions(
    exam_id: int,
    questions_data: ExamQuestionUpdate,
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Atualiza questões da prova."""
    try:
        exam = ExamService.update_exam_questions(db, exam_id, questions_data, current_user)
        
        return {
            "success": True,
            "message": "Questões da prova atualizadas com sucesso",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/{exam_id}", response_model=dict)
async def delete_exam(
    exam_id: int,
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Remove prova."""
    try:
        exam = ExamService.delete_exam(db, exam_id, current_user)
        
        return {
            "success": True,
            "message": "Prova removida com sucesso"
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/{exam_id}/status", response_model=dict)
async def change_exam_status(
    exam_id: int,
    new_status: ExamStatus,
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Altera status da prova."""
    try:
        exam = ExamService.change_exam_status(db, exam_id, new_status, current_user)
        
        return {
            "success": True,
            "message": f"Status da prova alterado para {new_status.value}",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/{exam_id}/pdf")
async def generate_exam_pdf(
    exam_id: int,
    include_answers: bool = Query(False, description="Incluir respostas"),
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Gera PDF da prova."""
    try:
        # Busca prova e questões
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        # Busca questões ordenadas
        questions = []
        for exam_question in sorted(exam.exam_questions, key=lambda x: x.order_index):
            questions.append(exam_question.question)
        
        # Configura PDF
        pdf_request = ExamPDFRequest(
            include_answers=include_answers,
            cover_info={
                "logo_path": None,
                "institution": "Olimpíadas de Matemática"
            }
        )
        
        # Gera PDF
        pdf_buffer = PDFService.generate_exam_pdf(exam, questions, pdf_request)
        
        # Nome do arquivo
        filename = f"prova_{exam.name.replace(' ', '_').lower()}.pdf"
        
        return StreamingResponse(
            BytesIO(pdf_buffer.read()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro na geração do PDF"
        )


@router.get("/stats/summary", response_model=dict)
async def get_exam_stats(
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Estatísticas de provas."""
    try:
        stats = ExamService.get_exam_stats(db, current_user)
        
        return {
            "success": True,
            "data": {"stats": stats}
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas"
        )

