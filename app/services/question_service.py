"""Serviços de gerenciamento de questões."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc
from sqlalchemy import or_, and_, desc

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
        """Cria nova questão salvando o snapshot do autor e localização."""
        category = db.query(Category).filter(Category.id == question_data.category_id).first()
        if not category:
            raise NotFoundException("Categoria não encontrada")

        grau = db.query(Grau).filter(Grau.id == question_data.grau_id).first()
        if not grau:
            raise NotFoundException("Grau educacional não encontrado")

        # CAPTURA DO SNAPSHOT: Busca dados do perfil do usuário logado
        # Usamos getattr por segurança para o caso de o perfil não estar carregado
        user_profile = getattr(current_user, "profile", None)
        campus_atual = user_profile.campus if user_profile else None
        cidade_atual = user_profile.cidade if user_profile else None

        question = Question(
            **question_data.dict(exclude={
                'image_id', 'professor_name', 'author_id', 'author_campus', 'author_cidade'
            }),
            author_id=current_user.id,
            professor_name=current_user.name,   
            author_campus=campus_atual,       
            author_cidade=cidade_atual,         
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
        from sqlalchemy import or_, and_, desc # 🌟 Certifique-se de que and_ está importado

        query = db.query(Question).options(
            joinedload(Question.category),
            joinedload(Question.grau),
            joinedload(Question.author),
            joinedload(Question.image)
        )

        # ── FILTRO POR ROLE ───────────────────────────────────────────────────
        user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

        if user_role == "STUDENT":
            # STUDENT vê apenas as próprias questões.
            query = query.filter(Question.author_id == current_user.id)

        elif user_role == "PROFESSOR":
            # PROFESSOR vê todas as questões, igual ao ADMIN.
            pass

        elif user_role == "REVISOR":
            #  TRAVA 1: Revisor NUNCA vê questões "Aplicadas" (category_id == 3)
            query = query.filter(Question.category_id != 3)

            # TRAVA 2: Se estiver na aba Aprovadas, vê apenas as que ele aprovou
            if filters.category_id == 2:
                query = query.filter(Question.reviewed_by_id == current_user.id)
            
            # TRAVA 3: Se estiver vendo "Todas as Questões" (sem filtro de aba)
            # Ele só pode ver as Pendentes (1) OU as Aprovadas (2) por ele mesmo
            elif not filters.category_id:
                query = query.filter(
                    or_(
                        Question.category_id == 1, # Todas as Pendentes
                        and_(
                            Question.category_id == 2, 
                            Question.reviewed_by_id == current_user.id
                        ) # Apenas Aprovadas por ele
                    )
                )

        # ADMIN: sem filtro adicional — vê tudo

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

        # ── TRAVAS DE SEGURANÇA POR ROLE ──────────────────────────────────────
        user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

        if user_role == "STUDENT" and question.author_id != current_user.id:
            raise ForbiddenException("Você não tem permissão para acessar esta questão")

        elif user_role == "REVISOR":
            # TRAVA 1: Revisor nunca vê questões Aplicadas (category_id == 3)
            if question.category_id == 3:
                raise ForbiddenException("Revisores não têm permissão para visualizar questões aplicadas")
            
            # TRAVA 2: Revisor só vê questões Aprovadas (category_id == 2) se ele mesmo aprovou
            if question.category_id == 2 and getattr(question, 'reviewed_by_id', None) != current_user.id:
                raise ForbiddenException("Revisores só podem visualizar questões aprovadas por eles mesmos")

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
        user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

        # Validação de permissões baseada na String da Role adaptada
        if user_role_str == "STUDENT":
            if question.author_id != current_user.id:
                raise ForbiddenException("Sem permissão para editar esta questão")
            if question.category_id == 2:
                raise ForbiddenException("Questões aprovadas não podem ser editadas")
        elif user_role_str == "PROFESSOR":
            pass # Permite que o professor edite qualquer questão
        elif user_role_str == "REVISOR":
            pass
        elif user_role_str != "ADMIN":
            raise ForbiddenException("Sem permissão para editar esta questão")

        update_data = question_data.dict(exclude_unset=True)

        if 'category_id' in update_data:
            category = db.query(Category).filter(
                Category.id == update_data['category_id']
            ).first()
            if not category:
                raise NotFoundException("Categoria não encontrada")

        should_notify_revision = False

        if user_role_str in ["REVISOR", "ADMIN"]:
            if update_data.get('category_id') == 2:
                update_data['reviewed_by_id'] = current_user.id

            if question.author_id != current_user.id:
                # Verifica se houve alteração real de conteúdo além do ID do revisor
                has_content_changes = any(
                    field not in ['reviewed_by_id']
                    for field in update_data.keys()
                )
                if has_content_changes:
                    should_notify_revision = True

        # Aplica as alterações no objeto do banco
        for field, value in update_data.items():
            setattr(question, field, value)

        db.commit()
        db.refresh(question)

        # ── DISPARO DE NOTIFICAÇÕES SEGURO (Prevenção de NotNullViolation) ────
        # Só tenta notificar se a questão possuir um autor e o autor não for quem está editando
        if question.author_id is not None and question.author_id != current_user.id:
            # 1. Notificação de Revisão de Conteúdo
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

            # 2. Notificação de Comentários inseridos
            if 'reviewer_comments' in update_data and update_data['reviewer_comments']:
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

            # 3. Notificação de Aprovação de Questão
            if 'category_id' in update_data and update_data['category_id'] == 2:
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
        user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

        if user_role_str == "STUDENT":
            if question.author_id != current_user.id:
                raise ForbiddenException("Sem permissão para deletar esta questão")
            if question.category_id == 2:
                raise ForbiddenException("Questões aprovadas não podem ser deletadas pelo autor")
        elif user_role_str == "PROFESSOR":
            if question.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode deletar suas próprias questões")
        elif user_role_str == "REVISOR":
            pass
        elif user_role_str != "ADMIN":
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

        question.category_id = 2
        question.reviewed_by_id = current_user.id

        # Só cria registros de notificação se houver um autor válido
        if question.author_id is not None:
            from app.models.notification import Notification

            nova_notificacao = Notification(
                user_id=question.author_id,
                triggered_by_user_id=current_user.id,
                type="QUESTION_REVIEWED",
                title="Questão Avaliada",
                message=f"Sua questão '{question.name}' foi avaliada e atualizada pelo revisor.",
                entity_type="question",
                entity_id=question.id,
                is_read=False
            )
            db.add(nova_notificacao)
            
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

        db.commit()
        db.refresh(question)
        return question

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
    def get_question_stats(db: Session, current_user: User) -> dict: # 🌟 Adicionado current_user
        """Estatísticas de questões."""
        from sqlalchemy import or_, and_

        # 1. Cria a query base dependendo do cargo
        base_query = db.query(Question)
        user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

        if user_role == "STUDENT":
            base_query = base_query.filter(Question.author_id == current_user.id)
            
        elif user_role == "REVISOR":
            # 🌟 O Revisor não contabiliza as Aplicadas (3) e nem as Aprovadas (2) por outros
            base_query = base_query.filter(
                or_(
                    Question.category_id == 1, # Pendentes
                    and_(
                        Question.category_id == 2, 
                        Question.reviewed_by_id == current_user.id
                    ) # Aprovadas por ele
                )
            )

        # 2. Usa a base_query blindada para fazer todas as contagens
        total_questions = base_query.count()

        categories_stats = {}
        for category in db.query(Category).all():
            count = base_query.filter(Question.category_id == category.id).count()
            categories_stats[category.name] = count

        difficulty_stats = {}
        for level in DifficultyLevel:
            count = base_query.filter(Question.difficulty_level == level).count()
            difficulty_stats[f"nivel_{level.value}"] = count

        grau_stats = {}
        for grau in db.query(Grau).all():
            count = base_query.filter(Question.grau_id == grau.id).count()
            grau_stats[grau.name] = count

        return {
            "total_questions": total_questions,
            "by_category": categories_stats,
            "by_difficulty": difficulty_stats,
            "by_grau": grau_stats
        }