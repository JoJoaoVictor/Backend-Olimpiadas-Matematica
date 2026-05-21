# app/models/user_profile.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    cpf = Column(String(14), unique=True, nullable=True)          # 000.000.000-00
    telefone = Column(String(15), nullable=True)                  # (00) 00000-0000
    campus = Column(String(100), nullable=True)
    cidade = Column(String(100), nullable=True)
    matricula = Column(String(20), nullable=True)
    curso = Column(String(100), nullable=True)

    user = relationship("User", back_populates="profile")