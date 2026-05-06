"""Rotas de provas."""
from sqlalchemy.orm import joinedload
import logging
from typing import List, Optional
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_professor_user,
    get_professor_or_revisor_user,
    get_admin_user
)
from app.models.user import User
from app.models.exam import ExamStatus
from app.schemas.exam import (
    ExamCreate,
    ExamUpdate,
    ExamResponse,
    ExamFilters,
    ExamQuestionUpdate,
    ExamPDFRequest,
    ExamLayoutUpdate,
)
from app.services.exam_service import ExamService
from app.services.pdf_service import PDFService
from app.core.exceptions import AppException, ValidationException
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=dict)
async def list_exams(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[ExamStatus] = Query(None),
    fase: Optional[str] = Query(None),
    anos: Optional[List[str]] = Query(None),
    author_id: Optional[int] = Query(None),
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    try:
        filters = ExamFilters(
            page=page, per_page=per_page, search=search,
            status=status, fase=fase, anos=anos, author_id=author_id
        )
        result = ExamService.get_exams(db, filters, current_user)
        return {"success": True, "data": result}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Recebido payload para criar prova: {exam_data.dict()}")
        exam = ExamService.create_exam(db, exam_data, current_user)
        return {
            "success": True,
            "message": "Prova criada com sucesso",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
    except AppException as e:
        logger.info(f"Erro ao criar prova: {e.detail}")
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/generate_pdf")
async def generate_pdf_from_payload(
    payload: dict,
    db: Session = Depends(get_db)
):
    """Gera PDF a partir de payload JSON enviado pelo frontend."""
    try:
        name         = payload.get("name", "Prova Sem Título")
        raw_fase      = payload.get("fase", "")
        raw_anos      = payload.get("anos", [])
        raw_questions = payload.get("questoes", [])
        ano_prova     = payload.get("ano", None) or __import__("datetime").datetime.now().year

        # Normaliza anos: pode vir como string única ou lista de labels do react-select
        # Exemplos: "4º Fundamental", ["4º Fundamental", "5º Fundamental"], ["1º Médio"]
        if isinstance(raw_anos, str):
            anos_lista = [raw_anos] if raw_anos.strip() else []
        elif isinstance(raw_anos, list):
            anos_lista = [str(a).strip() for a in raw_anos if a and str(a).strip()]
        else:
            anos_lista = []

        # Normaliza fase: pode vir como value do select ("1","2","Final") ou label ("Fase 1")
        fase = raw_fase if raw_fase else ""

        logger.info(f"📦 Gerando PDF para prova '{name}' com {len(raw_questions)} questões")

        formatted_questions = []
        for q in raw_questions:
            q_obj = {}
            q_obj['id'] = q.get("id")
            q_obj['name'] = q.get("name", "")
            q_obj['question_statement'] = q.get("question_statement") or q.get("questionStatement") or ""
            q_obj['questionStatement'] = q_obj['question_statement']
            q_obj['alternatives'] = q.get("alternatives", "")
            q_obj['correctAlternative'] = q.get("correct_alternative") or q.get("correctAlternative") or ""
            q_obj['correct_alternative'] = q_obj['correctAlternative']
            q_obj['detailedResolution'] = q.get("detailedResolution", "") or q.get("detailed_resolution", "")
            q_obj['detailed_resolution'] = q_obj['detailedResolution']

            image_field = q.get("image")
            if image_field:
                if isinstance(image_field, dict) and "url" in image_field:
                    q_obj['image'] = image_field['url']
                    q_obj['image_role'] = image_field.get('role')
                elif isinstance(image_field, str):
                    q_obj['image'] = image_field
                else:
                    q_obj['image'] = None
            else:
                images_array = q.get("images", [])
                if images_array and isinstance(images_array, list) and len(images_array) > 0:
                    first = images_array[0]
                    if isinstance(first, dict) and 'src' in first:
                        q_obj['image'] = first['src']
                        q_obj['image_role'] = first.get('role')
                    elif isinstance(first, str):
                        q_obj['image'] = first
                else:
                    q_obj['image'] = None

            if 'image_role' not in q_obj or q_obj['image_role'] is None:
                q_obj['image_role'] = q.get("image_role")

            if q_obj.get('image') and isinstance(q_obj['image'], str) and q_obj['image'].startswith('/uploads/'):
                q_obj['image'] = 'http://localhost:8000' + q_obj['image']

            formatted_questions.append(q_obj)

        mock_exam = {
            'name':      name,
            'fase':      fase,
            'anos':      anos_lista,
            'escola':    payload.get("escola", ""),
            'municipio': payload.get("municipio", ""),
            'ano':       ano_prova,
        }

        inst_name = getattr(settings, "DEFAULT_INSTITUTION_NAME", "Olimpíadas de Matemática")
        logo_path = getattr(settings, "DEFAULT_LOGO_PATH", None)

        pdf_request = ExamPDFRequest(
            exam_id=None,
            questions=[],
            fase=fase,
            anos=anos_lista,
            escola=payload.get("escola", ""),
            municipio=payload.get("municipio", ""),
            ano=ano_prova,
            include_answers=True,
            cover_info={
                "logo_path": logo_path,
                "institution": inst_name,
                "exam_title": name
            }
        )

        pdf_buffer = await PDFService.generate_exam_pdf(
            mock_exam,
            formatted_questions,
            pdf_request
        )

        safe_name = "".join([c if c.isalnum() else "_" for c in name])
        filename = f"prova_{safe_name}.pdf"

        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        logger.error(f"Erro ao gerar PDF via payload: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao gerar PDF: {str(e)}"
        )


@router.get("/{exam_id}", response_model=dict)
async def get_exam(
    exam_id: int,
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    try:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        logger.info(f"Exam {exam_id} has {len(exam.exam_questions)} questions")
        return {"success": True, "data": {"exam": ExamResponse.from_orm(exam)}}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/{exam_id}", response_model=dict)
async def update_exam(
    exam_id: int,
    exam_data: ExamUpdate,
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
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
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    try:
        exam = ExamService.update_exam_questions(db, exam_id, questions_data, current_user)
        return {
            "success": True,
            "message": "Questões da prova atualizadas com sucesso",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/{exam_id}/layout", response_model=dict)
async def update_exam_layout(
    exam_id: int,
    layout_data: ExamLayoutUpdate,
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    """
    Atualiza cabeçalho e/ou rodapé do PDF da prova.
    Aceita JSON com:
      header_image / footer_image : base64 da imagem, "" para restaurar padrão, null para não alterar
      header_size  / footer_size  : percentual 50-150
    """
    try:
        exam = ExamService.update_exam_layout(
            db=db,
            exam_id=exam_id,
            current_user=current_user,
            header_image_b64=layout_data.header_image,
            footer_image_b64=layout_data.footer_image,
            header_size=layout_data.header_size,
            footer_size=layout_data.footer_size,
        )
        return {
            "success": True,
            "message": "Layout da prova atualizado com sucesso",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.detail)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.delete("/{exam_id}", response_model=dict)
async def delete_exam(
    exam_id: int,
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    try:
        ExamService.delete_exam(db, exam_id, current_user)
        return {"success": True, "message": "Prova removida com sucesso"}
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.patch("/{exam_id}/status", response_model=dict)
async def change_exam_status(
    exam_id: int,
    new_status: ExamStatus,
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    try:
        exam = ExamService.change_exam_status(db, exam_id, new_status, current_user)
        return {
            "success": True,
            "message": f"Status alterado para {new_status.value}",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/{exam_id}/pdf")
async def generate_exam_pdf(
    exam_id: int,
    include_answers: bool = Query(False),
    institution_name: Optional[str] = Query(None),
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    try:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        # Força o carregamento antecipado da imagem de cada questão
        for eq in exam.exam_questions:
            if eq.question:
                _ = eq.question.image

        questions = [
            eq.question
            for eq in sorted(exam.exam_questions, key=lambda x: x.order_index)
        ]

        logo_path = getattr(settings, "DEFAULT_LOGO_PATH", None)
        inst_name = institution_name or getattr(settings, "DEFAULT_INSTITUTION_NAME", "Olimpíadas de Matemática")

        pdf_request = ExamPDFRequest(
            exam_id=exam_id,
            questions=[],
            fase=getattr(exam, 'fase', '1ª FASE'),
            anos=getattr(exam, 'anos', []),
            escola=getattr(exam, 'escola', ''),
            municipio=getattr(exam, 'municipio', ''),
            ano=getattr(exam, 'ano', 2024),
            include_answers=include_answers,
            cover_info={
                "logo_path": logo_path,
                "institution": inst_name,
                "exam_title": exam.name
            }
        )

        pdf_buffer = await PDFService.generate_exam_pdf(exam, questions, pdf_request)

        safe_name = "".join([c if c.isalnum() else "_" for c in exam.name])
        filename = f"prova_{safe_name}.pdf"

        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Erro ao gerar PDF da prova {exam_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno na geração do PDF."
        )