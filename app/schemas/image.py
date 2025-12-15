from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.base import TimestampedSchema


class ImageBase(BaseModel):
    """Schema base para imagem."""
    filename: str
    original_name: str
    file_size: int = Field(..., gt=0)
    mime_type: str
    width: Optional[int] = Field(None, gt=0)
    height: Optional[int] = Field(None, gt=0)


class ImageResponse(ImageBase, TimestampedSchema):
    """Schema para resposta de imagem."""
    file_path: str
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None

 
class ImageUpload(BaseModel):
    """Schema para upload de imagem."""
    description: Optional[str] = Field(None, max_length=500)

