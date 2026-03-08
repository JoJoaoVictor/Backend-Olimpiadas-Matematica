# app/services/pdf_service.py

import io
import asyncio
import json
import logging
from typing import List, Optional, Any, Dict
from concurrent.futures import ThreadPoolExecutor

from app.models.exam import Exam
from app.models.question import Question
from app.schemas.exam import ExamPDFRequest
from app.utils.pdf_generator import AdvancedPDFGenerator

logger = logging.getLogger(__name__)

if not hasattr(AdvancedPDFGenerator, 'create_exam_pdf'):
    raise AttributeError("AdvancedPDFGenerator não tem o método create_exam_pdf.")


class PDFService:
    _executor = ThreadPoolExecutor(max_workers=3)

    @staticmethod
    async def generate_exam_pdf(
        exam: Any,
        questions: List[Any],
        pdf_request: ExamPDFRequest,
        output_path: Optional[str] = None
    ) -> io.BytesIO:
        # Prepara dados do exame
        exam_data = PDFService._prepare_exam_data(exam, pdf_request)

        # Prepara dados das questões (simplificado, sem processar imagem)
        logger.info(f"📦 Preparando {len(questions)} questões para PDF")
        questions_data = PDFService._prepare_questions_data(questions)

        # Geração do PDF em thread separada
        loop = asyncio.get_event_loop()
        pdf_buffer = await loop.run_in_executor(
            PDFService._executor,
            AdvancedPDFGenerator.create_exam_pdf,
            exam_data,
            questions_data,
            None
        )

        if output_path:
            await PDFService._save_to_file(pdf_buffer, output_path)

        return pdf_buffer

    @staticmethod
    async def generate_question_bank_pdf(
        questions: List[Any],
        options: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        questions_data = PDFService._prepare_questions_data(questions)
        loop = asyncio.get_event_loop()
        pdf_buffer = await loop.run_in_executor(
            PDFService._executor,
            AdvancedPDFGenerator.create_question_bank_pdf,
            questions_data,
            options
        )
        return pdf_buffer

    @staticmethod
    async def generate_statistical_report(
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        loop = asyncio.get_event_loop()
        pdf_buffer = await loop.run_in_executor(
            PDFService._executor,
            AdvancedPDFGenerator.create_statistical_report,
            data,
            options
        )
        return pdf_buffer

    @staticmethod
    def _prepare_exam_data(exam: Any, pdf_request: ExamPDFRequest) -> Dict[str, Any]:
        if isinstance(exam, dict):
            return {
                "fase": pdf_request.fase or exam.get('fase', '1ª FASE'),
                "anos": pdf_request.anos or exam.get('anos', []),
                "escola": pdf_request.escola or exam.get('escola', ''),
                "municipio": pdf_request.municipio or exam.get('municipio', ''),
                "ano": pdf_request.ano or exam.get('ano', 2024),
            }
        else:
            return {
                "fase": pdf_request.fase or getattr(exam, 'fase', '1ª FASE'),
                "anos": pdf_request.anos or getattr(exam, 'anos', []),
                "escola": pdf_request.escola or getattr(exam, 'escola', ''),
                "municipio": pdf_request.municipio or getattr(exam, 'municipio', ''),
                "ano": pdf_request.ano or getattr(exam, 'ano', 2024),
            }

    @staticmethod
    def _prepare_questions_data(questions: List[Any]) -> List[Dict[str, Any]]:
        """
        Converte lista de questões para dict, preservando campos.
        NÃO processa imagens ou alternativas - o endpoint já fez isso.
        """
        clean_questions = []

        for idx, q in enumerate(questions):
            try:
                if isinstance(q, dict):
                    question_data = {
                        "id": q.get("id"),
                        "question_statement": q.get("question_statement") or q.get("questionStatement") or "",
                        "questionStatement": q.get("questionStatement") or q.get("question_statement") or "",
                        "image": q.get("image"),  # já é URL absoluta
                        "image_role": q.get("image_role"),  # <-- NOVO
                        "alternatives": q.get("alternatives", {}),
                        "correctAlternative": q.get("correctAlternative") or q.get("correct_alternative", ""),
                        "correct_alternative": q.get("correctAlternative") or q.get("correct_alternative", ""),
                        "name": q.get("name", ""),
                        "detailedResolution": q.get("detailedResolution", ""),
                        "detailed_resolution": q.get("detailedResolution", ""),
                    }
                else:
                    # Objeto SQLAlchemy
                    question_data = {
                        "id": getattr(q, 'id', None),
                        "question_statement": getattr(q, 'question_statement', '') or getattr(q, 'questionStatement', ''),
                        "questionStatement": getattr(q, 'questionStatement', '') or getattr(q, 'question_statement', ''),
                        "image": PDFService._extract_image_from_sqlalchemy(q),
                        "image_role": getattr(q, 'image_role', None),  # <-- NOVO
                        "alternatives": PDFService._sanitize_alternatives(q),
                        "correctAlternative": getattr(q, 'correctAlternative', '') or getattr(q, 'correct_alternative', ''),
                        "correct_alternative": getattr(q, 'correctAlternative', '') or getattr(q, 'correct_alternative', ''),
                        "name": getattr(q, 'name', ''),
                        "detailedResolution": getattr(q, 'detailedResolution', '') or getattr(q, 'detailed_resolution', ''),
                        "detailed_resolution": getattr(q, 'detailed_resolution', '') or getattr(q, 'detailedResolution', ''),
                    }

                clean_questions.append(question_data)

            except Exception as e:
                logger.error(f"Erro ao processar questão {idx}: {e}")
                q_id = q.get('id') if isinstance(q, dict) else getattr(q, 'id', '?')
                clean_questions.append({
                    "id": q_id,
                    "question_statement": f"[Erro ao carregar questão {q_id}]",
                    "questionStatement": f"[Erro ao carregar questão {q_id}]",
                    "image": None,
                    "image_role": None,
                    "alternatives": {},
                    "correctAlternative": "-",
                    "correct_alternative": "-",
                    "name": "",
                    "detailedResolution": "",
                    "detailed_resolution": "",
                })

        logger.info(f"✅ {len(clean_questions)} questões preparadas")
        return clean_questions

    @staticmethod
    def _extract_image_from_sqlalchemy(question_obj) -> Optional[str]:
        if hasattr(question_obj, 'image') and question_obj.image:
            return question_obj.image
        elif hasattr(question_obj, 'image_path') and question_obj.image_path:
            return question_obj.image_path
        elif hasattr(question_obj, 'image_url') and question_obj.image_url:
            return question_obj.image_url
        return None

    @staticmethod
    def _sanitize_alternatives(question: Any) -> Any:
        if isinstance(question, dict):
            alt = question.get('alternatives')
        else:
            alt = getattr(question, 'alternatives', None)

        if isinstance(alt, dict):
            return alt
        if not alt:
            return {}
        if isinstance(alt, str):
            try:
                return json.loads(alt)
            except:
                return alt
        return str(alt)

    @staticmethod
    async def _save_to_file(buffer: io.BytesIO, filepath: str) -> None:
        loop = asyncio.get_event_loop()
        def _write():
            with open(filepath, 'wb') as f:
                f.write(buffer.getvalue())
        await loop.run_in_executor(None, _write)


# Funções auxiliares para retrocompatibilidade
async def generate_exam_pdf_async(
    exam: Any,
    questions: List[Any],
    options: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    from app.schemas.exam import ExamPDFRequest
    pdf_request = ExamPDFRequest(
        exam_id=None,
        questions=[],
        fase=getattr(exam, 'fase', '1ª FASE') if not isinstance(exam, dict) else exam.get('fase', '1ª FASE'),
        anos=getattr(exam, 'anos', []) if not isinstance(exam, dict) else exam.get('anos', []),
        escola=options.get('escola', '') if options else '',
        municipio=options.get('municipio', '') if options else '',
        ano=options.get('ano', 2024) if options else 2024,
    )
    return await PDFService.generate_exam_pdf(exam, questions, pdf_request)


async def generate_question_bank_pdf_async(
    questions: List[Any],
    options: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    return await PDFService.generate_question_bank_pdf(questions, options)