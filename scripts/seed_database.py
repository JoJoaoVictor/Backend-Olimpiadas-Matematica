"""Script para popular o banco com dados iniciais."""

import asyncio
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models import Base, User, Category, Grau
from app.models.user import UserRole
from app.core.security import get_password_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

 
def create_tables():
    """Cria todas as tabelas do banco."""
    logger.info("🏗️  Criando tabelas...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tabelas criadas com sucesso!")


def seed_categories(db: Session):
    """Popula categorias iniciais."""
    logger.info("📁 Criando categorias...")
    
    categories = [
        {"name": "Pendente", "description": "Questões aguardando aprovação", "color": "#ffc107"},
        {"name": "Aprovada", "description": "Questões aprovadas para uso", "color": "#28a745"},
        {"name": "Rejeitada", "description": "Questões rejeitadas", "color": "#dc3545"},
        {"name": "Em Revisão", "description": "Questões sendo revisadas", "color": "#17a2b8"},
        {"name": "Arquivo", "description": "Questões arquivadas", "color": "#6c757d"},
    ]
    
    for cat_data in categories:
        existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
        if not existing:
            category = Category(**cat_data)
            db.add(category)
            logger.info(f"  ✓ Categoria criada: {cat_data['name']}")
    
    db.commit()
    logger.info("✅ Categorias criadas!")


def seed_graus(db: Session):
    """Popula graus educacionais."""
    logger.info("🎓 Criando graus educacionais...")
    
    graus = [
        {"name": "Fundamental I", "description": "1º ao 5º ano", "order_index": 1},
        {"name": "Fundamental II", "description": "6º ao 9º ano", "order_index": 2},
        {"name": "Ensino Médio", "description": "1º ao 3º ano do Ensino Médio", "order_index": 3},
    ]
    
    for grau_data in graus:
        existing = db.query(Grau).filter(Grau.name == grau_data["name"]).first()
        if not existing:
            grau = Grau(**grau_data)
            db.add(grau)
            logger.info(f"  ✓ Grau criado: {grau_data['name']}")
    
    db.commit()
    logger.info("✅ Graus criados!")


def seed_users(db: Session):
    """Cria usuários iniciais."""
    logger.info("👥 Criando usuários iniciais...")
    
    users = [
        {
            "name": "Administrador",
            "email": "admin@olimpiadas.com", 
            "password": "Admin@123456",
            "role": UserRole.ADMIN,
            "is_active": True,
            "is_email_verified": True
        },
        {
            "name": "Professor Exemplo",
            "email": "professor@olimpiadas.com",
            "password": "Prof@123456", 
            "role": UserRole.PROFESSOR,
            "is_active": True,
            "is_email_verified": True
        },
        {
            "name": "João Silva",
            "email": "joao.silva@escola.com",
            "password": "MinhaSenh@123",
            "role": UserRole.PROFESSOR,
            "is_active": True,
            "is_email_verified": True
        }
    ]
    
    for user_data in users:
        existing = db.query(User).filter(User.email == user_data["email"]).first()
        if not existing:
            user = User(
                name=user_data["name"],
                email=user_data["email"],
                password_hash=get_password_hash(user_data["password"]),
                role=user_data["role"],
                is_active=user_data["is_active"],
                is_email_verified=user_data["is_email_verified"]
            )
            db.add(user)
            logger.info(f"  ✓ Usuário criado: {user_data['email']} (senha: {user_data['password']})")
    
    db.commit()
    logger.info("✅ Usuários criados!")


def main():
    """Função principal do seed."""
    logger.info("🌱 Iniciando seed do banco de dados...")
    
    try:
        # Cria tabelas se não existirem
        create_tables()
        
        # Cria sessão do banco
        db = SessionLocal()
        
        try:
            # Popula dados iniciais
            seed_categories(db)
            seed_graus(db)
            seed_users(db)
            
            logger.info("🎉 Seed concluído com sucesso!")
            logger.info("\n" + "="*60)
            logger.info("📧 CREDENCIAIS DE ACESSO:")
            logger.info("  👑 Admin: admin@olimpiadas.com / Admin@123456")  
            logger.info("  👨‍🏫 Prof: professor@olimpiadas.com / Prof@123456")
            logger.info("  👤 User: joao.silva@escola.com / MinhaSenh@123")
            logger.info("="*60)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Erro durante o seed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

