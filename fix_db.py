from app.database import engine
from sqlalchemy import text

def consertar_banco():
    print("🔧 Iniciando correção do banco de dados...")
    with engine.begin() as conn:
        # Adiciona as colunas ignorando erro caso já existam
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS status userstatus NOT NULL DEFAULT 'PENDING';"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_by_id INTEGER REFERENCES users(id);"))
        
    print("✅ Colunas 'status', 'approved_at' e 'approved_by_id' criadas com sucesso!")

if __name__ == "__main__":
    consertar_banco()

    #   python fix_db.py