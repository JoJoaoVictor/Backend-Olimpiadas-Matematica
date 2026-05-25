from sqlalchemy import Column, Integer, String
from app.database import Base   

class CustomBNCC(Base):
    __tablename__ = "custom_bncc"

    id = Column(Integer, primary_key=True, index=True)
    grauId = Column(Integer, nullable=False)
    unidadeTematica = Column(String, nullable=False)
    objetosDeConhecimento = Column(String, nullable=False)
    habilidade = Column(String, unique=True, index=True, nullable=False)
    abilityDescription = Column(String, nullable=True)