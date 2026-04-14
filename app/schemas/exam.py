from typing import Optional, List
from pydantic import BaseModel, Field, validator
from app.models.exam import ExamStatus
from app.schemas.base import TimestampedSchema
from app.schemas.user import UserResponse
from app.schemas.question import QuestionResponse


class ExamBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    fase: str = Field(..., min_length=1, max_length=50)
    anos: List[str] = Field(..., min_items=1)
    status: ExamStatus = ExamStatus.PENDENTE
    description: Optional[str] = Field(None, max_length=1000)
    estimated_duration: Optional[int] = Field(None, gt=0, le=480)

    @validator("anos")
    def validate_anos(cls, v):
        valid_anos = [
            "1º", "2º", "3º", "4º", "5º", "6º", "7º", "8º", "9º",
            "1º Médio", "2º Médio", "3º Médio",
            "1º Fundamental", "2º Fundamental", "3º Fundamental",
            "4º Fundamental", "5º Fundamental", "6º Fundamental",
            "7º Fundamental", "8º Fundamental", "9º Fundamental",
        ]
        for ano in v:
            if ano not in valid_anos:
                raise ValueError(f"Ano '{ano}' não é válido. Use: {', '.join(valid_anos)}")
        return list(set(v))


class ExamCreate(ExamBase):
    question_ids: List[int] = Field(..., min_items=1, max_items=50)

    @validator("question_ids")
    def validate_question_ids(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("IDs das questões não podem estar duplicados")
        return v


class ExamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=5, max_length=200)
    fase: Optional[str] = Field(None, min_length=1, max_length=50)
    anos: Optional[List[str]] = Field(None, min_items=1)
    status: Optional[ExamStatus] = None
    description: Optional[str] = Field(None, max_length=1000)
    estimated_duration: Optional[int] = Field(None, gt=0, le=480)
    ano: Optional[int] = Field(None, ge=2000, le=2100)
    header_image: Optional[str] = Field(None)
    footer_image: Optional[str] = Field(None)
    header_size: Optional[float] = Field(None, ge=50.0, le=150.0)
    footer_size: Optional[float] = Field(None, ge=50.0, le=150.0)


class ExamQuestionUpdate(BaseModel):
    question_ids: List[int] = Field(..., min_items=1, max_items=50)

    @validator("question_ids")
    def validate_question_ids(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("IDs das questões não podem estar duplicados")
        return v


class ExamQuestionResponse(BaseModel):
    question: QuestionResponse
    order_index: int
    model_config = {"from_attributes": True}


class ExamResponse(ExamBase, TimestampedSchema):
    # author pode ser None se o usuário foi deletado (author_id = NULL)
    author: Optional[UserResponse] = None
    # author_name preserva o nome mesmo após deleção do autor
    author_name: str = ""
    total_questions: int
    questions: List[ExamQuestionResponse] = []
    ano: Optional[int] = None
    header_image: Optional[str] = None
    footer_image: Optional[str] = None
    header_size: float = 100.0
    footer_size: float = 100.0

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        if hasattr(obj, "exam_questions") and obj.exam_questions:
            obj.__dict__["questions"] = sorted(
                obj.exam_questions,
                key=lambda eq: eq.order_index
            )
        else:
            obj.__dict__["questions"] = []
        return cls.model_validate(obj)


class ExamListResponse(BaseModel):
    exams: List[ExamResponse]
    total: int
    page: int
    per_page: int
    pages: int


class ExamFilters(BaseModel):
    search: Optional[str] = Field(None, max_length=200)
    status: Optional[ExamStatus] = None
    fase: Optional[str] = Field(None, max_length=50)
    anos: Optional[List[str]] = None
    author_id: Optional[int] = Field(None, gt=0)
    page: int = Field(default=1, gt=0)
    per_page: int = Field(default=20, gt=0, le=100)


class ExamPDFRequest(BaseModel):
    exam_id: Optional[int] = Field(default=None)
    questions: List[dict] = Field(default=[])
    fase: Optional[str] = Field(default="1ª FASE")
    anos: Optional[List[str]] = Field(default=[])
    escola: Optional[str] = Field(default="")
    municipio: Optional[str] = Field(default="")
    ano: Optional[int] = Field(default=2024)
    include_answers: bool = Field(default=False)
    cover_info: Optional[dict] = Field(default=None)


class ExamHeaderInfo(BaseModel):
    school_name: Optional[str] = Field("Nome da Escola")
    teacher_name: Optional[str] = Field(None)
    title: str = Field(...)
    subtitle: Optional[str] = Field(None)
    student_field: bool = Field(True)
    class_field: bool = Field(True)
    date_field: bool = Field(True)


class ExamGenerateRequest(BaseModel):
    header_info: ExamHeaderInfo
    question_ids: List[int] = Field(..., min_items=1)
    include_answers: bool = Field(False)


class ExamLayoutUpdate(BaseModel):
    header_image: Optional[str] = Field(default=None)
    footer_image: Optional[str] = Field(default=None)
    header_size: float = Field(default=100.0, ge=50.0, le=150.0)
    footer_size: float = Field(default=100.0, ge=50.0, le=150.0)