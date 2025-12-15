import pytest
import os
import sys
from pathlib import Path

# =============================================================================
# ⚠️ CONFIGURAR ENVIRONMENT ANTES DE QUALQUER IMPORTAÇÃO ⚠️
# =============================================================================

# CONFIGURAR VARIÁVEIS DE TESTE PRIMEIRO
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest"

# SÓ DEPOIS configurar Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# AGORA importar módulos da aplicação
from app.main import app
from app.database import get_db
from app.models.base import Base

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Adicione isto ao seu conftest.py existente:

# Configurar banco de teste
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False}
)

TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def db_session():
    """Sessão isolada por teste"""
    # CRIAR TABELAS antes do teste
    Base.metadata.create_all(bind=engine)
    
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    # LIMPEZA
    session.close()
    transaction.rollback()
    connection.close()
    Base.metadata.drop_all(bind=engine)  # Limpar depois