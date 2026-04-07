"""
Script de migração: adiciona a coluna reviewed_by_id na tabela questions.
Arquivo: scripts/add_reviewed_by_column.py

Execução:
    python scripts/add_reviewed_by_column.py

Efeito:
    - Adiciona coluna reviewed_by_id (INTEGER, nullable, FK -> users.id)
    - Cria índice para performance nas queries de filtro por revisor
    - Questões existentes ficam com reviewed_by_id = NULL (não revisadas)
    - Idempotente: se a coluna já existir, o script avisa e encerra sem erro
"""

import sys
import os

# Garante que o path raiz do projeto está no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import engine


def column_exists(conn, table: str, column: str) -> bool:
    """Verifica se uma coluna já existe na tabela (SQLite compatível)."""
    result = conn.execute(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result.fetchall()]
    return column in columns


def run_migration():
    print("=" * 55)
    print("Migração: add reviewed_by_id em questions")
    print("=" * 55)

    with engine.connect() as conn:

        # ── 1. Verifica se já existe ──────────────────────────────────────
        if column_exists(conn, "questions", "reviewed_by_id"):
            print("✅ Coluna 'reviewed_by_id' já existe. Nada a fazer.")
            return

        # ── 2. Adiciona a coluna ──────────────────────────────────────────
        print("➕ Adicionando coluna reviewed_by_id...")
        conn.execute(text(
            "ALTER TABLE questions "
            "ADD COLUMN reviewed_by_id INTEGER REFERENCES users(id)"
        ))

        # ── 3. Cria índice para performance ───────────────────────────────
        # Necessário pois o filtro `WHERE reviewed_by_id = ?` é executado
        # em toda listagem de questões para revisores.
        print("🔍 Criando índice ix_questions_reviewed_by_id...")
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_questions_reviewed_by_id "
            "ON questions (reviewed_by_id)"
        ))

        conn.commit()
        print("✅ Migração concluída com sucesso.")
        print("   Questões existentes têm reviewed_by_id = NULL (não revisadas).")


if __name__ == "__main__":
    run_migration()