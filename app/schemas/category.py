from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.base import TimestampedSchema

class CategoryBase(BaseModel):
    """Schema base para categoria."""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    color: str = Field(default="#007bff", pattern=r"^#[0-9A-Fa-f]{6}$")

class CategoryCreate(CategoryBase):
    """Schema para criação de categoria."""
    pass

class CategoryUpdate(BaseModel):
    """Schema para atualização de categoria."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    
    # MUDANÇA RECOMENDADA: Deixe Optional e default=None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")

class CategoryResponse(CategoryBase, TimestampedSchema):
    """Schema para resposta de categoria."""
    pass