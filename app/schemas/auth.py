from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
from app.models.user import UserRole


class UserRegister(BaseModel):
    """Schema para registro de usuário."""
    name: str = Field(..., min_length=2, max_length=100, description="Nome completo")
    email: EmailStr = Field(..., description="Email válido")
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=100,
        description="Senha com pelo menos 8 caracteres"
    )
    role: Optional[UserRole] = Field(default=UserRole.PROFESSOR, description="Role do usuário")
     
    @validator("password")
    def validate_password(cls, v):
        """Valida força da senha."""
        if not any(c.islower() for c in v):
            raise ValueError("Senha deve conter pelo menos uma letra minúscula")
        if not any(c.isupper() for c in v):
            raise ValueError("Senha deve conter pelo menos uma letra maiúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve conter pelo menos um número")
        return v


class UserLogin(BaseModel):
    """Schema para login de usuário."""
    email: EmailStr = Field(..., description="Email do usuário")
    password: str = Field(..., description="Senha do usuário")


class TokenResponse(BaseModel):
    """Schema para resposta de tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class TokenRefresh(BaseModel):
    """Schema para refresh de token."""
    refresh_token: str


class PasswordReset(BaseModel):
    """Schema para reset de senha."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema para confirmação de reset de senha."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class EmailVerification(BaseModel):
    """Schema para verificação de email."""
    token: str

