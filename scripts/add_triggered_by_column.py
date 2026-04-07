"""
Script de Migração: Adicionar coluna 'triggered_by_user_id' à tabela 'notifications'
Arquivo: scripts/add_triggered_by_column.py
Adiciona a coluna triggered_by_user_id se ainda não existir na tabela de notificações.

Uso: python scripts/add_triggered_by_column.py
"""

import sqlite3
from pathlib import Path
import sys

# Adiciona o diretório raiz ao path para importar app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def add_triggered_by_column():
    """Adiciona a coluna 'triggered_by_user_id' à tabela 'notifications' se ainda não existir."""
    
    # Conecta ao banco de dados SQLite
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    
    try:
        # Verifica se a coluna já existe
        cursor.execute("PRAGMA table_info(notifications);")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'triggered_by_user_id' in column_names:
            print("✅ Coluna 'triggered_by_user_id' já existe!")
            return True
        
        # Adiciona a coluna se não existir
        alter_table_sql = """
        ALTER TABLE notifications 
        ADD COLUMN triggered_by_user_id INTEGER;
        """
        
        cursor.execute(alter_table_sql)
        
        # Cria o índice para a nova coluna
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_notifications_triggered_by_user_id ON notifications (triggered_by_user_id);")
        
        connection.commit()
        print("✅ Coluna 'triggered_by_user_id' adicionada com sucesso!")
        print("✅ Índice criado para otimização de queries")
        
    except sqlite3.OperationalError as e:
        print(f"❌ Erro ao adicionar coluna: {e}")
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
    print("🔄 Iniciando migração para adicionar coluna 'triggered_by_user_id'...")
    success = add_triggered_by_column()
    sys.exit(0 if success else 1)
