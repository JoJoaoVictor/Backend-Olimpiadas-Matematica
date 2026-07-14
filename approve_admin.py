from app.database import engine
from sqlalchemy import text

def aprovar_admin():
    print("🔧 Liberando acesso do Administrador...")
    with engine.begin() as conn:
        # Aprova especificamente o seu e-mail
        conn.execute(text(
            "UPDATE users SET status = 'APPROVED', is_active = true WHERE email = 'joaopadilha333@gmail.com';"
        ))
        
        # Opcional: Se você tiver outras contas de ADMIN, aprova todas elas de uma vez por precaução
        conn.execute(text(
            "UPDATE users SET status = 'APPROVED' WHERE role = 'ADMIN';"
        ))
        
    print("✅ Sua conta foi aprovada com sucesso! Pode entrar!")

if __name__ == "__main__":
    aprovar_admin()

    #     python approve_admin.py