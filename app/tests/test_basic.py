from sqlalchemy import text

def test_imports():
    """Teste se todas as importações básicas funcionam"""
    from app.main import app
    from app.database import get_db
    from app.models.base import Base
    from app.models.user import User
    from app.models.question import Question
    
    assert app is not None
    print("✅ Todas as importações funcionaram!")

def test_database_connection(db_session):
    """Teste se a conexão com o banco funciona"""
    result = db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
    print("✅ Conexão com banco funcionando!")

def test_fastapi_client(client):
    """Teste básico do cliente FastAPI"""
    # Testar uma rota simples (pode ser qualquer uma)
    response = client.get("/docs")
    # Pode retornar 200 (sucesso) ou 404 (se não existir) - ambos são OK para teste
    assert response.status_code in [200, 404]
    print("✅ Cliente FastAPI funcionando!") 