from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Category(BaseModel):
    """Model para categorias de questões (Aprovada, Pendente, etc)."""
    __tablename__ = "categories"
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#007bff")  # Código cor hex
    
    # Relacionamentos
    questions = relationship("Question", back_populates="category")
    
    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"
 