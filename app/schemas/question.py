from typing import Optional, List
from pydantic import BaseModel, Field, validator
from app.models.question import DifficultyLevel
from app.schemas.base import TimestampedSchema
from app.schemas.category import CategoryResponse
from app.schemas.grau import GrauResponse
from app.schemas.user import UserResponse
from app.schemas.image import ImageResponse


class QuestionBase(BaseModel):
    """Schema base para questão."""
    name: str = Field(..., min_length=1, max_length=200)
    professor_name: str = Field(..., min_length=1, max_length=100)
    serie_ano: str = Field(..., min_length=1, max_length=50)
    phase_level: str = Field(..., min_length=1, max_length=50)
    difficulty_level: DifficultyLevel
    bncc_theme: str = Field(..., min_length=1, max_length=200)
    knowledge_objects: str = Field(..., min_length=1)
    ability_code: str = Field(..., min_length=1, max_length=20)
    ability_description: str = Field(..., min_length=1)
    question_statement: str = Field(..., min_length=1)
    alternatives: str = Field(..., min_length=1)
    correct_alternative: str = Field(..., min_length=1, max_length=10)
    detailed_resolution: str = Field(..., min_length=1)
    latex_formula: Optional[str] = Field(None, max_length=2000)
    reviewer_comments: Optional[str] = Field(None, max_length=1000)
    image_role: Optional[str] = Field(None, max_length=10) 

    @validator("alternatives")
    def validate_alternatives(cls, v):
        """Valida se há 5 alternativas (a, b, c, d, e)."""
        import re
        alternatives = re.findall(r'[a-e]\)', v)
        if len(alternatives) != 5:
            raise ValueError("Deve conter exatamente 5 alternativas (a, b, c, d, e)")
        return v

    @validator("correct_alternative")
    def validate_correct_alternative(cls, v):
        """Valida se a alternativa correta é válida."""
        if v.lower() not in ['a', 'b', 'c', 'd', 'e']:
            raise ValueError("Alternativa correta deve ser a, b, c, d ou e")
        return v.lower()


class QuestionCreate(QuestionBase):
    """Schema para criação de questão."""
    category_id: int = Field(..., gt=0)
    grau_id: int = Field(..., gt=0)
    image_id: Optional[int] = Field(None, gt=0)


class QuestionUpdate(BaseModel):
    """Schema para atualização de questão."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    professor_name: Optional[str] = Field(None, min_length=1, max_length=100)
    serie_ano: Optional[str] = Field(None, min_length=1, max_length=50)
    phase_level: Optional[str] = Field(None, min_length=1, max_length=50)
    difficulty_level: Optional[DifficultyLevel] = None
    bncc_theme: Optional[str] = Field(None, min_length=1, max_length=200)
    knowledge_objects: Optional[str] = Field(None, min_length=1)
    ability_code: Optional[str] = Field(None, min_length=1, max_length=20)
    ability_description: Optional[str] = Field(None, min_length=1)
    question_statement: Optional[str] = Field(None, min_length=1)
    alternatives: Optional[str] = Field(None, min_length=1)
    correct_alternative: Optional[str] = Field(None, min_length=1, max_length=10)
    detailed_resolution: Optional[str] = Field(None, min_length=1)
    latex_formula: Optional[str] = Field(None, max_length=2000)
    category_id: Optional[int] = Field(None, gt=0)
    grau_id: Optional[int] = Field(None, gt=0)
    image_id: Optional[int] = Field(None, gt=0)
    reviewer_comments: Optional[str] = Field(None, max_length=1000)
    image_role: Optional[str] = Field(None, max_length=10)


class QuestionResponse(QuestionBase, TimestampedSchema):
    category: CategoryResponse
    grau: GrauResponse
    author: Optional[UserResponse] = None  
    image: Optional[ImageResponse] = None
    rendered_formula_url: Optional[str] = None
    is_applied: bool
    
    model_config = {
        "from_attributes": True
    }


class QuestionListResponse(BaseModel):
    """Schema para lista paginada de questões."""
    questions: List[QuestionResponse]
    total: int
    page: int
    per_page: int
    pages: int


class QuestionFilters(BaseModel):
    """Schema para filtros de questão."""
    search: Optional[str] = Field(None, max_length=200)
    category_id: Optional[int] = Field(None, gt=0)
    grau_id: Optional[int] = Field(None, gt=0)
    difficulty_level: Optional[DifficultyLevel] = None
    serie_ano: Optional[str] = Field(None, max_length=50)
    phase_level: Optional[str] = Field(None, max_length=50)
    bncc_theme: Optional[str] = Field(None, max_length=200)
    ability_code: Optional[str] = Field(None, max_length=20)
    author_id: Optional[int] = Field(None, gt=0)
    reviewer_id: Optional[int] = Field(None, gt=0)
    page: int = Field(default=1, gt=0)
    per_page: int = Field(default=20, gt=0, le=100)