import pytest
from app.models.user import User
from app.schemas.auth import UserRegister

def test_user_registration(client, db_session):
    """
    Teste de registro de usuário via endpoint HTTP.
    Verifica status, resposta e criação no banco.
    """
    # Dados de teste
    user_data = {
    "email": "login@example.com",
    "password": "Senha123",
    "name": "Test User"
}
    
    # Chamar endpoint de registro
    response = client.post("/api/v1/auth/register", json=user_data)
    
    # Verificações
    assert response.status_code == 201
    data = response.json()

     # Acesse a estrutura correta
    assert data["success"] == True
    assert data["data"]["user"]["email"] == user_data["email"]
    assert data["data"]["user"]["name"] == user_data["name"]  
    assert "id" in data["data"]["user"]
    assert "password" not in data["data"]["user"]  # Senha não deve retornar
    
    # Verificar se usuário foi criado no banco
    user_in_db = db_session.query(User).filter(User.email == user_data["email"]).first()
    assert user_in_db is not None
    assert user_in_db.email == user_data["email"]

def test_user_login(client, db_session):
    """
    Teste de login após registro.
    """
    # Primeiro registrar usuário
    user_data = {
        "email": "login@example.com", 
        "password": "Senha123",
        "name": "Login User"
    }
    client.post("/api/v1/auth/register", json=user_data)
    
    # Tentar login
    login_data = {
        "email": "login@example.com",
        "password": "Senha123"
    }
    response = client.post("/api/v1/auth/login", json=login_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data ["data"]["tokens"]
    assert data ["data"]["tokens"]["token_type"]  == "bearer"