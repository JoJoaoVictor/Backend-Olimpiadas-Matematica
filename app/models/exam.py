"""
Modelo de Dados: Prova
Arquivo: app/models/exam.py
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum, JSON, Float
from sqlalchemy.orm import relationship
import enum
from app.models.base import BaseModel


class ExamStatus(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APLICADA = "APLICADA"
    APROVADA = "APROVADA"


class Exam(BaseModel):
    __tablename__ = "exams"

    name   = Column(String(200), nullable=False, index=True)
    fase   = Column(String(50),  nullable=False, index=True)
    anos   = Column(JSON,        nullable=False)
    status = Column(Enum(ExamStatus), default=ExamStatus.PENDENTE, nullable=False)

    description        = Column(Text,    nullable=True)
    total_questions    = Column(Integer, default=0)
    estimated_duration = Column(Integer, nullable=True)
    ano                = Column(Integer, default=None, nullable=True)

    header_image = Column(Text,  nullable=True)
    footer_image = Column(Text,  nullable=True)
    header_size  = Column(Float, default=100.0, nullable=False)
    footer_size  = Column(Float, default=100.0, nullable=False)

    reviewer_comments = Column(Text, nullable=True)  # Comentários do revisor

    # Referência a quem revisou/aprovou a prova
    # SET NULL: se o revisor for apagado, o campo fica nulo.
    reviewed_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Relação para aceder aos dados do revisor (ex: exam.reviewed_by.name)
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])

    # SET NULL: ao deletar o autor, author_id vira NULL mas a prova permanece.
    # O histórico é preservado pelo campo author_name abaixo.
    author_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Snapshot do nome do autor salvo no momento da criação.
    # Preenchido automaticamente pelo exam_service — frontend não precisa enviar.
    # Garante exibição do nome mesmo após o usuário ser deletado.
    author_name = Column(String(100), nullable=False, default="")
    author_email = Column(String(150), nullable=True, default="")
    # Especificamos foreign_keys aqui para o SQLAlchemy não se confundir
    # com as duas relações que apontam para a tabela "users"
    author = relationship("User", foreign_keys=[author_id], back_populates="exams")
    
    exam_questions = relationship(
        "ExamQuestion",
        back_populates="exam",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Exam(id={self.id}, name='{self.name}', status='{self.status}')>"