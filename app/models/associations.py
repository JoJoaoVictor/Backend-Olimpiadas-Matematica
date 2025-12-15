from sqlalchemy import Column, Integer, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ExamQuestion(BaseModel):
    """Tabela de associação entre Exam e Question com ordem."""
    __tablename__ = "exam_questions"
    
    # Relacionamentos
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False) 
    
    # Ordem da questão na prova
    order_index = Column(Integer, nullable=False, default=0)
    
    # Relacionamentos (Objetos)
    exam = relationship("Exam", back_populates="exam_questions")
    question = relationship("Question", back_populates="exam_questions")
    
    def __repr__(self):
        return f"<ExamQuestion(exam_id={self.exam_id}, question_id={self.question_id}, order={self.order_index})>"

 