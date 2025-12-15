"""Script para criar usuário administrador."""

import sys
from pathlib import Path
import getpass

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User
from app.models.user import UserRole
from app.core.security import get_password_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

 
def create_admin():
    """Cria usuário administrador interativamente."""
    logger.info("👑 Criação de usuário administrador")
    
    # Coleta dados do usuário
    name = input("Nome completo: ").strip()
    if not name:
        logger.error("Nome é obrigatório!")
        return
    
    email = input("Email: ").strip().lower()
    if not email or "@" not in email:
        logger.error("Email válido é obrigatório!")
        return
    
    while True:
        password = getpass.getpass("Senha: ")
        if len(password) < 8:
            logger.error("Senha deve ter pelo menos 8 caracteres!")
            continue
        
        password_confirm = getpass.getpass("Confirme a senha: ")
        if password != password_confirm:
            logger.error("Senhas não coincidem!")
            continue
        break
    
    # Cria usuário no banco
    db = SessionLocal()
    try:
        # Verifica se usuário já existe
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            logger.error(f"❌ Usuário com email {email} já existe!")
            return
        
        # Cria novo admin
        admin = User(
            name=name,
            email=email,
            password_hash=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,
            is_email_verified=True
        )
        
        db.add(admin)
        db.commit()
        
        logger.info(f"✅ Administrador criado com sucesso!")
        logger.info(f"   Nome: {name}")
        logger.info(f"   Email: {email}")
        logger.info(f"   ID: {admin.id}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar administrador: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()

