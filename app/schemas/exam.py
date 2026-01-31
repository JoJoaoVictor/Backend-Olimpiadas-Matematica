from typing import Optional, List
from pydantic import BaseModel, Field, validator
from app.models.exam import ExamStatus
from app.schemas.base import TimestampedSchema
from app.schemas.user import UserResponse
from app.schemas.question import QuestionResponse


class ExamBase(BaseModel):
    """Schema base para prova."""
    name: str = Field(..., min_length=5, max_length=200)
    fase: str = Field(..., min_length=2, max_length=50)
    anos: List[str] = Field(..., min_items=1)
    status: ExamStatus = ExamStatus.PENDENTE
    description: Optional[str] = Field(None, max_length=1000)
    estimated_duration: Optional[int] = Field(None, gt=0, le=480)  # max 8 horas
    
    @validator("anos")
    def validate_anos(cls, v):
        """Valida lista de anos."""
        valid_anos = ["1º", "2º", "3º", "4º", "5º", "6º", "7º", "8º", "9º"]
        for ano in v:
            if ano not in valid_anos:
                raise ValueError(f"Ano '{ano}' não é válido. Use: {', '.join(valid_anos)}")
        return list(set(v))  # Remove duplicatas

  
class ExamCreate(ExamBase):
    """Schema para criação de prova."""
    question_ids: List[int] = Field(..., min_items=1, max_items=50)
    
    @validator("question_ids")
    def validate_question_ids(cls, v):
        """Valida IDs das questões."""
        if len(set(v)) != len(v):
            raise ValueError("IDs das questões não podem estar duplicados")
        return v


class ExamUpdate(BaseModel):
    """Schema para atualização de prova."""
    name: Optional[str] = Field(None, min_length=5, max_length=200)
    fase: Optional[str] = Field(None, min_length=2, max_length=50)
    anos: Optional[List[str]] = Field(None, min_items=1)
    status: Optional[ExamStatus] = None
    description: Optional[str] = Field(None, max_length=1000)
    estimated_duration: Optional[int] = Field(None, gt=0, le=480)


class ExamQuestionUpdate(BaseModel):
    """Schema para atualizar questões da prova."""
    question_ids: List[int] = Field(..., min_items=1, max_items=50)
    
    @validator("question_ids")
    def validate_question_ids(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("IDs das questões não podem estar duplicados")
        return v


class ExamQuestionResponse(BaseModel):
    """Schema para questão dentro de uma prova."""
    question: QuestionResponse
    order_index: int


class ExamResponse(ExamBase, TimestampedSchema):
    """Schema para resposta de prova."""
    author: UserResponse
    total_questions: int
    questions: List[ExamQuestionResponse] = []


class ExamListResponse(BaseModel):
    """Schema para lista paginada de provas."""
    exams: List[ExamResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ExamFilters(BaseModel):
    """Schema para filtros de prova."""
    search: Optional[str] = Field(None, max_length=200)
    status: Optional[ExamStatus] = None
    fase: Optional[str] = Field(None, max_length=50)
    anos: Optional[List[str]] = None
    author_id: Optional[int] = Field(None, gt=0)
    page: int = Field(default=1, gt=0)
    per_page: int = Field(default=20, gt=0, le=100)


class ExamPDFRequest(BaseModel):
    """
    Schema para requisição de geração de PDF.
    
    Usado tanto para:
    1. Gerar PDF de prova salva no banco (GET /exams/{id}/pdf)
    2. Gerar PDF "on-the-fly" do frontend (POST /exams/generate_pdf)
    
    Campos:
    - exam_id: ID da prova no banco (None se geração on-the-fly)
    - questions: Lista vazia (questões vêm do mock_exam ou do banco)
    - fase: Fase da olimpíada (ex: "1ª FASE", "2ª FASE")
    - anos: Lista de anos escolares (ex: ["4º", "5º"])
    - escola: Nome da escola (opcional, para campo no cabeçalho)
    - municipio: Nome do município (opcional, para campo no cabeçalho)
    - ano: Ano da olimpíada (ex: 2024)
    - include_answers: Se True, inclui página de gabarito ao final
    - cover_info: Informações extras da capa (logo, instituição, título)
    """
    exam_id: Optional[int] = Field(
        default=None, 
        description="ID da prova no banco (None para geração on-the-fly)"
    )
    questions: List[dict] = Field(
        default=[], 
        description="Lista de questões (vazio, vem do mock ou banco)"
    )
    fase: Optional[str] = Field(
        default="1ª FASE", 
        description="Fase da olimpíada"
    )
    anos: Optional[List[str]] = Field(
        default=[], 
        description="Anos escolares (ex: ['4º', '5º'])"
    )
    escola: Optional[str] = Field(
        default="", 
        description="Nome da escola (para campo no cabeçalho)"
    )
    municipio: Optional[str] = Field(
        default="", 
        description="Nome do município (para campo no cabeçalho)"
    )
    ano: Optional[int] = Field(
        default=2024, 
        description="Ano da olimpíada"
    )
    include_answers: bool = Field(
        default=False, 
        description="Incluir gabarito ao final"
    )
    cover_info: Optional[dict] = Field(
        default=None, 
        description="Informações da capa (logo_path, institution, exam_title)"
    )


class ExamHeaderInfo(BaseModel):
    """Detalhes do cabeçalho da prova (Logos, nomes, campos)."""
    school_name: Optional[str] = Field("Nome da Escola", description="Nome da instituição")
    teacher_name: Optional[str] = Field(None, description="Nome do professor")
    title: str = Field(..., description="Título da Prova (ex: Avaliação Bimestral)")
    subtitle: Optional[str] = Field(None, description="Subtítulo (ex: Matemática - 2º Ano)")
    student_field: bool = Field(True, description="Incluir campo para nome do aluno")
    class_field: bool = Field(True, description="Incluir campo para turma/série")
    date_field: bool = Field(True, description="Incluir campo para data")


class ExamGenerateRequest(BaseModel):
    """
    Payload para gerar PDF 'on-the-fly' (Montar Prova).
    O frontend envia os IDs e as configs, o backend devolve o PDF.
    """
    header_info: ExamHeaderInfo
    question_ids: List[int] = Field(..., min_items=1, description="Lista de IDs das questões selecionadas")
    include_answers: bool = Field(False, description="Se true, gera uma página extra com o gabarito")