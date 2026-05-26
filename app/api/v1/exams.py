"""Rotas de provas."""
from sqlalchemy.orm import joinedload
import logging
from typing import List, Optional
from io import BytesIO
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from app.models.question import Question

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

class ExamQuestionToggleAlternatives(BaseModel):
    hide_alternatives: bool

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

@router.get("/stats/summary", response_model=dict)
async def get_exam_stats_summary(
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    """Retorna estatísticas de provas filtradas pelas permissões do usuário."""
    try:
        # Repassa o usuário atual para o serviço aplicar a blindagem do Revisor
        stats = ExamService.get_exam_stats(db, current_user)
        return {
            "success": True,
            "data": {"stats": stats}
        }
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de provas: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas"
        )
    
@router.post("/generate_pdf")
async def generate_pdf_from_payload(
    payload: dict,
    db: Session = Depends(get_db)
):
    """Gera PDF a partir de payload JSON enviado pelo frontend."""
    try:
        name          = payload.get("name", "Prova Sem Título")
        raw_fase      = payload.get("fase", "")
        raw_anos      = payload.get("anos", [])
        raw_questions = payload.get("questoes", [])
        ano_prova     = payload.get("ano", None) or __import__("datetime").datetime.now().year

        # Normaliza anos
        if isinstance(raw_anos, str):
            anos_lista = [raw_anos] if raw_anos.strip() else []
        elif isinstance(raw_anos, list):
            anos_lista = [str(a).strip() for a in raw_anos if a and str(a).strip()]
        else:
            anos_lista = []

        fase = raw_fase if raw_fase else ""

        logger.info(f"📦 Gerando PDF para prova '{name}' com {len(raw_questions)} questões")

        # 1. EXTRAI APENAS OS IDS E A FLAG DO PAYLOAD DO REACT
        question_ids = []
        hide_alts_map = {}
        
        for q in raw_questions:
            q_id = q.get("id")
            if q_id:
                question_ids.append(q_id)
                # Guarda se o React avisou que essa questão não tem alternativa
                hide_alts_map[q_id] = q.get("hide_alternatives") in [True, "true"]

        # 2. BUSCA AS QUESTÕES COMPLETAS NO BANCO DE DADOS
        full_questions = []
        if question_ids:
            # Busca no banco
            db_questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
            
            # INJETA A FLAG EFÊMERA ANTES DE MANDAR PRO GERADOR DE PDF
            for db_q in db_questions:
                # Cria a propriedade dinâmica na memória só para o PDF_service ler
                db_q.hide_alternatives = hide_alts_map.get(db_q.id, False)
            
            # Ordena para manter a ordem exata que veio do frontend
            question_map = {q.id: q for q in db_questions}
            full_questions = [question_map[qid] for qid in question_ids if qid in question_map]

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

        # 3. MANDA AS QUESTÕES QUE VIERAM DO BANCO (full_questions) PARA O GERADOR
        pdf_buffer = await PDFService.generate_exam_pdf(
            mock_exam,
            full_questions, 
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

@router.patch("/{exam_id}/questions/{question_id}", response_model=dict)
async def toggle_exam_question_alternatives(
    exam_id: int,
    question_id: int,
    payload: ExamQuestionToggleAlternatives,
    current_user: User = Depends(get_professor_or_revisor_user),
    db: Session = Depends(get_db)
):
    """
    Alterna a flag hide_alternatives de uma questão específica dentro de uma prova.
    """
    try:
        # 1. Busca a prova usando o próprio serviço existente no backend
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        if not exam:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prova não encontrada."
            )

        # 2. Percorre a lista de exam_questions vinculadas para achar a correta
        assoc = None
        for eq in exam.exam_questions:
            if eq.question_id == question_id:
                assoc = eq
                break

        if not assoc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Esta questão não está vinculada a esta prova."
            )

        # 3. Altera a propriedade diretamente no objeto interceptado
        assoc.hide_alternatives = payload.hide_alternatives
        db.commit()
        db.refresh(assoc)
        db.refresh(exam)

        return {
            "success": True,
            "message": "Exibição de alternativas atualizada com sucesso",
            "data": {"exam": ExamResponse.from_orm(exam)}
        }

    except HTTPException as he:
        raise he
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f"Erro ao alternar alternativas da questão {question_id} na prova {exam_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao atualizar a questão na prova."
        )
    
@router.patch("/{exam_id}/questions", response_model=dict)
async def update_exam_questions(
    exam_id: int,
    questions_data: List[ExamQuestionUpdate],
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
        # 1. Busca o exame com as relações
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        # 2. Força o carregamento antecipado das imagens a partir da questão real
        for eq in exam.exam_questions:
            if eq.question:
                _ = eq.question.image

        # 3. Ordena a lista da tabela intermediária (que contém o hide_alternatives salvo)
        exam_questions_ordered = sorted(
            exam.exam_questions, 
            key=lambda x: getattr(x, 'order_index', 0)
        )

        # 4. Configura as variáveis de metadados da capa
        logo_path = getattr(settings, "DEFAULT_LOGO_PATH", None)
        inst_name = institution_name or getattr(settings, "DEFAULT_INSTITUTION_NAME", "Olimpíadas de Matemática")

        # 5. Monta o pdf_request PRIMEIRO antes de chamar o serviço
        pdf_request = ExamPDFRequest(
            exam_id=exam_id,
            questions=[],  # Mantido conforme sua estrutura original
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

        # 6. Chama o PDFService passando a lista intermediária ORDENADA com as flags salvas
        pdf_buffer = await PDFService.generate_exam_pdf(exam, exam_questions_ordered, pdf_request)

        # 7. Define o nome do arquivo de download de forma segura
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