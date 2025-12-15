"""Serviços de gerenciamento de questões."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.models.question import Question, DifficultyLevel
from app.models.category import Category
from app.models.grau import Grau
from app.models.user import User, UserRole
from app.schemas.question import QuestionCreate, QuestionUpdate, QuestionFilters
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException


class QuestionService:
    """Serviços de questões."""
    
    @staticmethod
    def create_question(
        db: Session, 
        question_data: QuestionCreate, 
        current_user: User
    ) -> Question:
        """Cria nova questão."""
        # Verifica se categoria existe
        category = db.query(Category).filter(Category.id == question_data.category_id).first()
        if not category:
            raise NotFoundException("Categoria não encontrada")
        
        # Verifica se grau existe
        grau = db.query(Grau).filter(Grau.id == question_data.grau_id).first()
        if not grau:
            raise NotFoundException("Grau educacional não encontrado")
        
        # Processa LaTeX se fornecido
        rendered_formula_url = None
        if question_data.latex_formula:
            # TODO: Implementar renderização LaTeX
            # rendered_formula_url = latex_service.render_formula(question_data.latex_formula)
            pass
        
        question = Question(
            **question_data.dict(exclude={'image_id'}),
            author_id=current_user.id,
            rendered_formula_url=rendered_formula_url,
            image_id=question_data.image_id
        )
        
        db.add(question)
        db.commit()
        db.refresh(question)
        
        return question
    
    @staticmethod
    def get_questions(
        db: Session,
        filters: QuestionFilters,
        current_user: User
    ) -> Dict[str, Any]:
        """Lista questões com filtros e paginação."""
        query = db.query(Question)
        
        # Filtro de busca
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Question.name.ilike(search_term),
                    Question.question_statement.ilike(search_term),
                    Question.bncc_theme.ilike(search_term),
                    Question.knowledge_objects.ilike(search_term)
                )
            )
        
        # Filtros específicos
        if filters.category_id:
            query = query.filter(Question.category_id == filters.category_id)
        
        if filters.grau_id:
            query = query.filter(Question.grau_id == filters.grau_id)
        
        if filters.difficulty_level:
            query = query.filter(Question.difficulty_level == filters.difficulty_level)
        
        if filters.serie_ano:
            query = query.filter(Question.serie_ano.ilike(f"%{filters.serie_ano}%"))
        
        if filters.phase_level:
            query = query.filter(Question.phase_level.ilike(f"%{filters.phase_level}%"))
        
        if filters.bncc_theme:
            query = query.filter(Question.bncc_theme.ilike(f"%{filters.bncc_theme}%"))
        
        if filters.ability_code:
            query = query.filter(Question.ability_code.ilike(f"%{filters.ability_code}%"))
        
        if filters.author_id:
            query = query.filter(Question.author_id == filters.author_id)
        
        # Ordenação
        query = query.order_by(desc(Question.created_at))
        
        # Contagem total
        total = query.count()
        
        # Paginação
        questions = query.offset((filters.page - 1) * filters.per_page).limit(filters.per_page).all()
        
        # Cálculo de páginas
        pages = (total + filters.per_page - 1) // filters.per_page
        
        return {
            "questions": questions,
            "total": total,
            "page": filters.page,
            "per_page": filters.per_page,
            "pages": pages
        }
    
    @staticmethod
    def get_question_by_id(db: Session, question_id: int, current_user: User) -> Question:
        """Busca questão por ID."""
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise NotFoundException("Questão não encontrada")
        return question
    
    @staticmethod
    def update_question(
        db: Session,
        question_id: int,
        question_data: QuestionUpdate,
        current_user: User
    ) -> Question:
        """Atualiza questão."""
        question = QuestionService.get_question_by_id(db, question_id, current_user)
        
        # Verifica permissão (autor ou admin)
        if question.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta questão")
        
        # Atualiza campos fornecidos
        update_data = question_data.dict(exclude_unset=True)
        
        # Valida categoria se fornecida
        if 'category_id' in update_data:
            category = db.query(Category).filter(Category.id == update_data['category_id']).first()
            if not category:
                raise NotFoundException("Categoria não encontrada")
        
        # Valida grau se fornecido
        if 'grau_id' in update_data:
            grau = db.query(Grau).filter(Grau.id == update_data['grau_id']).first()
            if not grau:
                raise NotFoundException("Grau educacional não encontrado")
        
        # Processa LaTeX se atualizado
        if 'latex_formula' in update_data and update_data['latex_formula']:
            # TODO: Implementar renderização LaTeX
            # update_data['rendered_formula_url'] = latex_service.render_formula(update_data['latex_formula'])
            pass
        
        for field, value in update_data.items():
            setattr(question, field, value)
        
        db.commit()
        db.refresh(question)
        
        return question
    
    @staticmethod
    def delete_question(db: Session, question_id: int, current_user: User) -> Question:
        """Remove questão."""
        question = QuestionService.get_question_by_id(db, question_id, current_user)
        
        # Verifica permissão (autor ou admin)
        if question.author_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para deletar esta questão")
        
        # Verifica se questão está sendo usada em provas
        from app.models.associations import ExamQuestion
        exam_usage = db.query(ExamQuestion).filter(ExamQuestion.question_id == question_id).first()
        if exam_usage:
            raise ConflictException("Questão não pode ser deletada pois está sendo usada em provas")
        
        db.delete(question)
        db.commit()
        
        return question
    
    @staticmethod
    def approve_question(db: Session, question_id: int, current_user: User) -> Question:
        """Aprova questão (apenas admin)."""
        question = QuestionService.get_question_by_id(db, question_id, current_user)
        
        if current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Apenas administradores podem aprovar questões")
        
        # Busca categoria "Aprovada"
        approved_category = db.query(Category).filter(Category.name == "Aprovada").first()
        if not approved_category:
            raise NotFoundException("Categoria 'Aprovada' não encontrada")
        
        question.category_id = approved_category.id
        db.commit()
        db.refresh(question)
        
        return question
    
    @staticmethod
    def get_question_stats(db: Session) -> dict:
        """Estatísticas de questões."""
        total_questions = db.query(Question).count()
        
        # Stats por categoria
        categories_stats = {}
        categories = db.query(Category).all()
        for category in categories:
            count = db.query(Question).filter(Question.category_id == category.id).count()
            categories_stats[category.name] = count
        
        # Stats por dificuldade
        difficulty_stats = {}
        for level in DifficultyLevel:
            count = db.query(Question).filter(Question.difficulty_level == level).count()
            difficulty_stats[f"nivel_{level.value}"] = count
        
        # Stats por grau
        grau_stats = {}
        graus = db.query(Grau).all()
        for grau in graus:
            count = db.query(Question).filter(Question.grau_id == grau.id).count()
            grau_stats[grau.name] = count
         
        return {
            "total_questions": total_questions,
            "by_category": categories_stats,
            "by_difficulty": difficulty_stats,
            "by_grau": grau_stats
        }

