"""
Migração: adiciona coluna 'ano' à tabela exams.

Como rodar:
    python scripts/add_exam_ano_column.py

Coluna adicionada:
    - ano  INTEGER NOT NULL DEFAULT <ano_atual>

O script é idempotente: pode ser rodado múltiplas vezes sem erros.
"""

import sys
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    db_path = root / "test.db"
    if not db_path.exists():
        try:
            from app.database import DATABASE_URL
            raw = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
            candidate = Path(raw) if Path(raw).is_absolute() else root / raw.lstrip("./")
            if candidate.exists():
                return candidate
        except Exception:
            pass
        raise FileNotFoundError(f"Banco de dados não encontrado em: {db_path}")
    return db_path


def migrate(db_path: Path) -> None:
    logger.info(f"Banco de dados: {db_path}")
    ano_atual = datetime.now().year

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(exams)")
        colunas = {row[1] for row in cursor.fetchall()}
        logger.info(f"Colunas atuais: {sorted(colunas)}")

        if "ano" in colunas:
            logger.info("  ⏭  Coluna 'ano' já existe — ignorando.")
        else:
            cursor.execute(f"ALTER TABLE exams ADD COLUMN ano INTEGER NOT NULL DEFAULT {ano_atual}")
            conn.commit()
            logger.info(f"  ✅ Coluna 'ano' adicionada (INTEGER, default={ano_atual}).")

        logger.info("✅ Migração concluída.")

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"❌ Erro SQLite: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        migrate(get_db_path())
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)