"""
Migração: adiciona colunas de cabeçalho/rodapé customizável à tabela exams.

Como rodar:
    python scripts/add_exam_layout_columns.py

Colunas adicionadas:
    - header_image  TEXT NULL      → imagem do cabeçalho em base64 ou path
    - footer_image  TEXT NULL      → imagem do rodapé em base64 ou path
    - header_size   REAL NOT NULL  → tamanho do cabeçalho em % (50–150, padrão 100)
    - footer_size   REAL NOT NULL  → tamanho do rodapé em % (50–150, padrão 100)

O script é idempotente: pode ser rodado múltiplas vezes sem erros.
"""

import sys
import sqlite3
import logging
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """Localiza o arquivo test.db na raiz do projeto."""
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
        raise FileNotFoundError(
            f"Banco de dados não encontrado em: {db_path}\n"
            "Certifique-se de que o servidor foi iniciado ao menos uma vez para criar o banco."
        )
    return db_path


def get_existing_columns(cursor: sqlite3.Cursor, table: str) -> set:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def migrate(db_path: Path) -> None:
    logger.info(f"Banco de dados: {db_path}")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        existing = get_existing_columns(cursor, "exams")
        logger.info(f"Colunas atuais em 'exams': {sorted(existing)}")

        # (nome, tipo SQL, default — None = coluna nullable sem default)
        colunas = [
            ("header_image", "TEXT", None),
            ("footer_image", "TEXT", None),
            ("header_size",  "REAL", 100.0),
            ("footer_size",  "REAL", 100.0),
        ]

        adicionadas = []
        for col_name, col_type, default in colunas:
            if col_name in existing:
                logger.info(f"  ⏭  '{col_name}' já existe — ignorando.")
                continue

            if default is None:
                ddl = f"ALTER TABLE exams ADD COLUMN {col_name} {col_type}"
            else:
                ddl = f"ALTER TABLE exams ADD COLUMN {col_name} {col_type} NOT NULL DEFAULT {default}"

            cursor.execute(ddl)
            adicionadas.append(col_name)
            logger.info(f"  ✅ '{col_name}' adicionada ({col_type}, default={default}).")

        conn.commit()

        if adicionadas:
            logger.info(f"\n🎉 Migração concluída! {len(adicionadas)} coluna(s): {adicionadas}")
        else:
            logger.info("\n✅ Banco já estava atualizado — nenhuma alteração necessária.")

        final = get_existing_columns(cursor, "exams")
        logger.info(f"Colunas finais em 'exams': {sorted(final)}")

    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"❌ Erro SQLite: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        db_path = get_db_path()
        migrate(db_path)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erro inesperado: {e}")
        sys.exit(1)