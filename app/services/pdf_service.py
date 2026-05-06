# app/services/pdf_service.py

import io
import json
import logging
from typing import List, Optional, Any, Dict

from app.models.exam import Exam
from app.models.question import Question
from app.schemas.exam import ExamPDFRequest
from app.utils.pdf_generator import AdvancedPDFGenerator

logger = logging.getLogger(__name__)

if not hasattr(AdvancedPDFGenerator, 'create_exam_pdf'):
    raise AttributeError("AdvancedPDFGenerator não tem o método create_exam_pdf.")


class PDFService:

    # ─── métodos de geração (agora assíncronos) ──────────────────────────
    @staticmethod
    async def generate_exam_pdf(
        exam: Any,
        questions: List[Any],
        pdf_request: ExamPDFRequest,
        output_path: Optional[str] = None
    ) -> io.BytesIO:
        exam_data = PDFService._prepare_exam_data(exam, pdf_request)
        questions_data = PDFService._prepare_questions_data(questions)

        logger.info(f"📦 Gerando PDF com {len(questions_data)} questões")
        pdf_buffer = await AdvancedPDFGenerator.create_exam_pdf(
            exam_data, questions_data, None
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
        pdf_buffer = await AdvancedPDFGenerator.create_question_bank_pdf(
            questions_data, options
        )
        return pdf_buffer

    @staticmethod
    async def generate_statistical_report(
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        pdf_buffer = await AdvancedPDFGenerator.create_statistical_report(
            data, options
        )
        return pdf_buffer

    # ─── métodos auxiliares (inalterados exceto _extract_image_from_sqlalchemy) ──
    @staticmethod
    def _prepare_exam_data(exam: Any, pdf_request: ExamPDFRequest) -> Dict[str, Any]:
        """Monta o dict que será passado para AdvancedPDFGenerator.create_exam_pdf."""
        if isinstance(exam, dict):
            return {
                "fase":         pdf_request.fase      or exam.get('fase', '1ª FASE'),
                "anos":         pdf_request.anos      or exam.get('anos', []),
                "escola":       pdf_request.escola    or exam.get('escola', ''),
                "municipio":    pdf_request.municipio or exam.get('municipio', ''),
                "ano":          pdf_request.ano       or exam.get('ano', 2024),
                "header_image": exam.get('header_image'),
                "footer_image": exam.get('footer_image'),
                "header_size":  exam.get('header_size', 100.0),
                "footer_size":  exam.get('footer_size', 100.0),
            }
        else:
            return {
                "fase":         pdf_request.fase      or getattr(exam, 'fase', '1ª FASE'),
                "anos":         pdf_request.anos      or getattr(exam, 'anos', []),
                "escola":       pdf_request.escola    or getattr(exam, 'escola', ''),
                "municipio":    pdf_request.municipio or getattr(exam, 'municipio', ''),
                "ano":          pdf_request.ano or (
                    getattr(exam, 'created_at', None).year
                    if getattr(exam, 'created_at', None) else
                    __import__('datetime').datetime.now().year
                ),
                "header_image": getattr(exam, 'header_image', None),
                "footer_image": getattr(exam, 'footer_image', None),
                "header_size":  getattr(exam, 'header_size',  100.0),
                "footer_size":  getattr(exam, 'footer_size',  100.0),
            }

    @staticmethod
    def _prepare_questions_data(questions: List[Any]) -> List[Dict[str, Any]]:
        """Converte lista de questões para dict, preservando campos."""
        clean_questions = []
        for idx, q in enumerate(questions):
            try:
                if isinstance(q, dict):
                    question_data = {
                        "id":                 q.get("id"),
                        "question_statement": q.get("question_statement") or q.get("questionStatement") or "",
                        "questionStatement":  q.get("questionStatement")  or q.get("question_statement") or "",
                        "image":              q.get("image"),
                        "image_role":         q.get("image_role"),
                        "alternatives":       q.get("alternatives", {}),
                        "correctAlternative": q.get("correctAlternative") or q.get("correct_alternative", ""),
                        "correct_alternative":q.get("correctAlternative") or q.get("correct_alternative", ""),
                        "name":               q.get("name", ""),
                        "detailedResolution": q.get("detailedResolution", ""),
                        "detailed_resolution":q.get("detailedResolution", ""),
                    }
                else:
                    question_data = {
                        "id":                 getattr(q, 'id', None),
                        "question_statement": getattr(q, 'question_statement', '') or getattr(q, 'questionStatement', ''),
                        "questionStatement":  getattr(q, 'questionStatement', '')  or getattr(q, 'question_statement', ''),
                        "image":              PDFService._extract_image_from_sqlalchemy(q),
                        "image_role":         getattr(q, 'image_role', None),
                        "alternatives":       PDFService._sanitize_alternatives(q),
                        "correctAlternative": getattr(q, 'correctAlternative', '') or getattr(q, 'correct_alternative', ''),
                        "correct_alternative":getattr(q, 'correctAlternative', '') or getattr(q, 'correct_alternative', ''),
                        "name":               getattr(q, 'name', ''),
                        "detailedResolution": getattr(q, 'detailedResolution', '') or getattr(q, 'detailed_resolution', ''),
                        "detailed_resolution":getattr(q, 'detailed_resolution', '') or getattr(q, 'detailedResolution', ''),
                    }
                clean_questions.append(question_data)
            except Exception as e:
                logger.error(f"Erro ao processar questão {idx}: {e}")
                q_id = q.get('id') if isinstance(q, dict) else getattr(q, 'id', '?')
                clean_questions.append({
                    "id": q_id,
                    "question_statement": f"[Erro ao carregar questão {q_id}]",
                    "questionStatement":  f"[Erro ao carregar questão {q_id}]",
                    "image": None,
                    "image_role": None,
                    "alternatives": {},
                    "correctAlternative": "-",
                    "correct_alternative":"-",
                    "name": "",
                    "detailedResolution": "",
                    "detailed_resolution":"",
                })
        logger.info(f"✅ {len(clean_questions)} questões preparadas")
        return clean_questions

    @staticmethod
    def _extract_image_from_sqlalchemy(question_obj) -> Optional[Dict[str, Any]]:
        """
        Extrai a URL da imagem de forma agnóstica (ORM ou dicionário).
        Retorna um dicionário com 'url' (absoluta) e 'role', ou None.
        """
        url = None
        role = getattr(question_obj, 'image_role', None) or 'MEDIUM'

        # 1. Tenta o relacionamento 'image' (objeto ORM carregado)
        img_obj = getattr(question_obj, 'image', None)
        if img_obj:
            if hasattr(img_obj, 'url'):
                url = img_obj.url
                role = getattr(img_obj, 'role', role)
            elif isinstance(img_obj, dict):
                url = img_obj.get('url') or img_obj.get('file_path')
                role = img_obj.get('role', role)

        # 2. Campos alternativos
        if not url:
            for field in ('image_path', 'image_url', 'url', 'file_path'):
                val = getattr(question_obj, field, None)
                if val and isinstance(val, str):
                    url = val
                    break
        if not url and isinstance(question_obj, dict):
            for field in ('image_path', 'image_url', 'url', 'file_path'):
                val = question_obj.get(field)
                if val and isinstance(val, str):
                    url = val
                    break
            if not url:
                img = question_obj.get('image')
                if isinstance(img, dict):
                    url = img.get('url') or img.get('file_path')
                    role = img.get('role', role)

        # 3. Fallback via image_id (busca no banco)
        if not url:
            img_id = getattr(question_obj, 'image_id', None) or (
                isinstance(question_obj, dict) and question_obj.get('image_id')
            )
            if img_id:
                from app.database import SessionLocal
                from app.models.image import Image
                with SessionLocal() as db:
                    img = db.query(Image).filter(Image.id == img_id).first()
                    if img and img.url:
                        url = img.url
                        role = getattr(question_obj, 'image_role', None) or 'MEDIUM'

        # 4. Converte caminho relativo em URL absoluta
        if url and isinstance(url, str) and url.startswith('/uploads/'):
            from app.core.config import settings
            base_url = getattr(settings, 'API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
            url = f"{base_url}{url}"

        if not url:
            return None

        return {'url': url.strip(), 'role': role}

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


# Funções auxiliares para retrocompatibilidade (inalteradas)
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