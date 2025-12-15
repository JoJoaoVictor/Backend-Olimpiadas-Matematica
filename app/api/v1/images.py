"""Rotas de upload de imagens."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.image import ImageResponse, ImageUpload
from app.services.image_service import ImageService
from app.core.exceptions import ValidationException

router = APIRouter()

 
@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    description: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload de imagem."""
    try:
        image = ImageService.upload_image(db, file, current_user, description)
        
        return {
            "success": True,
            "message": "Imagem enviada com sucesso",
            "data": {"image": ImageResponse.from_orm(image)}
        }
        
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro no upload da imagem"
        )


@router.get("/{image_id}", response_model=dict)
async def get_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Busca imagem por ID."""
    from app.models.image import Image
    
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagem não encontrada"
        )
    
    return {
        "success": True,
        "data": {"image": ImageResponse.from_orm(image)}
    }


@router.delete("/{image_id}", response_model=dict)
async def delete_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove imagem."""
    try:
        success = ImageService.delete_image(db, image_id, current_user)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Imagem não encontrada"
            )
        
        return {
            "success": True,
            "message": "Imagem removida com sucesso"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover imagem"
        )
