"""
Schemas de autenticação da aplicação.

Responsável por validar e estruturar:
- Registro de usuário
- Login
- Tokens JWT
- Refresh token
- Reset de senha (Solicitação e Confirmação)
"""

from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, validator
from app.models.user import UserRole

# =====================================================
# MIXIN DE VALIDAÇÃO DE SENHA
# =====================================================
class PasswordValidatorMixin:
    """
    Mixin para reutilizar a lógica de validação de senha forte
    tanto no Registro quanto no Reset de Senha.
    """
    @validator("password", "new_password", check_fields=False)
    def validate_password_strength(cls, password: str):
        if not password:
            return password
            
        if not any(char.islower() for char in password):
            raise ValueError("A senha deve conter pelo menos uma letra minúscula")

        if not any(char.isupper() for char in password):
            raise ValueError("A senha deve conter pelo menos uma letra maiúscula")

        if not any(char.isdigit() for char in password):
            raise ValueError("A senha deve conter pelo menos um número")

        return password

# =====================================================
# REGISTRO DE USUÁRIO
# =====================================================
class UserRegister(BaseModel, PasswordValidatorMixin):
    """
    Schema para registro de usuário.
    """
    name: str = Field(..., min_length=2, max_length=100, description="Nome completo")
    email: EmailStr = Field(..., description="Email válido")
    password: str = Field(..., min_length=8, max_length=100, description="Senha forte")
    role: Optional[UserRole] = Field(default=UserRole.STUDENT, description="Perfil do usuário")

# =====================================================
# LOGIN
# =====================================================
class UserLogin(BaseModel):
    """
    Schema para login tradicional com email e senha.
    """
    email: EmailStr
    password: str

# =====================================================
# RECUPERAÇÃO DE SENHA (ESQUECI A SENHA)
# =====================================================
class ForgotPasswordRequest(BaseModel):
    """
    Recebe o email para enviar o link de recuperação.
    """
    email: EmailStr

class ResetPasswordRequest(BaseModel, PasswordValidatorMixin):
    """
    Recebe o token e a nova senha para efetivar a troca.
    """
    token: str
    new_password: str = Field(..., min_length=8, max_length=100, alias="new_password")

# =====================================================
# TOKENS JWT
# =====================================================
class TokenResponse(BaseModel):
    """
    Estrutura dos Tokens JWT.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenRefresh(BaseModel):
    """
    Schema para renovação do access token.
    """
    refresh_token: str

# =====================================================
# RESPOSTAS DA API (SERIALIZAÇÃO)
# =====================================================

class UserSchema(BaseModel):
    """
    Representação pública do Usuário (sem senha).
    """
    id: int
    name: str
    email: EmailStr
    role: UserRole
    avatar_url: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True  

class AuthData(BaseModel):
    """
    Dados contidos na resposta de autenticação.
    """
    user: Optional[UserSchema] = None
    tokens: Optional[TokenResponse] = None

class UserResponse(BaseModel):
    """
    Envelope padrão de resposta da API de Autenticação.
    """
    success: bool
    message: Optional[str] = None
    data: Optional[AuthData] = None