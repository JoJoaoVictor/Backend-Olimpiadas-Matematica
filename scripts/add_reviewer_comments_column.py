"""
Script para adicionar coluna reviewer_comments à tabela exams.
Executar uma única vez via: python scripts/add_reviewer_comments_column.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal, engine

def add_reviewer_comments_column():
    with engine.connect() as conn:
        # Verificar se a coluna já existe (SQLite)
        result = conn.execute(text("PRAGMA table_info(exams)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'reviewer_comments' not in columns:
            print("Adicionando coluna 'reviewer_comments'...")
            conn.execute(text("ALTER TABLE exams ADD COLUMN reviewer_comments TEXT"))
            conn.commit()
            print("Coluna adicionada com sucesso.")
        else:
            print("Coluna 'reviewer_comments' já existe.")

if __name__ == "__main__":
    add_reviewer_comments_column()