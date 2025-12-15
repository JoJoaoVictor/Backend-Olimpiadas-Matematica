from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class ExamStatus(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APLICADA = "APLICADA" 
    APROVADA = "APROVADA"


class Exam(BaseModel):
    """Model para provas montadas."""
    __tablename__ = "exams"
    
    # Informações básicas
    name = Column(String(200), nullable=False, index=True)
    fase = Column(String(50), nullable=False, index=True)  # "3ª fase"
    anos = Column(JSON, nullable=False)  # Lista de anos: ["4º", "5º"]
    status = Column(Enum(ExamStatus), default=ExamStatus.PENDENTE, nullable=False)
    
    # Metadados
    description = Column(Text, nullable=True)
    total_questions = Column(Integer, default=0)
    estimated_duration = Column(Integer, nullable=True) 
    
    # Relacionamentos (Foreign Keys)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
     
    # Relacionamentos (Objetos)
    author = relationship("User", back_populates="exams")
    exam_questions = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Exam(id={self.id}, name='{self.name}', status='{self.status}')>"

