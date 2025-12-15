from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole
from app.schemas.base import TimestampedSchema


class UserBase(BaseModel):
    """Schema base para usuário."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    is_active: bool = True


class UserCreate(UserBase):
    """Schema para criação de usuário."""
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole = Field(default=UserRole.STUDENT)

class UserUpdate(BaseModel):
    """Schema para atualização de usuário."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

 
class UserResponse(TimestampedSchema):
    """Schema para resposta de usuário (sem dados sensíveis)."""
    name: str
    email: str
    role: UserRole
    avatar_url: Optional[str] = None
    is_active: bool
    is_email_verified: bool
    last_login: Optional[datetime] = None
    class Config:
        orm_mode = True


class UserProfile(UserResponse):
    """Schema estendido para perfil do usuário."""
    login_attempts: int
    locked_until: Optional[datetime] = None

