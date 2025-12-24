from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.question import Question, QuestionStatus
from app.models.exam import Exam, ExamStatus
from app.models.category import Category
from app.models.grau import Grau
from app.schemas.question import QuestionResponse
from app.schemas.exam import ExamResponse
from app.api.v1.auth import get_current_active_user

router = APIRouter()


@router.get("/questoesAprovadas", response_model=List[QuestionResponse])
async def get_questoes_aprovadas(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Endpoint compatível com frontend atual.
    Retorna questões aprovadas (status = APROVADA)
    """
    questions = db.query(Question).filter(
        Question.status == QuestionStatus.APROVADA
    ).offset(skip).limit(limit).all()
    
    return questions


@router.get("/projects", response_model=List[QuestionResponse])
async def get_projects(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Endpoint compatível para questões em revisão (projects do frontend)
    """
    questions = db.query(Question).filter(
        Question.status == QuestionStatus.PENDENTE
    ).offset(skip).limit(limit).all()
    
    return questions


@router.get("/provasMontadas", response_model=List[ExamResponse])
async def get_provas_montadas(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Endpoint compatível para provas montadas
    """
    exams = db.query(Exam).filter(
        Exam.status == ExamStatus.PENDENTE
    ).offset(skip).limit(limit).all()
    
    return exams


@router.get("/categoris")
async def get_categoris(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Endpoint compatível para categorias (nome do frontend)
    """
    categories = db.query(Category).all()
    
    return [
        {
            "id": cat.id,
            "name": cat.name,
            "description": cat.description,
            "color": cat.color
        }
        for cat in categories
    ]


@router.get("/grau")
async def get_grau(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Endpoint compatível para graus (nome do frontend)
    """
    graus = db.query(Grau).order_by(Grau.order_index).all()
    
    return [
        {
            "id": grau.id,
            "name": grau.name,
            "description": grau.description,
            "order_index": grau.order_index
        }
        for grau in graus
    ]


@router.get("/questoesAprovadas/{id}", response_model=QuestionResponse)
async def get_questao_aprovada(
    id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Busca questão aprovada por ID
    """
    question = db.query(Question).filter(
        Question.id == id,
        Question.status == QuestionStatus.APROVADA
    ).first()
    
    if not question:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    
    return question


@router.get("/projects/{id}", response_model=QuestionResponse)
async def get_project(
    id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Busca projeto (questão pendente) por ID
    """
    question = db.query(Question).filter(
        Question.id == id,
        Question.status == QuestionStatus.PENDENTE
    ).first()
    
    if not question:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    
    return question


@router.get("/provasMontadas/{id}", response_model=ExamResponse)
async def get_prova_montada(
    id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Busca prova montada por ID
    """
    exam = db.query(Exam).filter(Exam.id == id).first()
    
    if not exam:
        raise HTTPException(status_code=404, detail="Prova não encontrada")
    
    return exam