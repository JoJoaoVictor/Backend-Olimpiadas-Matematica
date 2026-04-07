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
    serie_ano = Column(String(50), nullable=False, index=True)
    phase_level = Column(String(50), nullable=False, index=True)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False, index=True)

    # BNCC
    bncc_theme = Column(String(200), nullable=False, index=True)
    knowledge_objects = Column(Text, nullable=False)
    ability_code = Column(String(20), nullable=False, index=True)
    ability_description = Column(Text, nullable=False)

    # Conteúdo da questão
    question_statement = Column(Text, nullable=False)
    alternatives = Column(Text, nullable=False)
    correct_alternative = Column(String(10), nullable=False)
    detailed_resolution = Column(Text, nullable=False)

    # Conteúdo matemático (LaTeX)
    latex_formula = Column(Text, nullable=True)
    rendered_formula_url = Column(String(500), nullable=True)

    # Relacionamentos (Foreign Keys)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    grau_id = Column(Integer, ForeignKey("graus.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=True)
    image_role = Column(String(10), nullable=True)
    reviewer_comments = Column(Text, nullable=True)

    # ── CAMPO NOVO ───────────────────────────────────────────────────────────
    # reviewed_by_id: registra qual REVISOR fez a última revisão desta questão.
    # Preenchido automaticamente pelo question_service quando um REVISOR edita.
    # Permite filtrar "questões revisadas por mim" na listagem do REVISOR.
    # nullable=True pois questões novas ainda não foram revisadas.
    reviewed_by_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    # Relacionamentos (Objetos)
    category = relationship("Category", back_populates="questions")
    grau = relationship("Grau", back_populates="questions")
    author = relationship(
        "User",
        foreign_keys=[author_id],
        back_populates="questions"
    )
    # Relacionamento separado para o revisor (foreign_keys obrigatório pois
    # há duas FKs para a mesma tabela users)
    reviewer = relationship(
        "User",
        foreign_keys=[reviewed_by_id],
        back_populates="reviewed_questions"
    )
    image = relationship("Image", back_populates="questions")
    exam_questions = relationship("ExamQuestion", back_populates="question")

    def __repr__(self):
        return f"<Question(id={self.id}, name='{self.name[:30]}...')>"