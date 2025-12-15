from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Grau(BaseModel):
    """Model para graus educacionais (Fundamental I, II, Médio)."""
    __tablename__ = "graus"
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)  # Para ordenação
    
    # Relacionamentos
    questions = relationship("Question", back_populates="grau")
     
    def __repr__(self):
        return f"<Grau(id={self.id}, name='{self.name}')>"
