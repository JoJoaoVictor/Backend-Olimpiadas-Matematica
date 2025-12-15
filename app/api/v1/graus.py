"""Rotas de graus educacionais."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.models.grau import Grau
from app.schemas.grau import GrauCreate, GrauUpdate, GrauResponse

router = APIRouter()

 
@router.get("", response_model=dict)
async def list_graus(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lista todos os graus educacionais."""
    graus = db.query(Grau).order_by(Grau.order_index).all()
    
    return {
        "success": True,
        "data": {
            "graus": [GrauResponse.from_orm(grau) for grau in graus]
        }
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_grau(
    grau_data: GrauCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Cria novo grau educacional (apenas admin)."""
    try:
        # Verifica se já existe
        existing = db.query(Grau).filter(Grau.name == grau_data.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Grau com este nome já existe"
            )
        
        grau = Grau(**grau_data.dict())
        db.add(grau)
        db.commit()
        db.refresh(grau)
        
        return {
            "success": True,
            "message": "Grau criado com sucesso",
            "data": {"grau": GrauResponse.from_orm(grau)}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao criar grau"
        )


@router.get("/{grau_id}", response_model=dict)
async def get_grau(
    grau_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Busca grau por ID."""
    grau = db.query(Grau).filter(Grau.id == grau_id).first()
    if not grau:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grau não encontrado"
        )
    
    return {
        "success": True,
        "data": {"grau": GrauResponse.from_orm(grau)}
    }


@router.patch("/{grau_id}", response_model=dict)
async def update_grau(
    grau_id: int,
    grau_data: GrauUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Atualiza grau (apenas admin)."""
    grau = db.query(Grau).filter(Grau.id == grau_id).first()
    if not grau:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grau não encontrado"
        )
    
    