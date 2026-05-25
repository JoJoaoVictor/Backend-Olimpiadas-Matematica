# app/services/pdf_service.py

import io
import os
import json
import logging
import asyncio
import base64
from pathlib import Path
from typing import List, Optional, Any, Dict

from app.models.exam import Exam
from app.models.question import Question
from app.schemas.exam import ExamPDFRequest
from app.utils.pdf_generator import AdvancedPDFGenerator

logger = logging.getLogger(__name__)

if not hasattr(AdvancedPDFGenerator, 'create_exam_pdf'):
    raise AttributeError("AdvancedPDFGenerator não tem o método create_exam_pdf.")


class PDFService:

    # ─── MÉTODOS DE GERAÇÃO ASSÍNCRONOS ──────────────────────────────────
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

    # ─── MÉTODOS AUXILIARES E PREPARAÇÃO DE DADOS ────────────────────────
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
    def _prepare_questions_data(exam_questions: List[Any]) -> List[Dict[str, Any]]:
        """Mapeamento blindado com base64 inteligente de imagens do Windows e controle de alternativas."""
        questions_data = []
        
        for eq in exam_questions:
            # Identifica modelo real
            is_assoc = hasattr(eq, 'question') and getattr(eq, 'question', None) is not None
            q = eq.question if is_assoc else eq
            
            # Recupera a flag do botão "esconder alternativas" (Tenta achar a nível de dict ou Model)
            hide_alts = False
            
            # 1. Tenta buscar a flag na tabela associativa (ExamQuestion) se aplicável
            if is_assoc and hasattr(eq, 'hide_alternatives'):
                hide_alts = bool(getattr(eq, 'hide_alternatives'))
            # 2. Tenta buscar no modelo Question ou num dicionário puro
            elif hasattr(q, 'hide_alternatives'):
                hide_alts = bool(getattr(q, 'hide_alternatives'))
            elif isinstance(eq, dict):
                hide_alts = bool(eq.get('hide_alternatives', False))

            # Converte alternativas
            raw_alternatives = getattr(q, 'alternatives', {})
            alternatives_dict = PDFService._convert_alternatives_to_dict(raw_alternatives)
            
            #  Zera alternativas se a flag de esconder for verdadeira
            # O dicionário vira vazio, e o gerador de PDF não vai desenhar as alternativas (letras A, B, C...)
            if hide_alts:
                alternatives_dict = {}

            # Conversão robusta de imagem local -> base64 (Evita erro de Caminho Absoluto no Windows)
            image_base64 = None
            if getattr(q, 'image', None) and getattr(q.image, 'file_path', None):
                # Remove barras invertidas ou iniciais que o Windows entende como disco C:
                raw_path = str(q.image.file_path).replace('\\', '/')
                if raw_path.startswith('/'):
                    raw_path = raw_path.lstrip('/')
                
                # Concatena a pasta do seu projeto local com a pasta de uploads
                file_path = Path(os.getcwd()) / raw_path

                try:
                    if file_path.exists():
                        with open(file_path, "rb") as image_file:
                            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                            mime_type = getattr(q.image, 'mime_type', 'image/png')
                            image_base64 = f"data:{mime_type};base64,{encoded_string}"
                    else:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Imagem não encontrada fisicamente: {file_path}")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Erro ao converter imagem em base64: {e}")

            # Fallbacks finais de imagens
            img_dict = PDFService._extract_image_from_sqlalchemy(q)
            image_url_final = image_base64 if image_base64 else (img_dict.get('url') if img_dict else None)
            image_role_final = img_dict.get('role') if img_dict else getattr(q, 'image_role', None)

            questions_data.append({
                "id": getattr(q, 'id', None),
                "name": getattr(q, 'name', ''),
                "professor_name": getattr(q, 'professor_name', ''),
                "serie_ano": getattr(q, 'serie_ano', ''),
                "phase_level": getattr(q, 'phase_level', ''),
                "difficulty_level": getattr(q, 'difficulty_level', ''),
                "bncc_theme": getattr(q, 'bncc_theme', ''),
                "knowledge_objects": getattr(q, 'knowledge_objects', ''),
                "ability_code": getattr(q, 'ability_code', ''),
                "ability_description": getattr(q, 'ability_description', ''),
                
                # ENUNCIADO DE VOLTA COM DUPLO MAPEAMENTO DE CHAVE
                "statement": getattr(q, 'question_statement', ''),
                "question_statement": getattr(q, 'question_statement', ''),
                
                # ALTERNATIVAS OBEDECENDO A FLAG E MAPEADAS
                "alternatives": alternatives_dict,
                "hide_alternatives": hide_alts,
                
                "correct_alternative": getattr(q, 'correct_alternative', ''),
                "detailed_resolution": getattr(q, 'detailed_resolution', ''),
                "latex_formula": getattr(q, 'latex_formula', None),
                "rendered_formula_url": getattr(q, 'rendered_formula_url', None),
                
                # IMAGENS EM BASE64 COM DUPLO MAPEAMENTO
                "image_url": image_url_final,
                "image": {"url": image_url_final, "role": image_role_final} if image_url_final else None,
                "image_role": image_role_final,
            })
            
        return questions_data
    
    @staticmethod
    def _convert_alternatives_to_dict(alternatives_field: Any) -> Dict[str, Any]:
        """Garante o retorno de um dicionário válido de alternativas."""
        if not alternatives_field:
            return {}
        
        if isinstance(alternatives_field, dict):
            return alternatives_field.copy()
            
        if isinstance(alternatives_field, str):
            text_str = alternatives_field.strip()
            
            if text_str.startswith('{') and text_str.endswith('}'):
                try:
                    parsed = json.loads(text_str)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass

            import re
            pattern = re.compile(r'(?:^|\s+)([a-eA-E0-9])[\s\)]+\s*(.*?)(?=\s+(?:[a-eA-E0-9])[\s\)]+\s*|$)')
            normalized_text = " ".join(text_str.split())
            matches = pattern.findall(normalized_text)
            
            if matches:
                return {key.lower(): value.strip() for key, value in matches}
            
            lines = [line.strip() for line in text_str.split('\n') if line.strip()]
            fallback_dict = {}
            for line in lines:
                if ')' in line:
                    parts = line.split(')', 1)
                    key = parts[0].strip().lower()
                    val = parts[1].strip()
                    if len(key) == 1:
                        fallback_dict[key] = val
            if fallback_dict:
                return fallback_dict
                
        return {}

    @staticmethod
    def _extract_image_from_sqlalchemy(question_obj) -> Optional[Dict[str, Any]]:
        """Extrai a URL da imagem de forma agnóstica (ORM ou dicionário)."""
        url = None
        role = getattr(question_obj, 'image_role', None) or 'MEDIUM'

        img_obj = getattr(question_obj, 'image', None)
        if img_obj:
            if hasattr(img_obj, 'url'):
                url = img_obj.url
                role = getattr(img_obj, 'role', role)
            elif isinstance(img_obj, dict):
                url = img_obj.get('url') or img_obj.get('file_path')
                role = img_obj.get('role', role)

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

        if url and isinstance(url, str) and url.startswith('/uploads/'):
            from app.core.config import settings
            base_url = getattr(settings, 'API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
            url = f"{base_url}{url}"

        if not url:
            return None

        return {'url': url.strip(), 'role': role}

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