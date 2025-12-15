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
    """Schema para geração de PDF."""
    include_answers: bool = Field(default=False, description="Incluir gabarito")
    cover_info: Optional[dict] = Field(
        default=None, 
        description="Informações da capa (escola, aluno, etc)"
    )

