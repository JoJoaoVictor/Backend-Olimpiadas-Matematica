from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Image(BaseModel):
    """Model para imagens anexadas às questões."""
    __tablename__ = "images"
    
    # Informações do arquivo
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # em bytes
    mime_type = Column(String(100), nullable=False)
    
    # Dimensões da imagem
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
     
    # URLs (para CDN ou storage externo)
    url = Column(String(500), nullable=True)
    
    # Relacionamentos
    questions = relationship("Question", back_populates="image")
    
    def __repr__(self):
        return f"<Image(id={self.id}, filename='{self.filename}')>"
