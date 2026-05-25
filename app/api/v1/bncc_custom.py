from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.dependencies import get_db
from app.models.custom_bncc_model import CustomBNCC
from app.schemas.custom_bncc_schemas import CustomBNCCCreate, CustomBNCCResponse

router = APIRouter()

@router.get("/", response_model=List[CustomBNCCResponse])
def get_custom_bnccs(db: Session = Depends(get_db)):
    return db.query(CustomBNCC).all()


@router.post("/", response_model=CustomBNCCResponse, status_code=status.HTTP_201_CREATED)
def create_custom_bncc(bncc: CustomBNCCCreate, db: Session = Depends(get_db)):
    existing = db.query(CustomBNCC).filter(CustomBNCC.habilidade == bncc.habilidade).first()
    if existing:
        raise HTTPException(status_code=400, detail="Habilidade já cadastrada no servidor.")
    
    new_bncc = CustomBNCC(
        grauId=bncc.grauId,
        unidadeTematica=bncc.unidadeTematica,
        objetosDeConhecimento=bncc.objetosDeConhecimento,
        habilidade=bncc.habilidade,
        abilityDescription=bncc.abilityDescription
    )
    
    db.add(new_bncc)
    db.commit()
    db.refresh(new_bncc)
    
    return new_bncc

@router.delete("/{bncc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_bncc(bncc_id: int, db: Session = Depends(get_db)):
    """
    Remove uma habilidade BNCC customizada do banco de dados pelo seu ID.
    """
    # 1. Busca a habilidade no banco de dados
    bncc_to_delete = db.query(CustomBNCC).filter(CustomBNCC.id == bncc_id).first()
    
    # 2. Se não existir, retorna erro 404
    if not bncc_to_delete:
        raise HTTPException(status_code=404, detail="Habilidade não encontrada.")
    
    # 3. Se existir, deleta e salva a alteração
    db.delete(bncc_to_delete)
    db.commit()
    
    return None # O status 204 No Content não precisa retornar corpo na resposta