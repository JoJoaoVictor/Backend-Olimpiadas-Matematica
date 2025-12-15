from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.base import TimestampedSchema


class GrauBase(BaseModel):
    """Schema base para grau educacional."""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    order_index: int = Field(default=0, ge=0)


class GrauCreate(GrauBase):
    """Schema para criação de grau."""
    pass

 
class GrauUpdate(BaseModel):
    """Schema para atualização de grau."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    order_index: Optional[int] = Field(None, ge=0)


class GrauResponse(GrauBase, TimestampedSchema):
    """Schema para resposta de grau."""
    pass
