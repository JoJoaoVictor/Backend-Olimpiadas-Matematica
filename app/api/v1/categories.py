"""Rotas de categorias."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse
from app.core.exceptions import NotFoundException, ConflictException

router = APIRouter()

 
@router.get("", response_model=dict)
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista todas as categorias."""
    categories = db.query(Category).all()
    
    return {
        "success": True,
        "data": {
            "categories": [CategoryResponse.from_orm(cat) for cat in categories]
        }
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Cria nova categoria (apenas admin)."""
    try:
        # Verifica se já existe
        existing = db.query(Category).filter(Category.name == category_data.name).first()
        if existing:
            raise ConflictException("Categoria com este nome já existe")
        
        category = Category(**category_data.dict())
        db.add(category)
        db.commit()
        db.refresh(category)
        
        return {
            "success": True,
            "message": "Categoria criada com sucesso",
            "data": {"category": CategoryResponse.from_orm(category)}
        }
        
    except ConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar categoria"
        )


@router.get("/{category_id}", response_model=dict)
async def get_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Busca categoria por ID."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada"
        )
    
    return {
        "success": True,
        "data": {"category": CategoryResponse.from_orm(category)}
    }


@router.patch("/{category_id}", response_model=dict)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Atualiza categoria (apenas admin)."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada"
        )
    
    try:
        update_data = category_data.dict(exclude_unset=True)
        
        # Verifica nome duplicado
        if 'name' in update_data:
            existing = db.query(Category).filter(
                Category.name == update_data['name'],
                Category.id != category_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Categoria com este nome já existe"
                )
        
        for field, value in update_data.items():
            setattr(category, field, value)
        
        db.commit()
        db.refresh(category)
        
        return {
            "success": True,
            "message": "Categoria atualizada com sucesso",
            "data": {"category": CategoryResponse.from_orm(category)}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar categoria"
        )


@router.delete("/{category_id}", response_model=dict)
async def delete_category(
    category_id: int,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Remove categoria (apenas admin)."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada"
        )
    
    try:
        # Verifica se tem questões associadas
        from app.models.question import Question
        questions_count = db.query(Question).filter(Question.category_id == category_id).count()
        
        if questions_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Categoria não pode ser removida pois tem {questions_count} questões associadas"
            )
        
        db.delete(category)
        db.commit()
        
        return {
            "success": True,
            "message": "Categoria removida com sucesso"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover categoria"
        )


