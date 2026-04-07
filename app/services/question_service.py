"""Serviços de gerenciamento de questões."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc

from app.models.question import Question, DifficultyLevel
from app.models.category import Category
from app.models.grau import Grau
from app.models.user import User, UserRole
from app.schemas.question import (
    QuestionCreate, QuestionUpdate, QuestionFilters, QuestionResponse
)
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException
from app.models.notification import NotificationType, EntityType
from app.services.notification_service import NotificationService


class QuestionService:

    @staticmethod
    def create_question(
        db: Session,
        question_data: QuestionCreate,
        current_user: User
    ) -> Question:
        """Cria nova questão."""
        category = db.query(Category).filter(Category.id == question_data.category_id).first()
        if not category:
            raise NotFoundException("Categoria não encontrada")

        grau = db.query(Grau).filter(Grau.id == question_data.grau_id).first()
        if not grau:
            raise NotFoundException("Grau educacional não encontrado")

        question = Question(
            **question_data.dict(exclude={'image_id'}),
            author_id=current_user.id,
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
        """
        Lista questões com filtros, paginação e visibilidade por role.
        """
        query = db.query(Question).options(
            joinedload(Question.category),
            joinedload(Question.grau),
            joinedload(Question.author),
            joinedload(Question.image)
        )

        # ── FILTRO POR ROLE ───────────────────────────────────────────────────
        # Garante que estamos comparando strings, evitando bugs do tipo Enum vs String
        user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

        if user_role == "PROFESSOR":
            query = query.filter(Question.author_id == current_user.id)

        elif user_role == "REVISOR":
            # LÓGICA POR ABA:
            # ABA "Approvadas" (category_id == 2) → Mostrar APENAS as que ESSE REVISOR aprovou
            # ABA "Pendentes" (category_id == 1) → Mostrar TODAS as questões pendentes
            if filters.category_id == 2:
                # Questões aprovadas: filtrar por reviewed_by_id do revisor atual
                query = query.filter(Question.reviewed_by_id == current_user.id)
            # Se category_id != 2 (ou == 1), não aplica filtro: REVISOR vê TODAS

        # ── FILTROS DE BUSCA ──────────────────────────────────────────────────
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

        if filters.reviewer_id:
            query = query.filter(Question.reviewed_by_id == filters.reviewer_id)

        query = query.order_by(desc(Question.created_at))

        total = query.count()
        questions = query.offset(
            (filters.page - 1) * filters.per_page
        ).limit(filters.per_page).all()

        pages = (total + filters.per_page - 1) // filters.per_page
        questions_data = [QuestionResponse.model_validate(q) for q in questions]

        return {
            "questions": questions_data,
            "total": total,
            "page": filters.page,
            "per_page": filters.per_page,
            "pages": pages
        }

    @staticmethod
    def get_question_by_id(
        db: Session,
        question_id: int,
        current_user: User
    ) -> Question:
        """Busca questão por ID."""
        question = db.query(Question).options(
            joinedload(Question.category),
            joinedload(Question.grau),
            joinedload(Question.author),
            joinedload(Question.image)
        ).filter(Question.id == question_id).first()

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

        if current_user.role == UserRole.PROFESSOR:
            if question.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode editar suas próprias questões")
        elif current_user.role == UserRole.REVISOR:
            pass
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta questão")

        update_data = question_data.dict(exclude_unset=True)

        if 'category_id' in update_data:
            category = db.query(Category).filter(
                Category.id == update_data['category_id']
            ).first()
            if not category:
                raise NotFoundException("Categoria não encontrada")

        # ✅ Flag para rastrear se criamos notificação de revisão geral
        should_notify_revision = False
        
        if current_user.role in [UserRole.REVISOR, UserRole.ADMIN]:
            # ✅ CORREÇÃO: Permitir que REVISOR aprove sua própria questão
            # Quando mudou de ESTUDANTE para REVISOR, pode revisar/aprovar suas próprias questões
            if update_data.get('category_id') == 2:
                update_data['reviewed_by_id'] = current_user.id
            
            # Lógica de notificações: só notificar se for questão de outro autor
            if question.author_id != current_user.id:
                # ✅ CORREÇÃO BUG 1: Determinar se há alterações que merecem notificação
                # Se revisor alterou ANY campo, deve notificar (exceto apenas reviewed_by_id)
                has_content_changes = any(
                    field not in ['reviewed_by_id'] 
                    for field in update_data.keys()
                )
                if has_content_changes:
                    should_notify_revision = True

        for field, value in update_data.items():
            setattr(question, field, value)

        db.commit()
        db.refresh(question)

        # ✅ Criar notificações APÓS refresh (transação segura)
        if current_user.role in [UserRole.REVISOR, UserRole.ADMIN]:
            if question.author_id != current_user.id:
                # Notificação geral de revisão (qualquer alteração)
                if should_notify_revision:
                    NotificationService.create_notification(
                        db=db,
                        user_id=question.author_id,
                        notification_type=NotificationType.QUESTION_REVISED,
                        title="Sua questão foi revisada",
                        message=f"A questão '{question.name}' foi revisada por {current_user.name}",
                        entity_type=EntityType.QUESTION,
                        entity_id=question.id,
                        triggered_by_user_id=current_user.id
                    )

        if 'reviewer_comments' in update_data and update_data['reviewer_comments']:
            if question.author_id != current_user.id:
                NotificationService.create_notification(
                    db=db,
                    user_id=question.author_id,
                    notification_type=NotificationType.QUESTION_COMMENTED,
                    title="Sua questão recebeu um comentário",
                    message=f"Novo comentário sobre a questão '{question.name}': {update_data['reviewer_comments'][:100]}",
                    entity_type=EntityType.QUESTION,
                    entity_id=question.id,
                    triggered_by_user_id=current_user.id
                )

        if 'category_id' in update_data and update_data['category_id'] == 2:
            if question.author_id != current_user.id:
                NotificationService.create_notification(
                    db=db,
                    user_id=question.author_id,
                    notification_type=NotificationType.QUESTION_APPROVED,
                    title="Sua questão foi aprovada!",
                    message=f"A questão '{question.name}' foi aprovada!",
                    entity_type=EntityType.QUESTION,
                    entity_id=question.id,
                    triggered_by_user_id=current_user.id
                )

        return question

    @staticmethod
    def delete_question(
        db: Session,
        question_id: int,
        current_user: User
    ) -> Question:
        """Remove questão."""
        question = QuestionService.get_question_by_id(db, question_id, current_user)

        if current_user.role == UserRole.PROFESSOR:
            if question.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode deletar suas próprias questões")
        elif current_user.role == UserRole.REVISOR:
            pass
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para deletar esta questão")

        from app.models.associations import ExamQuestion
        exam_usage = db.query(ExamQuestion).filter(
            ExamQuestion.question_id == question_id
        ).first()
        if exam_usage:
            raise ConflictException(
                "Questão não pode ser deletada pois está sendo usada em provas"
            )

        db.delete(question)
        db.commit()

        return question

    @staticmethod
    def approve_question(
        db: Session,
        question_id: int,
        current_user: User
    ) -> Question:
        """Aprova questão (REVISOR e ADMIN)."""
        question = QuestionService.get_question_by_id(db, question_id, current_user)

        user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        if user_role not in ["ADMIN", "REVISOR"]:
            raise ForbiddenException("Sem permissão para aprovar questões")

        # ── O SEGREDO ESTÁ AQUI ────────────────────────────────────────────────
        # Se o seu Frontend pesquisa a aba 'Aprovadas' mandando category_id=2 na URL, 
        # nós DEVEMOS salvar a questão com o ID 2, ignorando a busca por nome.
        question.category_id = 2 
        question.reviewed_by_id = current_user.id 

        # IMPORTANTE: Se você usa um loop 'setattr' de um schema Pydantic antes daqui, 
        # certifique-se de que ele não está sobrescrevendo o reviewed_by_id de volta para None!

        # 2. Cria a Notificação para o Autor
        from models.notification import Notification # Certifique-se de importar seu model corretamente

        nova_notificacao = Notification(
            user_id=question.author_id,             # O dono da questão que vai receber
            triggered_by_user_id=current_user.id,   # O revisor que disparou a ação
            type="QUESTION_REVIEWED",               # Ajuste para o texto/Enum que seu banco usa
            title="Questão Avaliada",
            message=f"Sua questão '{question.name}' foi avaliada e atualizada pelo revisor.",
            entity_type="question",
            entity_id=question.id,
            is_read=False
        )
        
        # 3. Adiciona a notificação na "fila" do banco
        db.add(nova_notificacao)

        # 4. Salva a atualização da questão E a nova notificação JUNTAS
        db.commit()
        db.refresh(question)

        # ── CORREÇÃO 3 (Opcional, mas recomendada) ──────────────────────────────
        # Adicionei o disparo de notificação aqui também, pois estava faltando 
        # na rota de aprovação direta.
        if question.author_id != current_user.id:
            NotificationService.create_notification(
                db=db,
                user_id=question.author_id,
                notification_type=NotificationType.QUESTION_APPROVED,
                title="Sua questão foi aprovada!",
                message=f"A questão '{question.name}' foi aprovada!",
                entity_type=EntityType.QUESTION,
                entity_id=question.id,
                triggered_by_user_id=current_user.id
            )

        return question

    @staticmethod
    def get_question_stats(db: Session) -> dict:
        """Estatísticas de questões."""
        total_questions = db.query(Question).count()

        categories_stats = {}
        for category in db.query(Category).all():
            count = db.query(Question).filter(
                Question.category_id == category.id
            ).count()
            categories_stats[category.name] = count

        difficulty_stats = {}
        for level in DifficultyLevel:
            count = db.query(Question).filter(
                Question.difficulty_level == level
            ).count()
            difficulty_stats[f"nivel_{level.value}"] = count

        grau_stats = {}
        for grau in db.query(Grau).all():
            count = db.query(Question).filter(
                Question.grau_id == grau.id
            ).count()
            grau_stats[grau.name] = count

        return {
            "total_questions": total_questions,
            "by_category": categories_stats,
            "by_difficulty": difficulty_stats,
            "by_grau": grau_stats
        }