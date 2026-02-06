# app/services/pdf_service.py

"""
Serviço de Geração de PDF (Async) para Olimpíada de Matemática UNEMAT
ARQUITETURA:
- Este serviço é uma camada FINA que prepara dados e chama o pdf_generator.py
- Não duplica lógica, apenas orquestra o fluxo async/sync
- Sanitiza dados do banco antes de passar para o gerador
"""

import io
import asyncio
from typing import List, Optional, Any, Dict
from concurrent.futures import ThreadPoolExecutor

from app.models.exam import Exam
from app.models.question import Question
from app.schemas.exam import ExamPDFRequest
from app.utils.pdf_generator import AdvancedPDFGenerator

# Verifique se o método existe
if not hasattr(AdvancedPDFGenerator, 'create_exam_pdf'):
    raise AttributeError("AdvancedPDFGenerator não tem o método create_exam_pdf. Verifique o arquivo pdf_generator.py.")

class PDFService:
    """
    Serviço de orquestração para geração de PDFs
    Converte operações síncronas do Playwright em async para FastAPI
    """

    # ThreadPool para executar operações síncronas do Playwright
    _executor = ThreadPoolExecutor(max_workers=3)

    @staticmethod
    async def generate_exam_pdf(
        exam: Any,
        questions: List[Any],
        pdf_request: ExamPDFRequest,
        output_path: Optional[str] = None
    ) -> io.BytesIO:
        """
        Gera PDF da prova (versão async para FastAPI)
        
        Args:
            exam: Objeto Exam do SQLAlchemy OU dict
            questions: Lista de objetos Question OU dict
            pdf_request: Schema com configurações do PDF
            output_path: Caminho opcional para salvar arquivo
            
        Returns:
            BytesIO contendo o PDF gerado
        """
        
        # Prepara dados do exame (conversão segura para dict)
        exam_data = PDFService._prepare_exam_data(exam, pdf_request)
        
        # Prepara dados das questões (sanitização robusta)
        questions_data = PDFService._prepare_questions_data(questions)
        
        # Executa geração síncrona em thread separada
        loop = asyncio.get_event_loop()
        pdf_buffer = await loop.run_in_executor(
            PDFService._executor,
            AdvancedPDFGenerator.create_exam_pdf,
            exam_data,
            questions_data,
            None  # options
        )
        
        # Salva em arquivo se solicitado
        if output_path:
            await PDFService._save_to_file(pdf_buffer, output_path)
        
        return pdf_buffer

    @staticmethod
    async def generate_question_bank_pdf(
        questions: List[Any],
        options: Optional[Dict[str, Any]] = None
    ) -> io.BytesIO:
        """
        Gera PDF do banco de questões (sem metadados de prova)
        """
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
        """
        Gera relatório estatístico (implementação futura)
        """
        loop = asyncio.get_event_loop()
        pdf_buffer = await loop.run_in_executor(
            PDFService._executor,
            AdvancedPDFGenerator.create_statistical_report,
            data,
            options
        )
        
        return pdf_buffer

    # ========== MÉTODOS AUXILIARES PRIVADOS ==========

    @staticmethod
    def _prepare_exam_data(exam: Any, pdf_request: ExamPDFRequest) -> Dict[str, Any]:
        """
        Converte objeto Exam do SQLAlchemy OU dict para dict limpo
        Prioriza dados do pdf_request sobre o banco
        """
        # Se for dict, usa diretamente
        if isinstance(exam, dict):
            return {
                "fase": pdf_request.fase or exam.get('fase', '1ª FASE'),
                "anos": pdf_request.anos or exam.get('anos', []),
                "escola": pdf_request.escola or exam.get('escola', ''),
                "municipio": pdf_request.municipio or exam.get('municipio', ''),
                "ano": pdf_request.ano or exam.get('ano', 2024),
            }
        else:
            # Assume que é objeto SQLAlchemy
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
        Converte lista de Questions (SQLAlchemy OU dict) para dicts limpos
        Aplica sanitização de dados corrompidos
        """
        clean_questions = []
        
        for q in questions:
            try:
                # Se for dict, processa diretamente
                if isinstance(q, dict):
                    question_data = {
                        "id": q.get("id"),
                        "question_statement": q.get("question_statement") or q.get("questionStatement") or "",
                        "questionStatement": q.get("question_statement") or q.get("questionStatement") or "",
                        "image": q.get("image"),
                        "alternatives": q.get("alternatives", {}),
                        "correctAlternative": q.get("correctAlternative") or q.get("correct_alternative", ""),
                        "correct_alternative": q.get("correctAlternative") or q.get("correct_alternative", ""),
                        "name": q.get("name", ""),
                        "detailedResolution": q.get("detailedResolution", ""),
                        "detailed_resolution": q.get("detailed_resolution", "") or q.get("detailedResolution", ""),
                    }
                else:
                    # Assume que é objeto Question do SQLAlchemy
                    question_data = {
                        "id": getattr(q, 'id', None),
                        "question_statement": (
                            getattr(q, 'question_statement', None) or 
                            getattr(q, 'questionStatement', '')
                        ),
                        "questionStatement": (
                            getattr(q, 'question_statement', None) or 
                            getattr(q, 'questionStatement', '')
                        ),
                        "image": getattr(q, 'image', None),
                        "alternatives": PDFService._sanitize_alternatives(q),
                        "correctAlternative": (
                            getattr(q, 'correctAlternative', None) or 
                            getattr(q, 'correct_alternative', '-')
                        ),
                        "correct_alternative": (
                            getattr(q, 'correctAlternative', None) or 
                            getattr(q, 'correct_alternative', '-')
                        ),
                        "name": getattr(q, 'name', ''),
                        "detailedResolution": getattr(q, 'detailedResolution', '') or getattr(q, 'detailed_resolution', ''),
                        "detailed_resolution": getattr(q, 'detailed_resolution', '') or getattr(q, 'detailedResolution', ''),
                    }
                
                clean_questions.append(question_data)
                
            except Exception as e:
                # Se houver erro ao processar questão, adiciona placeholder
                q_id = q.get('id') if isinstance(q, dict) else getattr(q, 'id', '?')
                print(f"⚠️ Erro ao processar questão ID {q_id}: {e}")
                clean_questions.append({
                    "id": q_id,
                    "question_statement": f"[Erro ao carregar questão {q_id}]",
                    "questionStatement": f"[Erro ao carregar questão {q_id}]",
                    "image": None,
                    "alternatives": {},
                    "correctAlternative": "-",
                    "correct_alternative": "-",
                    "name": "",
                    "detailedResolution": "",
                    "detailed_resolution": "",
                })
        
        return clean_questions

    @staticmethod
    def _sanitize_alternatives(question: Any) -> Any:
        """
        SANITIZAÇÃO CRÍTICA: Previne erro 'int' object has no attribute 'keys'
        
        Retorna:
            - dict se dados válidos
            - string se dados corrompidos (será tratado no gerador)
        """
        # Se for dicionário
        if isinstance(question, dict):
            alternatives_raw = question.get('alternatives')
        else:
            # Objeto SQLAlchemy
            alternatives_raw = getattr(question, 'alternatives', None)
        
        # Caso 1: Já é um dicionário válido
        if isinstance(alternatives_raw, dict):
            return alternatives_raw
        
        # Caso 2: É None ou vazio
        if not alternatives_raw:
            return {}
        
        # Caso 3: É string (pode ser JSON válido ou corrompido)
        if isinstance(alternatives_raw, str):
            return alternatives_raw  # O gerador vai tentar parsear
        
        # Caso 4: É int, float ou outro tipo (DADOS CORROMPIDOS)
        # Converte para string para não quebrar o sistema
        return str(alternatives_raw)

    @staticmethod
    async def _save_to_file(buffer: io.BytesIO, filepath: str) -> None:
        """Salva buffer em arquivo de forma assíncrona"""
        loop = asyncio.get_event_loop()
        
        def _write():
            with open(filepath, 'wb') as f:
                f.write(buffer.getvalue())
        
        await loop.run_in_executor(None, _write)


# ========== FUNÇÕES AUXILIARES PARA RETROCOMPATIBILIDADE ==========

async def generate_exam_pdf_async(
    exam: Any,
    questions: List[Any],
    options: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    """
    Função auxiliar para manter compatibilidade com código antigo
    """
    from app.schemas.exam import ExamPDFRequest
    
    # Cria request padrão se não fornecido
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
    """
    Função auxiliar para banco de questões
    """
    return await PDFService.generate_question_bank_pdf(questions, options)