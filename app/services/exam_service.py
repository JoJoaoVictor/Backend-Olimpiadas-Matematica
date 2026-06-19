"""Serviços de gerenciamento de provas."""

import base64
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc, or_, and_, func 
from app.models.category import Category
from app.schemas.exam import ExamResponse
from app.models.exam import Exam, ExamStatus
from app.models.question import Question
from app.models.user import User, UserRole
from app.models.associations import ExamQuestion
from app.schemas.exam import ExamCreate, ExamUpdate, ExamFilters, ExamQuestionUpdate
from app.core.exceptions import NotFoundException, ForbiddenException, ConflictException, ValidationException
from app.core.config import settings
from app.models.notification import NotificationType, EntityType
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def _path_to_file(upload_root: Path, stored_path: str) -> Path:
    relative = stored_path.removeprefix("/uploads/").removeprefix("uploads/")
    return upload_root / relative


class ExamService:

    @staticmethod
    def create_exam(db: Session, exam_data: ExamCreate, current_user: User) -> Exam:
        try:
            questions = db.query(Question.id).filter(
                Question.id.in_(exam_data.question_ids)
            ).all()
            
            if len(questions) != len(exam_data.question_ids):
                found_ids = {q.id for q in questions}
                missing_ids = set(exam_data.question_ids) - found_ids
                raise NotFoundException(f"Questões não encontradas: {list(missing_ids)}")

            exam = Exam(
                name=exam_data.name,
                description=exam_data.description,
                author_id=current_user.id,
                fase=exam_data.fase,
                anos=exam_data.anos,
                ano=getattr(exam_data, 'ano', None),
                total_questions=len(exam_data.question_ids),
                status=exam_data.status or ExamStatus.PENDENTE 
            )
            db.add(exam)
            db.flush()

            exam_questions = [
                ExamQuestion(exam_id=exam.id, question_id=qid, order_index=i + 1)
                for i, qid in enumerate(exam_data.question_ids)
            ]
            if exam_questions:
                db.bulk_save_objects(exam_questions)

            if exam_data.question_ids:
                category_applied = db.query(Category).filter(
                    func.lower(Category.name) == "aplicadas"
                ).first()

                if category_applied:
                    db.query(Question).filter(
                        Question.id.in_(exam_data.question_ids)
                    ).update({"category_id": category_applied.id}, synchronize_session=False)
                else:
                    logger.warning(
                        "⚠️ Categoria 'Aplicadas' não encontrada no banco. "
                        "As questões foram vinculadas à prova, mas o status da categoria não foi alterado."
                    )

            db.commit()
            db.refresh(exam)
            logger.info(f"Prova criada com sucesso: {exam.id} por usuário {current_user.id}")
            return exam

        except Exception as e:
            db.rollback()
            logger.error(f"Erro interno ao criar prova: {str(e)}")
            raise e
        
    @staticmethod
    def get_exams(db: Session, filters: ExamFilters, current_user: User) -> Dict[str, Any]:
        query = db.query(Exam).options(
            selectinload(Exam.author).selectinload(User.profile),
            selectinload(Exam.exam_questions).selectinload(ExamQuestion.question)
        )

        # ── BLINDAGEM DE LISTAGEM ──────────────────────────────────────────────
        # REMOVIDA: A trava do PROFESSOR. Agora eles podem ver a lista global.
        
        if current_user.role == UserRole.REVISOR:
            # TRAVA REVISOR: Vê provas Pendentes OU Aprovadas por ele mesmo
            query = query.filter(
                or_(
                    Exam.status == ExamStatus.PENDENTE,
                    and_(Exam.status == ExamStatus.APROVADA, getattr(Exam, 'reviewed_by_id', Exam.author_id) == current_user.id)
                )
            )

        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(Exam.name.ilike(search_term), Exam.description.ilike(search_term))
            )

        if filters.status:
            query = query.filter(Exam.status == filters.status)

        if filters.fase:
            query = query.filter(Exam.fase.ilike(f"%{filters.fase}%"))

        if filters.anos:
            for ano in filters.anos:
                query = query.filter(Exam.anos.contains(ano))

        if filters.author_id and current_user.role == UserRole.ADMIN:
            query = query.filter(Exam.author_id == filters.author_id)

        total = query.count()
        query = query.order_by(desc(Exam.created_at))
        exams = query.offset(
            (filters.page - 1) * filters.per_page
        ).limit(filters.per_page).all()

        exam_schemas = [ExamResponse.from_orm(exam) for exam in exams]
        pages = (total + filters.per_page - 1) // filters.per_page

        return {
            "exams": exam_schemas,
            "total": total,
            "page": filters.page,
            "per_page": filters.per_page,
            "pages": pages,
        }

    @staticmethod
    def get_exam_by_id(db: Session, exam_id: int, current_user: User) -> Exam:
        exam = db.query(Exam).options(
            selectinload(Exam.author).selectinload(User.profile),
            selectinload(Exam.exam_questions).selectinload(ExamQuestion.question)
        ).filter(Exam.id == exam_id).first()

        if not exam:
            raise NotFoundException("Prova não encontrada")

        # ── BLINDAGEM DE ACESSO DIRETO ─────────────────────────────────────────
        # REMOVIDA: A trava do PROFESSOR. Agora eles podem acessar provas de outros.

        if current_user.role == UserRole.REVISOR:
            if exam.status == ExamStatus.APLICADA:
                raise ForbiddenException("Revisores não têm permissão para visualizar provas aplicadas")
            if exam.status == ExamStatus.APROVADA and getattr(exam, 'reviewed_by_id', None) != current_user.id:
                raise ForbiddenException("Revisores só podem visualizar provas aprovadas por eles mesmos")

        return exam

    @staticmethod
    def update_exam(db: Session, exam_id: int, exam_data: ExamUpdate, current_user: User) -> Exam:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        if current_user.role == UserRole.PROFESSOR and exam.author_id != current_user.id:
            raise ForbiddenException("Você não tem permissão para editar esta prova")

        if exam_data.name is not None:
            exam.name = exam_data.name
        if exam_data.description is not None:
            exam.description = exam_data.description
        if exam_data.fase is not None:
            exam.fase = exam_data.fase
        if hasattr(exam_data, 'ano') and getattr(exam_data, 'ano') is not None:
            exam.ano = getattr(exam_data, 'ano')
        if exam_data.anos is not None:
            exam.anos = exam_data.anos
        if exam_data.status is not None:
            exam.status = exam_data.status
        if hasattr(exam_data, 'reviewer_comments') and exam_data.reviewer_comments is not None:
            exam.reviewer_comments = exam_data.reviewer_comments
            
        if current_user.role in [UserRole.REVISOR, UserRole.ADMIN] and exam_data.status == ExamStatus.APROVADA:
            if hasattr(exam, 'reviewed_by_id'):
                exam.reviewed_by_id = current_user.id
      
        status_str = str(exam.status).replace("ExamStatus.", "").upper()
        
        questions_to_update = db.query(ExamQuestion.question_id).filter(
            ExamQuestion.exam_id == exam.id
        ).all()
        question_ids = [q.question_id for q in questions_to_update]
        
        if question_ids:
            if status_str in ["APROVADA", "APLICADA"]:
                category_applied = db.query(Category).filter(
                    func.lower(Category.name) == "aplicadas"
                ).first()

                if not category_applied:
                    category_applied = Category(name="Aplicadas", description="Questões oficiais", color="#28a745")
                    db.add(category_applied)
                    db.flush()

                db.query(Question).filter(
                    Question.id.in_(question_ids)
                ).update({"category_id": category_applied.id}, synchronize_session=False)
                
            elif status_str in ["PENDENTE"]:
                still_in_use = db.query(ExamQuestion.question_id).join(
                    Exam, Exam.id == ExamQuestion.exam_id
                ).filter(
                    ExamQuestion.question_id.in_(question_ids),
                    Exam.id != exam.id, 
                    Exam.status.in_([ExamStatus.APROVADA, ExamStatus.APLICADA])
                ).all()
                
                still_in_use_ids = {q[0] for q in still_in_use}
                ids_to_revert = list(set(question_ids) - still_in_use_ids)
                
                if ids_to_revert:
                    db.query(Question).filter(
                        Question.id.in_(ids_to_revert)
                    ).update({"category_id": 2}, synchronize_session=False)

        db.commit()
        db.refresh(exam)
        return exam
    
    @staticmethod
    def update_exam_questions(
        db: Session, exam_id: int, questions_data: List[ExamQuestionUpdate], current_user: User
    ) -> Exam:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        if current_user.role == UserRole.PROFESSOR and exam.author_id != current_user.id:
            raise ForbiddenException("Você não tem permissão para editar esta prova")

        pure_ids = [q.question_id for q in questions_data]
        q_data_dict = {q.question_id: q for q in questions_data}

        if pure_ids:
            existing_questions = db.query(Question.id).filter(Question.id.in_(pure_ids)).all()
            existing_ids = [q[0] for q in existing_questions]
            missing = set(pure_ids) - set(existing_ids)
            if missing:
                raise NotFoundException(f"Questões não encontradas: {missing}")

        current_eqs = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).all()
        current_eq_dict = {eq.question_id: eq for eq in current_eqs}
        current_ids = list(current_eq_dict.keys())

        ids_to_remove = set(current_ids) - set(pure_ids)
        ids_to_add = set(pure_ids) - set(current_ids)

        if ids_to_remove:
            db.query(ExamQuestion).filter(
                ExamQuestion.exam_id == exam.id,
                ExamQuestion.question_id.in_(ids_to_remove)
            ).delete(synchronize_session=False)

        for q_id in ids_to_add:
            data = q_data_dict[q_id]
            new_eq = ExamQuestion(
                exam_id=exam.id, 
                question_id=q_id, 
                order_index=0,
                hide_alternatives=data.hide_alternatives 
            )
            db.add(new_eq)

        db.flush()

        for index, q_id in enumerate(pure_ids):
            data = q_data_dict[q_id]
            db.query(ExamQuestion).filter(
                ExamQuestion.exam_id == exam.id,
                ExamQuestion.question_id == q_id
            ).update({
                "order_index": index + 1,
                "hide_alternatives": data.hide_alternatives 
            }, synchronize_session=False)

        exam.total_questions = len(pure_ids)
        status_str = str(exam.status).replace("ExamStatus.", "").upper()
        
        if status_str in ["APROVADA", "APLICADA"] and pure_ids:
            category_applied = db.query(Category).filter(func.lower(Category.name) == "aplicadas").first()
            if not category_applied:
                category_applied = Category(name="Aplicadas", description="Em provas oficiais", color="#28a745")
                db.add(category_applied)
                db.flush()
                
            db.query(Question).filter(
                Question.id.in_(pure_ids)
            ).update({"category_id": category_applied.id}, synchronize_session=False)

        if ids_to_remove:
            still_in_use = db.query(ExamQuestion.question_id).join(
                Exam, Exam.id == ExamQuestion.exam_id
            ).filter(
                ExamQuestion.question_id.in_(list(ids_to_remove)),
                Exam.id != exam.id,
                Exam.status.in_([ExamStatus.APROVADA, ExamStatus.APLICADA])
            ).all()
            
            still_in_use_ids = {q[0] for q in still_in_use}
            ids_to_revert = list(set(ids_to_remove) - still_in_use_ids)

            if ids_to_revert:
                db.query(Question).filter(
                    Question.id.in_(ids_to_revert)
                ).update({"category_id": 2}, synchronize_session=False)

        db.commit()
        db.refresh(exam)
        return exam
    
    @staticmethod
    def update_exam_layout(
        db: Session,
        exam_id: int,
        current_user: User,
        header_image_b64: Optional[str] = None,
        footer_image_b64: Optional[str] = None,
        header_size: float = 100.0,
        footer_size: float = 100.0,
    ) -> Exam:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        if current_user.role == UserRole.PROFESSOR:
            if exam.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode editar suas próprias provas")
        elif current_user.role == UserRole.REVISOR:
            pass
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta prova")

        upload_root = Path(settings.UPLOAD_PATH)

        def _apagar(stored_path: Optional[str]) -> None:
            if not stored_path:
                return
            file_path = _path_to_file(upload_root, stored_path)
            if file_path.exists():
                file_path.unlink()

        def _salvar(b64_string: str, tipo: str, path_atual: Optional[str]) -> str:
            if "," in b64_string:
                header_part, data_part = b64_string.split(",", 1)
                ext = ".jpg" if ("jpeg" in header_part or "jpg" in header_part) else ".png"
            else:
                data_part, ext = b64_string, ".png"

            try:
                image_bytes = base64.b64decode(data_part)
            except Exception:
                raise ValidationException("Imagem inválida — falha ao decodificar base64.")

            if len(image_bytes) > 5 * 1024 * 1024:
                raise ValidationException("Imagem do layout não pode exceder 5MB.")

            _apagar(path_atual)

            dest_dir = upload_root / "layouts" / tipo
            dest_dir.mkdir(parents=True, exist_ok=True)

            filename  = f"exam_{exam_id}_{tipo}_{uuid.uuid4().hex[:8]}{ext}"
            file_path = dest_dir / filename

            with open(file_path, "wb") as f:
                f.write(image_bytes)

            return f"/uploads/layouts/{tipo}/{filename}"

        if header_image_b64 is not None:
            if header_image_b64 == "":
                _apagar(exam.header_image)
                exam.header_image = None
            else:
                exam.header_image = _salvar(header_image_b64, "header", exam.header_image)

        if footer_image_b64 is not None:
            if footer_image_b64 == "":
                _apagar(exam.footer_image)
                exam.footer_image = None
            else:
                exam.footer_image = _salvar(footer_image_b64, "footer", exam.footer_image)

        exam.header_size = max(50.0, min(150.0, float(header_size)))
        exam.footer_size = max(50.0, min(150.0, float(footer_size)))

        try:
            db.commit()
            db.refresh(exam)

            if current_user.role in [UserRole.REVISOR, UserRole.ADMIN]:
                if exam.author_id != current_user.id:
                    NotificationService.create_notification(
                        db=db,
                        user_id=exam.author_id,
                        notification_type=NotificationType.EXAM_REVISED,
                        title="Layout da Prova Atualizado",
                        message=f"{current_user.name} atualizou o layout da prova '{exam.name}'",
                        entity_type=EntityType.EXAM,
                        entity_id=exam.id,
                        triggered_by_user_id=current_user.id
                    )
            return exam
        except Exception as e:
            db.rollback()
            raise e
    
    @staticmethod
    def delete_exam(db: Session, exam_id: int, current_user: User) -> Exam:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        if current_user.role == UserRole.PROFESSOR:
            if exam.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode deletar suas próprias provas")
        elif current_user.role == UserRole.REVISOR:
            pass
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para deletar esta prova")

        if exam.status == ExamStatus.APLICADA:
            raise ConflictException("Prova aplicada não pode ser deletada")

        questions_in_exam = db.query(ExamQuestion.question_id).filter(
            ExamQuestion.exam_id == exam.id
        ).all()
        
        question_ids = [q.question_id for q in questions_in_exam]
        
        if question_ids:
            still_in_use = db.query(ExamQuestion.question_id).join(
                Exam, Exam.id == ExamQuestion.exam_id
            ).filter(
                ExamQuestion.question_id.in_(question_ids),
                Exam.id != exam.id,
                Exam.status.in_([ExamStatus.APROVADA, ExamStatus.APLICADA])
            ).all()
            
            still_in_use_ids = {q[0] for q in still_in_use}
            ids_to_revert = list(set(question_ids) - still_in_use_ids)

            if ids_to_revert:
                db.query(Question).filter(
                    Question.id.in_(ids_to_revert)
                ).update({"category_id": 2}, synchronize_session=False)

        upload_root = Path(settings.UPLOAD_PATH)
        for field in ("header_image", "footer_image"):
            path_val = getattr(exam, field, None)
            if path_val:
                file_path = _path_to_file(upload_root, path_val)
                if file_path.exists():
                    file_path.unlink()

        db.delete(exam)
        db.commit()
        return exam
    
    @staticmethod
    def change_exam_status(
        db: Session, exam_id: int, new_status: ExamStatus, current_user: User
    ) -> Exam:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        if new_status == ExamStatus.APROVADA and current_user.role not in [UserRole.ADMIN, UserRole.REVISOR]:
            raise ForbiddenException("Apenas administradores e revisores podem aprovar provas")

        if current_user.role == UserRole.PROFESSOR:
            if exam.author_id != current_user.id:
                raise ForbiddenException(
                    "PROFESSOR só pode alterar status de suas próprias provas"
                )

        exam.status = new_status

        if new_status == ExamStatus.APROVADA:
            if hasattr(exam, 'reviewed_by_id'):
                exam.reviewed_by_id = current_user.id

        status_str = str(exam.status).replace("ExamStatus.", "").upper()

        if status_str in ["APROVADA", "APLICADA"]:
            questions_to_update = db.query(ExamQuestion.question_id).filter(
                ExamQuestion.exam_id == exam.id
            ).all()
            
            question_ids = [q.question_id for q in questions_to_update]
            
            if question_ids:
                category_applied = db.query(Category).filter(
                    func.lower(Category.name) == "aplicadas"
                ).first()

                if not category_applied:
                    category_applied = Category(
                        name="Aplicadas", 
                        description="Questões já utilizadas em provas oficiais",
                        color="#28a745" 
                    )
                    db.add(category_applied)
                    db.flush() 

                db.query(Question).filter(
                    Question.id.in_(question_ids)
                ).update({"category_id": category_applied.id}, synchronize_session=False)

        db.commit()
        db.refresh(exam)

        if current_user.role in [UserRole.REVISOR, UserRole.ADMIN]:
            if exam.author_id != current_user.id:
                NotificationService.create_notification(
                    db=db,
                    user_id=exam.author_id,
                    notification_type=NotificationType.EXAM_REVISED,
                    title="Status da Prova Alterado",
                    message=f"{current_user.name} alterou o status da prova '{exam.name}' para {new_status.value}",
                    entity_type=EntityType.EXAM,
                    entity_id=exam.id,
                    triggered_by_user_id=current_user.id
                )
        return exam

    @staticmethod
    def get_exam_stats(db: Session, current_user: User) -> dict:
        query = db.query(Exam)
        
        # ── BLINDAGEM NO DASHBOARD DE ESTATÍSTICAS ─────────────────────────────
        # REMOVIDA: A trava do PROFESSOR. As estatísticas globais são exibidas.
            
        if current_user.role == UserRole.REVISOR:
            # TRAVA REVISOR
            query = query.filter(
                or_(
                    Exam.status == ExamStatus.PENDENTE,
                    and_(Exam.status == ExamStatus.APROVADA, getattr(Exam, 'reviewed_by_id', Exam.author_id) == current_user.id)
                )
            )

        total_exams = query.count()

        stats_query = db.query(Exam.status, func.count(Exam.id))
        
        # REMOVIDA: A trava do PROFESSOR nos detalhes por status.
            
        if current_user.role == UserRole.REVISOR:
            # TRAVA REVISOR NOS DETALHES POR STATUS
            stats_query = stats_query.filter(
                or_(
                    Exam.status == ExamStatus.PENDENTE,
                    and_(Exam.status == ExamStatus.APROVADA, getattr(Exam, 'reviewed_by_id', Exam.author_id) == current_user.id)
                )
            )

        stats_results = stats_query.group_by(Exam.status).all()
        status_stats  = {status.value: count for status, count in stats_results}

        for status in ExamStatus:
            if status.value not in status_stats:
                status_stats[status.value] = 0

        return {"total_exams": total_exams, "by_status": status_stats}