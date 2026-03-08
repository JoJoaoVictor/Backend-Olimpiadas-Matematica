"""Rotas de provas."""
import logging
from typing import List, Optional
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_professor_user
from app.models.user import User
from app.models.exam import ExamStatus
from app.schemas.exam import (
    ExamCreate,
    ExamUpdate,
    ExamResponse,
    ExamFilters,
    ExamQuestionUpdate,
    ExamPDFRequest
)
from app.services.exam_service import ExamService
from app.services.pdf_service import PDFService
from app.core.exceptions import AppException
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
    current_user: User = Depends(get_professor_user),
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
        # Extrai dados básicos
        name = payload.get("name", "Prova Sem Título")
        fase = payload.get("fase", "")
        anos_str = payload.get("anos", "")
        raw_questions = payload.get("questoes", [])

        logger.info(f"📦 Gerando PDF para prova '{name}' com {len(raw_questions)} questões")

        formatted_questions = []
        for q in raw_questions:
            q_obj = {}

            q_obj['id'] = q.get("id")
            q_obj['name'] = q.get("name", "")

            # Enunciado
            q_obj['question_statement'] = q.get("question_statement") or q.get("questionStatement") or ""
            q_obj['questionStatement'] = q_obj['question_statement']

            # Alternativas (já vêm no formato "a) texto\nb) texto...")
            q_obj['alternatives'] = q.get("alternatives", "")

            # Alternativa correta
            q_obj['correctAlternative'] = q.get("correct_alternative") or q.get("correctAlternative") or ""
            q_obj['correct_alternative'] = q_obj['correctAlternative']

            # Resolução
            q_obj['detailedResolution'] = q.get("detailedResolution", "") or q.get("detailed_resolution", "")
            q_obj['detailed_resolution'] = q_obj['detailedResolution']

           # Imagem: prioridade para o campo 'image'
            image_field = q.get("image")
            if image_field:
                if isinstance(image_field, dict) and "url" in image_field:
                    q_obj['image'] = image_field['url']
                    q_obj['image_role'] = image_field.get('role')
                    print(f"Questão ID {q.get('id')}: image_role = {q_obj.get('image_role')}")
                elif isinstance(image_field, str):
                    q_obj['image'] = image_field
                    # Não define image_role aqui (será pego depois)
                else:
                    q_obj['image'] = None
            else:
                # Fallback para array 'images' (legado)
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

            #captura o image_role do objeto original, se não foi definido acima
            if 'image_role' not in q_obj or q_obj['image_role'] is None:
                q_obj['image_role'] = q.get("image_role")

            # (opcional) converter URL relativa para absoluta
            if q_obj.get('image') and isinstance(q_obj['image'], str) and q_obj['image'].startswith('/uploads/'):
                q_obj['image'] = 'http://localhost:8000' + q_obj['image']

            formatted_questions.append(q_obj)

        # Cria mock do exame
        mock_exam = {
            'name': name,
            'fase': fase,
            'anos': [anos_str] if isinstance(anos_str, str) else anos_str,
            'escola': payload.get("escola", ""),
            'municipio': payload.get("municipio", ""),
            'ano': payload.get("ano", 2024)
        }

        # Configuração do PDF request
        inst_name = getattr(settings, "DEFAULT_INSTITUTION_NAME", "Olimpíadas de Matemática")
        logo_path = getattr(settings, "DEFAULT_LOGO_PATH", None)

        pdf_request = ExamPDFRequest(
            exam_id=None,
            questions=[],
            fase=fase,
            anos=[anos_str] if isinstance(anos_str, str) else anos_str,
            escola=payload.get("escola", ""),
            municipio=payload.get("municipio", ""),
            ano=payload.get("ano", 2024),
            include_answers=True,
            cover_info={
                "logo_path": logo_path,
                "institution": inst_name,
                "exam_title": name
            }
        )

                # ========== GERAÇÃO DO PDF ==========
        pdf_buffer = await PDFService.generate_exam_pdf(
            mock_exam,
            formatted_questions,
            pdf_request
        )

        # ========== PREPARAÇÃO DA RESPOSTA ==========
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
    current_user: User = Depends(get_professor_user),
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
    current_user: User = Depends(get_professor_user),
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
    current_user: User = Depends(get_professor_user),
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


@router.delete("/{exam_id}", response_model=dict)
async def delete_exam(
    exam_id: int,
    current_user: User = Depends(get_professor_user),
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
    current_user: User = Depends(get_professor_user),
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
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    try:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

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


@router.get("/stats/summary", response_model=dict)
async def get_exam_stats(
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    try:
        stats = ExamService.get_exam_stats(db, current_user)
        return {"success": True, "data": {"stats": stats}}
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas"
        )