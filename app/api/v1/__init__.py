"""API v1 routes."""

from fastapi import APIRouter

from . import auth, users, categories, graus, images, questions, exams, admin

api_router = APIRouter()

# Inclui todas as rotas
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(users.router, prefix="/users", tags=["Usuários"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categorias"])
api_router.include_router(graus.router, prefix="/graus", tags=["Graus"])
api_router.include_router(images.router, prefix="/images", tags=["Imagens"])
api_router.include_router(questions.router, prefix="/questions", tags=["Questões"])
api_router.include_router(exams.router, prefix="/exams", tags=["Provas"])
api_router.include_router(admin.router, prefix="/admin", tags=["Administração"])