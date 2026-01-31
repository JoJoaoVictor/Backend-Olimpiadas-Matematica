"""Serviços de gerenciamento de provas."""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func

from app.models.exam import Exam, ExamStatus
from app.models.question import Question
from app.models.user import User, UserRole
from app.models.associations import ExamQuestion
from app.schemas.exam import ExamCreate, ExamUpdate, ExamFilters, ExamQuestionUpdate
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException

# Configuração de Logger
logger = logging.getLogger(__name__)

class ExamService:
    """Serviços de provas."""
    
    @staticmethod
    def create_exam(db: Session, exam_data: ExamCreate, current_user: User) -> Exam:
        """Cria nova prova com inserção otimizada de questões."""
        try:
            # 1. Validação: Verifica se todas as questões existem numa única query
            questions = db.query(Question.id).filter(Question.id.in_(exam_data.question_ids)).all()
            found_ids = {q.id for q in questions}
            
            if len(found_ids) != len(exam_data.question_ids):
                missing_ids = set(exam_data.question_ids) - found_ids
                raise NotFoundException(f"Questões não encontradas: {list(missing_ids)}")
             
            # 2. Cria objeto da prova
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
            db.flush() # Gera o ID da prova sem commitar a transação ainda
            
            # 3. Bulk Insert das Associações (Muito mais rápido que loop com db.add)
            exam_questions = [
                ExamQuestion(
                    exam_id=exam.id,
                    question_id=question_id,
                    order_index=i + 1
                )
                for i, question_id in enumerate(exam_data.question_ids)
            ]
            
            if exam_questions:
                db.bulk_save_objects(exam_questions)
            
            db.commit()
            db.refresh(exam)
            
            logger.info(f"Prova criada: {exam.id} por usuário {current_user.id}")
            return exam
            
        except Exception as e:
            db.rollback()
            logger.error(f"Erro ao criar prova: {str(e)}")
            raise e
    
    @staticmethod
    def get_exams(
        db: Session,
        filters: ExamFilters,
        current_user: User
    ) -> Dict[str, Any]:
        """Lista provas com filtros."""
        query = db.query(Exam)
        
        # Permissões de visualização
        if current_user.role == UserRole.PROFESSOR:
            query = query.filter(Exam.author_id == current_user.id)
        
        # Filtro de busca textual
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Exam.name.ilike(search_term),
                    Exam.description.ilike(search_term)
                )
            )
        
        # Filtros exatos
        if filters.status:
            query = query.filter(Exam.status == filters.status)
        
        if filters.fase:
            query = query.filter(Exam.fase.ilike(f"%{filters.fase}%"))
        
        # Filtro de array (Anos)
        if filters.anos:
            # PostgreSQL array overlap ou contains
            # Assumindo que 'anos' no DB é JSON ou Array
            for ano in filters.anos:
                # Ajuste conforme seu dialeto SQL (ex: JSON_CONTAINS ou operador @>)
                # Aqui uso uma abordagem genérica que funciona se a coluna for JSON/Array
                query = query.filter(Exam.anos.contains(ano)) 
        
        if filters.author_id and current_user.role == UserRole.ADMIN:
            query = query.filter(Exam.author_id == filters.author_id)
        
        # Ordenação e Paginação
        total = query.count()
        query = query.order_by(desc(Exam.created_at))
        exams = query.offset((filters.page - 1) * filters.per_page).limit(filters.per_page).all()
        
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
        """Busca prova por ID com verificação de segurança."""
        exam = db.query(Exam).filter(Exam.id == exam_id).first()
        if not exam:
            raise NotFoundException("Prova não encontrada")
        
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
        """Atualiza metadados da prova."""
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        # Permissão de edição
        if exam.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta prova")
        
        update_data = exam_data.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(exam, field, value)
        
        try:
            db.commit()
            db.refresh(exam)
            return exam
        except Exception as e:
            db.rollback()
            raise e
    
    @staticmethod
    def update_exam_questions(
        db: Session,
        exam_id: int,
        questions_data: ExamQuestionUpdate,
        current_user: User
    ) -> Exam:
        """Atualiza a lista de questões (substituição completa)."""
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        if exam.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta prova")
        
        # Verifica existência das questões (Query Otimizada)
        questions = db.query(Question.id).filter(
            Question.id.in_(questions_data.question_ids)
        ).all()
        
        if len(questions) != len(questions_data.question_ids):
            found_ids = {q.id for q in questions}
            missing_ids = set(questions_data.question_ids) - found_ids
            raise NotFoundException(f"Questões não encontradas: {list(missing_ids)}")
        
        try:
            # Remove associações antigas
            db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).delete()
            
            # Adiciona novas com Bulk Insert
            new_associations = [
                ExamQuestion(
                    exam_id=exam_id,
                    question_id=qid,
                    order_index=i + 1
                )
                for i, qid in enumerate(questions_data.question_ids)
            ]
            
            if new_associations:
                db.bulk_save_objects(new_associations)
            
            # Atualiza contador
            exam.total_questions = len(questions_data.question_ids)
            
            db.commit()
            db.refresh(exam)
            return exam
            
        except Exception as e:
            db.rollback()
            logger.error(f"Erro ao atualizar questões da prova {exam_id}: {str(e)}")
            raise e
    
    @staticmethod
    def delete_exam(db: Session, exam_id: int, current_user: User) -> Exam:
        """Remove prova."""
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)
        
        if exam.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para deletar esta prova")
        
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
        
        if new_status == ExamStatus.APROVADA and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Apenas administradores podem aprovar provas")
        
        exam.status = new_status
        db.commit()
        db.refresh(exam)
        return exam
    
    @staticmethod
    def get_exam_stats(db: Session, current_user: User) -> dict:
        """Estatísticas agregadas via SQL (Otimizado)."""
        query = db.query(Exam)
        
        if current_user.role == UserRole.PROFESSOR:
            query = query.filter(Exam.author_id == current_user.id)
            
        # Total geral
        total_exams = query.count()
        
        # Agregação por Status (Uma única query ao invés de várias)
        # SELECT status, COUNT(*) FROM exams GROUP BY status
        stats_query = db.query(
            Exam.status, 
            func.count(Exam.id)
        )
        
        if current_user.role == UserRole.PROFESSOR:
            stats_query = stats_query.filter(Exam.author_id == current_user.id)
            
        stats_results = stats_query.group_by(Exam.status).all()
        
        # Converte lista de tuplas em dicionário
        # Ex: [('rascunho', 5), ('publicada', 2)] -> {'rascunho': 5, 'publicada': 2}
        status_stats = {
            status.value: count 
            for status, count in stats_results
        }
        
        # Preenche com 0 os status que não retornaram
        for status in ExamStatus:
            if status.value not in status_stats:
                status_stats[status.value] = 0
        
        return {
            "total_exams": total_exams,
            "by_status": status_stats
        }