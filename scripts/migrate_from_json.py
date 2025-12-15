"""Script para migrar dados do db.json para PostgreSQL."""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, Question, Category, Grau, Exam, ExamQuestion
from app.models.user import UserRole
from app.models.question import DifficultyLevel
from app.models.exam import ExamStatus
from app.core.security import get_password_hash
import logging
 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_json_data(json_path: str) -> dict:
    """Carrega dados do arquivo JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"❌ Arquivo {json_path} não encontrado!")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"❌ Erro ao decodificar JSON: {e}")
        return {}


def migrate_users(db: Session, data: dict):
    """Migra usuários do JSON."""
    logger.info("👥 Migrando usuários...")
    
    users_data = data.get('users', [])
    migrated = 0
    
    for user_json in users_data:
        existing = db.query(User).filter(User.email == user_json['email']).first()
        if existing:
            logger.info(f"  ⏭️  Usuário já existe: {user_json['email']}")
            continue
        
        user = User(
            name=user_json.get('name', 'Usuário Migrado'),
            email=user_json['email'],
            password_hash=get_password_hash(user_json.get('password', 'TempPass@123')),
            role=UserRole.PROFESSOR,  # Role padrão
            is_active=True,
            is_email_verified=True
        )
        
        db.add(user)
        migrated += 1
        logger.info(f"  ✓ Usuário migrado: {user_json['email']}")
    
    db.commit()
    logger.info(f"✅ {migrated} usuários migrados!")


def migrate_questions(db: Session, data: dict):
    """Migra questões do JSON.""" 
    logger.info("📝 Migrando questões...")
    
    # Busca IDs das categorias e graus
    categoria_aprovada = db.query(Category).filter(Category.name == "Aprovada").first()
    categoria_pendente = db.query(Category).filter(Category.name == "Pendente").first()
    grau_fund2 = db.query(Grau).filter(Grau.name == "Fundamental II").first()
    admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
    
    if not all([categoria_aprovada, categoria_pendente, grau_fund2, admin_user]):
        logger.error("❌ Dados básicos (categorias, graus, admin) não encontrados!")
        return
    
    # Migra questões aprovadas
    questoes_data = data.get('questõesAprovadas', [])
    migrated = 0
    
    for questao_json in questoes_data:
        questao = Question(
            name=questao_json.get('name', 'Questão Migrada'),
            professor_name=questao_json.get('professorName', 'Professor Migrado'),
            serie_ano=questao_json.get('serieAno', '9º ano'),
            phase_level=questao_json.get('phaseLevel', '3ª fase'),
            difficulty_level=DifficultyLevel(questao_json.get('difficultyLevel', 3)),
            bncc_theme=questao_json.get('bnccTheme', 'Matemática'),
            knowledge_objects=questao_json.get('knowledgeObjects', 'Não especificado'),
            ability_code=questao_json.get('abilityCode', 'EF09MA01'),
            ability_description=questao_json.get('abilityDescription', 'Habilidade migrada'),
            question_statement=questao_json.get('questionStatement', 'Enunciado migrado'),
            alternatives=questao_json.get('alternatives', 'a) Op1 b) Op2 c) Op3 d) Op4 e) Op5'),
            correct_alternative=questao_json.get('correctAlternative', 'a'),
            detailed_resolution=questao_json.get('detailedResolution', 'Resolução migrada'),
            category_id=categoria_aprovada.id,
            grau_id=grau_fund2.id,
            author_id=admin_user.id
        )
        
        db.add(questao)
        migrated += 1
        logger.info(f"  ✓ Questão migrada: {questao_json.get('name', 'Sem nome')[:50]}...")
    
    # Migra questões pendentes
    questoes_pendentes = data.get('projects', [])
    
    for questao_json in questoes_pendentes:
        questao = Question(
            name=questao_json.get('name', 'Questão Pendente'),
            professor_name=questao_json.get('professorName', 'Professor Migrado'),
            serie_ano=questao_json.get('serieAno', '9º ano'),
            phase_level=questao_json.get('phaseLevel', '3ª fase'),
            difficulty_level=DifficultyLevel(questao_json.get('difficultyLevel', 3)),
            bncc_theme=questao_json.get('bnccTheme', 'Matemática'),
            knowledge_objects=questao_json.get('knowledgeObjects', 'Não especificado'),
            ability_code=questao_json.get('abilityCode', 'EF09MA01'),
            ability_description=questao_json.get('abilityDescription', 'Habilidade migrada'),
            question_statement=questao_json.get('questionStatement', 'Enunciado migrado'),
            alternatives=questao_json.get('alternatives', 'a) Op1 b) Op2 c) Op3 d) Op4 e) Op5'),
            correct_alternative=questao_json.get('correctAlternative', 'a'),
            detailed_resolution=questao_json.get('detailedResolution', 'Resolução migrada'),
            category_id=categoria_pendente.id,
            grau_id=grau_fund2.id,
            author_id=admin_user.id
        )
        
        db.add(questao)
        migrated += 1
        logger.info(f"  ✓ Questão pendente migrada: {questao_json.get('name', 'Sem nome')[:50]}...")
    
    db.commit()
    logger.info(f"✅ {migrated} questões migradas!")


def migrate_exams(db: Session, data: dict):
    """Migra provas do JSON."""
    logger.info("🎯 Migrando provas...")
    
    admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if not admin_user:
        logger.error("❌ Usuário admin não encontrado!")
        return
    
    provas_data = data.get('provasMontadas', [])
    migrated = 0
    
    for prova_json in provas_data:
        # Cria prova
        prova = Exam(
            name=prova_json.get('name', 'Prova Migrada'),
            fase=prova_json.get('fase', '3ª fase'),
            anos=prova_json.get('anos', ['9º']),
            status=ExamStatus.PENDENTE,
            description=f"Prova migrada do sistema anterior",
            author_id=admin_user.id,
            total_questions=len(prova_json.get('questoes', []))
        )
        
        db.add(prova)
        db.commit()  # Commit para obter ID
        
        # Adiciona questões à prova
        questoes_prova = prova_json.get('questoes', [])
        for i, questao_json in enumerate(questoes_prova):
            # Tenta encontrar questão por nome
            questao = db.query(Question).filter(
                Question.name == questao_json.get('name', '')
            ).first()
            
            if questao:
                exam_question = ExamQuestion(
                    exam_id=prova.id,
                    question_id=questao.id,
                    order_index=i + 1
                )
                db.add(exam_question)
        
        migrated += 1
        logger.info(f"  ✓ Prova migrada: {prova_json.get('name', 'Sem nome')}")
    
    db.commit()
    logger.info(f"✅ {migrated} provas migradas!")


def main():
    """Função principal da migração."""
    if len(sys.argv) < 2:
        logger.error("❌ Uso: python migrate_from_json.py <caminho_para_db.json>")
        return
    
    json_path = sys.argv[1]
    logger.info(f"🔄 Iniciando migração de {json_path}...")
    
    # Carrega dados do JSON
    data = load_json_data(json_path)
    if not data:
        return
    
    # Conecta ao banco
    db = SessionLocal()
    
    try:
        # Executa migrações
        migrate_users(db, data)
        migrate_questions(db, data) 
        migrate_exams(db, data)
        
        logger.info("🎉 Migração concluída com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro durante migração: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()

