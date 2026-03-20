from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum, JSON, Float
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
    fase = Column(String(50), nullable=False, index=True)
    anos = Column(JSON, nullable=False)
    status = Column(Enum(ExamStatus), default=ExamStatus.PENDENTE, nullable=False)
    
    # Metadados
    description = Column(Text, nullable=True)
    total_questions = Column(Integer, default=0)
    estimated_duration = Column(Integer, nullable=True)

    # Ano da prova (editável pelo usuário)
    ano = Column(Integer, default=None, nullable=True)

    # Configurações visuais do PDF (cabeçalho/rodapé)
    # Armazena o caminho relativo ou URL da imagem customizada.
    # None = usa o padrão estático (heder.PNG / footer.PNG)
    header_image = Column(Text, nullable=True)   # path relativo ou URL base64
    footer_image = Column(Text, nullable=True)   # path relativo ou URL base64
    # Percentual do tamanho em relação ao padrão: 50–150 (100 = tamanho original)
    header_size = Column(Float, default=100.0, nullable=False)
    footer_size = Column(Float, default=100.0, nullable=False)
    
    # Relacionamentos (Foreign Keys)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
     
    # Relacionamentos (Objetos)
    author = relationship("User", back_populates="exams")
    exam_questions = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Exam(id={self.id}, name='{self.name}', status='{self.status}')>"