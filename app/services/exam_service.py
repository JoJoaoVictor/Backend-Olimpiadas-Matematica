"""Serviços de gerenciamento de provas."""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.models.exam import Exam, ExamStatus
from app.models.question import Question
from app.models.user import User, UserRole
from app.models.associations import ExamQuestion
from app.schemas.exam import ExamCreate, ExamUpdate, ExamFilters, ExamQuestionUpdate
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException


class ExamService:
    """Serviços de provas."""
    
    @staticmethod
    def create_exam(db: Session, exam_data: ExamCreate, current_user: User) -> Exam:
        """Cria nova prova."""
        # Verifica se questões existem
        questions = db.query(Question).filter(Question.id.in_(exam_data.question_ids)).all()
        
        if len(questions) != len(exam_data.question_ids):
            missing_ids = set(exam_data.question_ids) - {q.id for q in questions}
            raise NotFoundException(f"Questões não encontradas: {list(missing_ids)}")
         
        # Cria prova
        exam = Exam(
            name=exam_data.name,
            fase=exam_data.fase,
            anos=exam_data.anos,
            status=exam_data.status,
            description=exam_data.description,
            estimated_duration=exam_data.estimated_duration,
            author_id=current_user.id,
            total_questions=len(exam_data.question_ids)
        )
        
        db.add(exam)
        db.commit()
        db.refresh(exam)
        
        # Adiciona questões à prova
        for i, question_id in enumerate(exam_data.question_ids):
            exam_question = ExamQuestion(
                exam_id=exam.id,
                question_id=question_id,
                order_index=i + 1
            )
            db.add(exam_question)
        
        db.commit()
        db.refresh(exam)
        
        return exam
    
    @staticmethod
    def get_exams(
        db: Session,
        filters: ExamFilters,
        current_user: User
    ) -> Dict[str, Any]:
        """Lista provas com filtros."""
        query = db.query(Exam)
        
        # Professores veem apenas suas provas, admins veem todas
        if current_user.role == UserRole.PROFESSOR:
            query = query.filter(Exam.author_id == current_user.id)
        
        # Filtro de busca
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Exam.name.ilike(search_term),
                    Exam.description.ilike(search_term)
                )
            )
        
        # Filtros específicos
        if filters.status:
            query = query.filter(Exam.status == filters.status)
        
        if filters.fase:
            query = query.filter(Exam.fase.ilike(f"%{filters.fase}%"))
        
        if filters.anos:
            # Filtro por qualquer ano da lista
            for ano in filters.anos:
                query = query.filter(Exam.anos.contains([ano]))
        
        if filters.author_id and current_user.role == UserRole.ADMIN:
            query = query.filter(Exam.author_id == filters.author_id)
        
        # Ordenação
        query = query.order_by(desc(Exam.created_at))
        
        # Contagem total
        total = query.count()
        
        # Paginação
        exams = query.offset((filters.page - 1) * filters.per_page).limit(filters.per_page).all()
        
        # Cálculo de páginas
        pages = (total + filters.per_page - 1) // filters.per_page
        
        return {
            "exams": exams,
            "total": total,
            "page": filters.page,
            "per_page": filters.per_page,
            "pages": pages
        }
    
    @staticmethod
    def get_exam_by_id(db: Session, exam_id: int, current_user: User) -> Exam:
        """Busca prova por ID."""
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            raise NotFoundException("Prova não encontrada")
        
        # Verifica permissão
        if (current_user.role == UserRole.PROFESSOR and 
            exam.author_id != current_user.id):
            raise ForbiddenException("Sem permissão para acessar esta prova")
        
        return exam
    
    @staticmethod
    def update_exam(
        db: Session,
        exam_id: int,
        exam_data: ExamUpdate,
        current_user: User
    ) -> Exam:
        """Atualiza prova."""
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        # Verifica permissão de edição
        if exam.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta prova")
        
        # Atualiza campos fornecidos
        update_data = exam_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(exam, field, value)
        
        db.commit()
        db.refresh(exam)
        
        return exam
    
    @staticmethod
    def update_exam_questions(
        db: Session,
        exam_id: int,
        questions_data: ExamQuestionUpdate,
        current_user: User
    ) -> Exam:
        """Atualiza questões da prova."""
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        # Verifica permissão
        if exam.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta prova")
        
        # Verifica se questões existem
        questions = db.query(Question).filter(
            Question.id.in_(questions_data.question_ids)
        ).all()
        
        if len(questions) != len(questions_data.question_ids):
            missing_ids = set(questions_data.question_ids) - {q.id for q in questions}
            raise NotFoundException(f"Questões não encontradas: {list(missing_ids)}")
        
        # Remove questões atuais
        db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).delete()
        
        # Adiciona novas questões
        for i, question_id in enumerate(questions_data.question_ids):
            exam_question = ExamQuestion(
                exam_id=exam_id,
                question_id=question_id,
                order_index=i + 1
            )
            db.add(exam_question)
        
        # Atualiza total de questões
        exam.total_questions = len(questions_data.question_ids)
        
        db.commit()
        db.refresh(exam)
        
        return exam
    
    @staticmethod
    def delete_exam(db: Session, exam_id: int, current_user: User) -> Exam:
        """Remove prova."""
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        # Verifica permissão
        if exam.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para deletar esta prova")
        
        # Verifica se pode ser deletada (não aplicada)
        if exam.status == ExamStatus.APLICADA:
            raise ConflictException("Prova aplicada não pode ser deletada")
        
        db.delete(exam)
        db.commit()
        
        return exam
    
    @staticmethod
    def change_exam_status(
        db: Session,
        exam_id: int,
        new_status: ExamStatus,
        current_user: User
    ) -> Exam:
        """Altera status da prova."""
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        # Apenas admin pode aprovar provas
        if new_status == ExamStatus.APROVADA and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Apenas administradores podem aprovar provas")
        
        exam.status = new_status
        db.commit()
        db.refresh(exam)
        
        return exam
    
    @staticmethod
    def get_exam_stats(db: Session, current_user: User) -> dict:
        """Estatísticas de provas."""
        query = db.query(Exam)
        
        # Professores veem apenas suas stats
        if current_user.role == UserRole.PROFESSOR:
            query = query.filter(Exam.author_id == current_user.id)
        
        total_exams = query.count()
        
        # Stats por status
        status_stats = {}
        for status in ExamStatus:
            count = query.filter(Exam.status == status).count()
            status_stats[status.value] = count
        
        return {
            "total_exams": total_exams,
            "by_status": status_stats
        }

