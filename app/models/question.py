"""
Modelo de Dados: Questão
Arquivo: app/models/question.py
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel
from sqlalchemy.ext.hybrid import hybrid_property

class DifficultyLevel(int, enum.Enum):
    MUITO_FACIL   = 1
    FACIL         = 2
    MEDIO         = 3
    DIFICIL       = 4
    MUITO_DIFICIL = 5


class Question(BaseModel):
    __tablename__ = "questions"

    name           = Column(String(200), nullable=False, index=True)
    professor_name = Column(String(100), nullable=False)
    
    author_campus  = Column(String(100), nullable=True)
    author_cidade  = Column(String(100), nullable=True)

    serie_ano        = Column(String(50),  nullable=False, index=True)
    phase_level      = Column(String(50),  nullable=False, index=True)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False, index=True)

    bncc_theme          = Column(String(200), nullable=False, index=True)
    knowledge_objects   = Column(Text,        nullable=False)
    ability_code        = Column(String(20),  nullable=False, index=True)
    ability_description = Column(Text,        nullable=False)

    question_statement  = Column(Text,       nullable=False)
    alternatives        = Column(Text,       nullable=False)
    correct_alternative = Column(String(10), nullable=False)
    detailed_resolution = Column(Text,       nullable=False)

    latex_formula        = Column(Text,        nullable=True)
    rendered_formula_url = Column(String(500), nullable=True)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    grau_id     = Column(Integer, ForeignKey("graus.id"),      nullable=False)

    # SET NULL: ao deletar o autor, author_id vira NULL mas a questão permanece.
    # O campo professor_name (já existente) preserva o nome do criador.
    author_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    image_id          = Column(Integer, ForeignKey("images.id"), nullable=True)
    image_role        = Column(String(10), nullable=True)
    reviewer_comments = Column(Text,       nullable=True)

    # SET NULL: se o revisor for deletado, reviewed_by_id vira NULL.
    # A questão permanece no banco; só deixa de aparecer na listagem
    # do revisor deletado (que não existe mais).
    reviewed_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    category  = relationship("Category", back_populates="questions")
    grau      = relationship("Grau",     back_populates="questions")
    author    = relationship(
        "User",
        foreign_keys=[author_id],
        back_populates="questions"
    )
    reviewer  = relationship(
        "User",
        foreign_keys=[reviewed_by_id],
        back_populates="reviewed_questions"
    )
    image          = relationship("Image",        back_populates="questions")
    exam_questions = relationship("ExamQuestion", back_populates="question")

    def __repr__(self):
        return f"<Question(id={self.id}, name='{self.name[:30]}...')>"
    
    @hybrid_property
    def is_applied(self) -> bool:
        """Retorna True se a questão já foi associada a alguma prova."""
        return len(self.exam_questions) > 0