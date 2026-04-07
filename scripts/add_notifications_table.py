"""
Script de Migração: Criar tabela 'notifications'
Arquivo: scripts/add_notifications_table.py
Cria a tabela de notificações no banco SQLite sem apagar dados existentes.

Uso: python scripts/add_notifications_table.py
"""

import sqlite3
from pathlib import Path
import sys

# Adiciona o diretório raiz ao path para importar app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def create_notifications_table():
    """Cria a tabela 'notifications' se ainda não existir."""
    
    # Conecta ao banco de dados SQLite
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    
    try:
        # Cria a tabela com IF NOT EXISTS para segurança
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            triggered_by_user_id INTEGER,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            entity_type VARCHAR(20) NOT NULL,
            entity_id INTEGER NOT NULL,
            is_read BOOLEAN DEFAULT 0 NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (triggered_by_user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        """
        
        cursor.execute(create_table_sql)
        
        # Cria índices para otimização de queries
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_notifications_triggered_by_user_id ON notifications (triggered_by_user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_notifications_type ON notifications (type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_notifications_entity_type ON notifications (entity_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_notifications_entity_id ON notifications (entity_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read);")
        
        connection.commit()
        print("✅ Tabela 'notifications' criada com sucesso!")
        print("✅ Índices criados para otimização de queries")
        
    except sqlite3.OperationalError as e:
        print(f"❌ Erro ao criar tabela: {e}")
        connection.rollback()
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()
    
    return True


if __name__ == "__main__":
    print("🔄 Iniciando migração da tabela de notificações...")
    success = create_notifications_table()
    sys.exit(0 if success else 1)
