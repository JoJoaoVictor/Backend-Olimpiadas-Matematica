"""Serviços de gerenciamento de provas."""

import base64
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import desc, or_, func

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
    """
    Converte o path armazenado no banco (/uploads/layouts/header/xxx.png)
    para o path absoluto no disco usando removeprefix (Python 3.9+).
    """
    relative = stored_path.removeprefix("/uploads/").removeprefix("uploads/")
    return upload_root / relative


class ExamService:
    """Serviços de provas."""

    @staticmethod
    def create_exam(db: Session, exam_data: ExamCreate, current_user: User) -> Exam:
        try:
            questions = db.query(Question.id).filter(Question.id.in_(exam_data.question_ids)).all()
            found_ids = {q.id for q in questions}

            if len(found_ids) != len(exam_data.question_ids):
                missing_ids = set(exam_data.question_ids) - found_ids
                raise NotFoundException(f"Questões não encontradas: {list(missing_ids)}")

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
            db.flush()

            exam_questions = [
                ExamQuestion(exam_id=exam.id, question_id=question_id, order_index=i + 1)
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
    def get_exams(db: Session, filters: ExamFilters, current_user: User) -> Dict[str, Any]:
        query = db.query(Exam).options(
            selectinload(Exam.author),
            selectinload(Exam.exam_questions).selectinload(ExamQuestion.question)
        )

        if current_user.role == UserRole.PROFESSOR:
            query = query.filter(Exam.author_id == current_user.id)

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
        exams = query.offset((filters.page - 1) * filters.per_page).limit(filters.per_page).all()

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
            selectinload(Exam.author),
            selectinload(Exam.exam_questions).selectinload(ExamQuestion.question)
        ).filter(Exam.id == exam_id).first()

        if not exam:
            raise NotFoundException("Prova não encontrada")

        # REVISOR pode acessar qualquer prova
        # PROFESSOR só acessa suas próprias
        # ADMIN acessa qualquer uma
        if current_user.role == UserRole.PROFESSOR and exam.author_id != current_user.id:
            raise ForbiddenException("Sem permissão para acessar esta prova")

        return exam

    @staticmethod
    def update_exam(db: Session, exam_id: int, exam_data: ExamUpdate, current_user: User) -> Exam:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        # Verifica permissão (autor, revisor ou admin)
        # REVISOR pode editar qualquer prova
        # PROFESSOR só edita a própria
        # ADMIN edita qualquer uma
        if current_user.role == UserRole.PROFESSOR:
            if exam.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode editar suas próprias provas")
        elif current_user.role == UserRole.REVISOR:
            # REVISOR pode editar qualquer prova
            pass
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta prova")

        update_data = exam_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(exam, field, value)

        try:
            db.commit()
            db.refresh(exam)
            
            # Notifica autor se REVISOR/ADMIN editou
            if current_user.role in [UserRole.REVISOR, UserRole.ADMIN]:
                if exam.author_id != current_user.id:
                    NotificationService.create_notification(
                        db=db,
                        user_id=exam.author_id,
                        notification_type=NotificationType.EXAM_REVISED,
                        title="Prova Revisada",
                        message=f"{current_user.name} revisou a prova '{exam.name}'",
                        entity_type=EntityType.EXAM,
                        entity_id=exam.id,
                        triggered_by_user_id=current_user.id
                    )
            
            return exam
        except Exception as e:
            db.rollback()
            raise e

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
        """
        Salva imagens de cabeçalho/rodapé em disco e atualiza a prova.
        "" = restaurar padrão (apaga arquivo, limpa campo).
        None = não alterar o campo.
        """
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        # Verifica permissão (autor, revisor ou admin)
        # REVISOR pode editar layout de qualquer prova
        # PROFESSOR só edita suas próprias
        # ADMIN edita qualquer uma
        if current_user.role == UserRole.PROFESSOR:
            if exam.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode editar suas próprias provas")
        elif current_user.role == UserRole.REVISOR:
            # REVISOR pode editar layout de qualquer prova
            pass
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta prova")

        upload_root = Path(settings.UPLOAD_PATH)

        def _apagar(stored_path: Optional[str]) -> None:
            """Remove arquivo de layout do disco com segurança."""
            if not stored_path:
                return
            file_path = _path_to_file(upload_root, stored_path)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Layout removido do disco: {file_path}")

        def _salvar(b64_string: str, tipo: str, path_atual: Optional[str]) -> str:
            """Decodifica base64, remove arquivo anterior e salva novo."""
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

            # Remove arquivo anterior antes de criar o novo
            _apagar(path_atual)

            dest_dir = upload_root / "layouts" / tipo
            dest_dir.mkdir(parents=True, exist_ok=True)

            filename  = f"exam_{exam_id}_{tipo}_{uuid.uuid4().hex[:8]}{ext}"
            file_path = dest_dir / filename

            with open(file_path, "wb") as f:
                f.write(image_bytes)

            return f"/uploads/layouts/{tipo}/{filename}"

        # ── Cabeçalho ──────────────────────────────────────────────────────
        if header_image_b64 is not None:
            if header_image_b64 == "":
                _apagar(exam.header_image)
                exam.header_image = None
            else:
                exam.header_image = _salvar(header_image_b64, "header", exam.header_image)

        # ── Rodapé ─────────────────────────────────────────────────────────
        if footer_image_b64 is not None:
            if footer_image_b64 == "":
                _apagar(exam.footer_image)
                exam.footer_image = None
            else:
                exam.footer_image = _salvar(footer_image_b64, "footer", exam.footer_image)

        # ── Tamanhos ────────────────────────────────────────────────────────
        exam.header_size = max(50.0, min(150.0, float(header_size)))
        exam.footer_size = max(50.0, min(150.0, float(footer_size)))

        try:
            db.commit()
            db.refresh(exam)
            logger.info(f"Layout da prova {exam_id} atualizado por usuário {current_user.id}")
            
            # Notifica autor se REVISOR/ADMIN editou layout
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
    def update_exam_questions(
        db: Session,
        exam_id: int,
        questions_data: ExamQuestionUpdate,
        current_user: User,
    ) -> Exam:
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        # Verifica permissão (autor, revisor ou admin)
        # REVISOR pode editar questões de qualquer prova
        # PROFESSOR só edita suas próprias
        # ADMIN edita qualquer uma
        if current_user.role == UserRole.PROFESSOR:
            if exam.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode editar suas próprias provas")
        elif current_user.role == UserRole.REVISOR:
            # REVISOR pode editar questões de qualquer prova
            pass
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para editar esta prova")

        questions = db.query(Question.id).filter(
            Question.id.in_(questions_data.question_ids)
        ).all()

        if len(questions) != len(questions_data.question_ids):
            found_ids = {q.id for q in questions}
            missing_ids = set(questions_data.question_ids) - found_ids
            raise NotFoundException(f"Questões não encontradas: {list(missing_ids)}")

        try:
            db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).delete()

            new_associations = [
                ExamQuestion(exam_id=exam_id, question_id=qid, order_index=i + 1)
                for i, qid in enumerate(questions_data.question_ids)
            ]

            if new_associations:
                db.bulk_save_objects(new_associations)

            exam.total_questions = len(questions_data.question_ids)
            db.commit()
            db.refresh(exam)
            
            # Notifica autor se REVISOR/ADMIN editou questões
            if current_user.role in [UserRole.REVISOR, UserRole.ADMIN]:
                if exam.author_id != current_user.id:
                    NotificationService.create_notification(
                        db=db,
                        user_id=exam.author_id,
                        notification_type=NotificationType.EXAM_REVISED,
                        title="Questões da Prova Atualizadas",
                        message=f"{current_user.name} atualizou as questões da prova '{exam.name}'",
                        entity_type=EntityType.EXAM,
                        entity_id=exam.id,
                        triggered_by_user_id=current_user.id
                    )
            
            return exam

        except Exception as e:
            db.rollback()
            logger.error(f"Erro ao atualizar questões da prova {exam_id}: {str(e)}")
            raise e

    @staticmethod
    def delete_exam(db: Session, exam_id: int, current_user: User) -> Exam:
        """Remove prova e seus arquivos de layout."""
        exam = ExamService.get_exam_by_id(db, exam_id, current_user)

        # Verifica permissão (autor, revisor ou admin)
        # REVISOR pode deletar qualquer prova
        # PROFESSOR só deleta suas próprias
        # ADMIN deleta qualquer uma
        if current_user.role == UserRole.PROFESSOR:
            if exam.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode deletar suas próprias provas")
        elif current_user.role == UserRole.REVISOR:
            # REVISOR pode deletar qualquer prova
            pass
        elif current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Sem permissão para deletar esta prova")

        if exam.status == ExamStatus.APLICADA:
            raise ConflictException("Prova aplicada não pode ser deletada")

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

        # Apenas ADMIN pode mudar status para APROVADA
        if new_status == ExamStatus.APROVADA and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("Apenas administradores podem aprovar provas")

        # REVISOR pode mudar status de qualquer prova (exceto APROVADA)
        # PROFESSOR só muda status de suas próprias provas
        # ADMIN pode mudar status de qualquer prova
        if current_user.role == UserRole.PROFESSOR:
            if exam.author_id != current_user.id:
                raise ForbiddenException("PROFESSOR só pode alterar status de suas próprias provas")

        exam.status = new_status
        db.commit()
        db.refresh(exam)
        
        # Notifica autor se REVISOR/ADMIN mudou status
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

        if current_user.role == UserRole.PROFESSOR:
            query = query.filter(Exam.author_id == current_user.id)

        total_exams = query.count()

        stats_query = db.query(Exam.status, func.count(Exam.id))

        if current_user.role == UserRole.PROFESSOR:
            stats_query = stats_query.filter(Exam.author_id == current_user.id)

        stats_results = stats_query.group_by(Exam.status).all()
        status_stats  = {status.value: count for status, count in stats_results}

        for status in ExamStatus:
            if status.value not in status_stats:
                status_stats[status.value] = 0

        return {"total_exams": total_exams, "by_status": status_stats}