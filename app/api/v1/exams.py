"""Rotas de provas."""
from app.models.question import Question  # Adicione esta linha
import logging
from typing import List, Optional
from io import BytesIO
import types  # Usado para criar objetos mock dinâmicos

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
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

# Configuração do logger
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=dict)
async def list_exams(
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(20, ge=1, le=100, description="Itens por página"),
    search: Optional[str] = Query(None, description="Busca textual"),
    status: Optional[ExamStatus] = Query(None, description="Filtro por status"),
    fase: Optional[str] = Query(None, description="Filtro por fase"),
    anos: Optional[List[str]] = Query(None, description="Filtro por anos"),
    author_id: Optional[int] = Query(None, description="Filtro por autor"),
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

        return {"success": True, "data": result}

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Cria uma nova prova."""
    try:
        exam = ExamService.create_exam(db, exam_data, current_user)

        return {
            "success": True,
            "message": "Prova criada com sucesso",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


# ------------------------------------------------------------------------------
# ROTA DE GERAÇÃO DE PDF A PARTIR DE PAYLOAD (FRONTEND)
# ------------------------------------------------------------------------------
@router.post("/generate_pdf")
async def generate_pdf_from_payload(
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Gera PDF a partir de um payload JSON enviado pelo frontend.
    """
    try:
        # ========== EXTRAÇÃO DOS DADOS DO PAYLOAD ==========
        name = payload.get("name", "Prova Sem Título")
        fase = payload.get("fase", "")
        anos_str = payload.get("anos", "")
        raw_questions = payload.get("questoes", [])

        # ========== CORREÇÃO: USAR APENAS DADOS DO PAYLOAD ==========
        formatted_questions = []
        
        for q in raw_questions:
            q_obj = {}
            
            # Atributos básicos do payload
            q_obj['id'] = q.get("id")
            q_obj['name'] = q.get("name", "")
            q_obj['question_statement'] = q.get("question_statement") or q.get("questionStatement") or ""
            q_obj['questionStatement'] = q_obj['question_statement']
            
            # Alternativas - converte string JSON para dict se necessário
            alternatives = q.get("alternatives", {})
            if isinstance(alternatives, str):
                try:
                    import json
                    alternatives = json.loads(alternatives)
                except:
                    alternatives = {}
            q_obj['alternatives'] = alternatives
            
            # Alternativa correta
            q_obj['correctAlternative'] = q.get("correct_alternative") or q.get("correctAlternative") or ""
            q_obj['correct_alternative'] = q_obj['correctAlternative']
            
            # ========== CORREÇÃO CRÍTICA: USAR RESOLUÇÃO DO PAYLOAD ==========
            # O payload já tem a resolução! Não buscar no banco.
            # Usa detailedResolution (camelCase) do payload, que é o nome correto
            detailed_resolution = q.get("detailedResolution", "")
            q_obj['detailedResolution'] = detailed_resolution
            q_obj['detailed_resolution'] = detailed_resolution  # Alias para compatibilidade
            
            # Imagem
            q_obj['image'] = q.get("image")
            
            formatted_questions.append(q_obj)

        print(f"DEBUG - Total questões formatadas: {len(formatted_questions)}")
        
        # ========== CRIAÇÃO DO MOCK DA PROVA ==========
        mock_exam = {
            'name': name,
            'fase': fase,
            'anos': [anos_str] if isinstance(anos_str, str) else anos_str,
            'escola': payload.get("escola", ""),
            'municipio': payload.get("municipio", ""),
            'ano': payload.get("ano", 2024)
        }

        # ========== CONFIGURAÇÃO DO PDF REQUEST ==========
        inst_name = getattr(
            settings,
            "DEFAULT_INSTITUTION_NAME",
            "Olimpíadas de Matemática"
        )
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

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        # Log do erro completo para debug
        logger.error(
            f"Erro ao gerar PDF via payload: {str(e)}",
            exc_info=True
        )
        # Retorna erro 500 com mensagem descritiva
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
        exam = ExamService.update_exam_questions(
            db,
            exam_id,
            questions_data,
            current_user
        )

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
    """Altera status da prova."""
    try:
        exam = ExamService.change_exam_status(
            db,
            exam_id,
            new_status,
            current_user
        )

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
    """Gera PDF da prova salva no banco de dados."""
    try:
        # Busca a prova no banco
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        # Ordena as questões pelo order_index
        questions = [
            eq.question
            for eq in sorted(
                exam.exam_questions,
                key=lambda x: x.order_index
            )
        ]

        # Busca configurações institucionais
        logo_path = getattr(settings, "DEFAULT_LOGO_PATH", None)
        inst_name = institution_name or getattr(
            settings,
            "DEFAULT_INSTITUTION_NAME",
            "Olimpíadas de Matemática"
        )

        # Cria o schema ExamPDFRequest
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

        # Gera o PDF chamando o serviço
        pdf_buffer = await PDFService.generate_exam_pdf(
            exam,
            questions,
            pdf_request
        )

        # Sanitiza nome do arquivo
        safe_name = "".join([c if c.isalnum() else "_" for c in exam.name])
        filename = f"prova_{safe_name}.pdf"

        # Retorna o PDF como resposta
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(
            f"Erro ao gerar PDF da prova {exam_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno na geração do PDF."
        )


@router.get("/stats/summary", response_model=dict)
async def get_exam_stats(
    current_user: User = Depends(get_professor_user),
    db: Session = Depends(get_db)
):
    """Estatísticas gerais das provas."""
    try:
        stats = ExamService.get_exam_stats(db, current_user)
        return {"success": True, "data": {"stats": stats}}

    except Exception as e:
        logger.error(
            f"Erro ao buscar estatísticas: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas"
        )