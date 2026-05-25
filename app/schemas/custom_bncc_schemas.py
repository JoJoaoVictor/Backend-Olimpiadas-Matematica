from pydantic import BaseModel
from typing import Optional

class CustomBNCCBase(BaseModel):
    grauId: int
    unidadeTematica: str
    objetosDeConhecimento: str
    habilidade: str
    abilityDescription: Optional[str] = None

class CustomBNCCCreate(CustomBNCCBase):
    pass

class CustomBNCCResponse(CustomBNCCBase):
    id: int

    class Config:
        from_attributes = True # Se usar Pydantic v1, mude para orm_mode = True