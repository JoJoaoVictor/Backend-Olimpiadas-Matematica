"""
Schemas Pydantic para validação e serialização de dados de usuários.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole
from app.schemas.base import TimestampedSchema


class UserBase(BaseModel):
    """Schema base com campos comuns."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    is_active: bool = True


class UserCreate(UserBase):
    """Schema para criação de usuário (Registration)."""
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole = Field(default=UserRole.STUDENT)


class UserUpdate(BaseModel):
    """Schema para atualização geral de dados do usuário."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None  # Admin pode atualizar role na edição geral também


class UserRoleUpdate(BaseModel):
    """Schema específico para alterar apenas o cargo (Role)."""
    role: UserRole


class UserResponse(TimestampedSchema):
    """
    Schema de resposta para o frontend.
    Herda de TimestampedSchema para ter created_at e updated_at.
    """
    id: int
    name: str
    email: str
    role: UserRole
    avatar_url: Optional[str] = None
    is_active: bool
    is_email_verified: bool
    last_login: Optional[datetime] = None
    has_password: bool

    class Config:
        from_attributes= True  # Permite ler dados direto do objeto SQLAlchemy

class UserProfile(UserResponse):
    """Schema estendido com dados sensíveis do próprio usuário."""
    login_attempts: int
    locked_until: Optional[datetime] = None

    """ Schema para o usuário atualizar o PRÓPRIO perfil."""
class UserUpdateProfile(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)

class ChangePassword(BaseModel):
    """Schema para troca de senha."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)