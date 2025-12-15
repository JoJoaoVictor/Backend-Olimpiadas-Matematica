from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class DifficultyLevel(int, enum.Enum):
    MUITO_FACIL = 1
    FACIL = 2  
    MEDIO = 3
    DIFICIL = 4
    MUITO_DIFICIL = 5


class Question(BaseModel):
    """Model para questões matemáticas."""
    __tablename__ = "questions"
     
    # Identificação básica
    name = Column(String(200), nullable=False, index=True)
    professor_name = Column(String(100), nullable=False)
    
    # Classificação educacional
    serie_ano = Column(String(50), nullable=False, index=True)  # "4º ano", "5º", etc
    phase_level = Column(String(50), nullable=False, index=True)  # "3ª fase"
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False, index=True)
    
    # BNCC
    bncc_theme = Column(String(200), nullable=False, index=True)  # Álgebra, Geometria, etc
    knowledge_objects = Column(Text, nullable=False)  # Objetos de conhecimento
    ability_code = Column(String(20), nullable=False, index=True)  # EF05MA01, etc
    ability_description = Column(Text, nullable=False) # Descrição da habilidade
    
    # Conteúdo da questão
    question_statement = Column(Text, nullable=False)  # Enunciado
    alternatives = Column(Text, nullable=False)  # 5 alternativas
    correct_alternative = Column(String(10), nullable=False)  # a, b, c, d, e
    detailed_resolution = Column(Text, nullable=False)  # Resolução detalhada
    
    # Conteúdo matemático (LaTeX)
    latex_formula = Column(Text, nullable=True)  # Fórmulas em LaTeX
    rendered_formula_url = Column(String(500), nullable=True)  # URL da fórmula renderizada
    
    # Relacionamentos (Foreign Keys)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    grau_id = Column(Integer, ForeignKey("graus.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=True)
    
    # Relacionamentos (Objetos)
    category = relationship("Category", back_populates="questions")
    grau = relationship("Grau", back_populates="questions")
    author = relationship("User", back_populates="questions")
    image = relationship("Image", back_populates="questions")
    exam_questions = relationship("ExamQuestion", back_populates="question")
    
    def __repr__(self):
        return f"<Question(id={self.id}, name='{self.name[:30]}...')>"
